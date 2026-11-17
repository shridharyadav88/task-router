#!/usr/bin/env python3
"""task-router v0: recommend-only deterministic lookup (stdlib only).

Sizing is done OUTSIDE this script by Jev/elephant (Choice/Score/Noul).
This script maps final size x quota x installed -> cheapest capable pick.
Exit 0 = recommendation. Exit 2 = clarify / defer / spec_too_long. Exit 1 = error.
Audit: appends one JSONL line per decision (hashes only, no text/secrets).
"""
import argparse
import hashlib
import json
import os
import sys
import time

ROUTER_V = "0.1.0"
TABLE_V = "2026-12"
MAX_SPEC_CHARS = 48000  # ~12k tokens; over this the spec must be trimmed, never truncated silently

INDEX = {"R1": 61.7, "R2": 59.3, "R3": 54.4}
EFFORT = {
    "S": {"claude-code": "low", "codex": "low"},
    "M": {"claude-code": "medium", "codex": "medium"},
    "L": {"claude-code": "high", "codex": "high"},
    "XL": {"claude-code": "max", "codex": None},
}
DOWN = {"max": "high", "high": "medium", "medium": "low", "low": "low"}
CHAINS = {
    "S": [("R3", "codex"), ("R2", "claude-code"), ("CURSOR", "cursor-agent")],
    "M": [("R3", "codex"), ("R2", "claude-code"), ("CURSOR", "cursor-agent")],
    "L": [("R2", "claude-code"), ("R3", "codex"), ("CURSOR", "cursor-agent")],
    "XL": [("R1", "claude-code"), ("R2", "claude-code")],
}


def state(v):
    if v is None or v < 0:
        return "LOW"  # UNKNOWN counts as LOW
    if v < 0.2:
        return "RESERVE"
    if v < 0.5:
        return "LOW"
    return "OK"


def cmd_for(agent, model, effort, cursor_model):
    if agent == "claude-code":
        return "claude --model %s --effort %s -p '<task>'" % (model, effort)
    if agent == "codex":
        return "codex exec '<task>' -c model_reasoning_effort=\"%s\"" % effort
    return "cursor-agent --model %s -p '<task>'" % (cursor_model or "<PINNED-ID>")


def main():
    p = argparse.ArgumentParser(description="task-router v0 recommend-only lookup")
    p.add_argument("--spec", required=True, help="path to the task spec file")
    p.add_argument("--size", required=True, choices=["S", "M", "L", "XL"])
    p.add_argument("--bumped", action="store_true", help="Score bump applied (+1 step)")
    p.add_argument("--choice", default="", help="raw Choice value (for audit)")
    p.add_argument("--noul", action="store_true", help="spec too vague -> clarify")
    p.add_argument("--self-agent", default="", help="calling agent id: prefer it on ties")
    p.add_argument("--no-codex-ok", action="store_true", help="R3 has no index row: codex fallback-only")
    p.add_argument("--claude-wk", type=float, default=-1.0)
    p.add_argument("--claude-h5", type=float, default=-1.0)
    p.add_argument("--codex-wk", type=float, default=-1.0)
    p.add_argument("--codex-h5", type=float, default=-1.0)
    p.add_argument("--quota-src", default="est",
                   help="provenance of the quota numbers: est, measured, user-GT, metered-screenshot, probe, vendor-table")
    p.add_argument("--cursor-model", default="")
    p.add_argument("--avoid-agent", action="append", default=[],
                   help="spread rule: skip this provider if an alternative clears the bar")
    p.add_argument("--cursor-mult", type=float, default=-1.0)
    p.add_argument("--engine", default="jev", choices=["jev", "elephant"])
    p.add_argument("--engine-v", default="")
    p.add_argument("--prompt-sha", default="")
    p.add_argument("--log", default=os.path.expanduser("~/.local/state/task-router/decisions.jsonl"))
    a = p.parse_args()

    if a.noul:
        print(json.dumps({"action": "clarify", "final_size": None,
                          "ask": ["goal in one line", "files/area touched", "done = which tests"],
                          "note": "never guess XL on a vague spec"}, indent=2))
        return 2
    try:
        with open(a.spec, "r", errors="replace") as f:
            text = f.read()
    except OSError as e:
        print("spec unreadable: %s" % e, file=sys.stderr)
        return 1
    if len(text) > MAX_SPEC_CHARS:
        print(json.dumps({"action": "spec_too_long",
                          "spec_chars": len(text), "max_chars": MAX_SPEC_CHARS,
                          "note": "trim the spec, never truncate silently"}, indent=2))
        return 2
    sha = hashlib.sha256(text.encode()).hexdigest()[:16]
    codex_ok = not a.no_codex_ok
    quota = {"claude-code": {"wk": a.claude_wk, "h5": a.claude_h5, "src": a.quota_src},
             "codex": {"wk": a.codex_wk, "h5": a.codex_h5, "src": a.quota_src}}
    # spread rule: honor --avoid-agent only while an alternative row stays actionable
    avoid = set(a.avoid_agent or [])
    def actionable(agent, row):
        if row == "R3" and not codex_ok:
            return False
        if agent == "cursor-agent" and (not a.cursor_model or a.cursor_mult > 2):
            return False
        if EFFORT[a.size][agent] is None:
            return False
        return True
    if avoid and not any(actionable(ag, r) for r, ag in CHAINS[a.size] if ag not in avoid):
        if any(actionable(ag, r) for r, ag in CHAINS[a.size]):
            warnings0 = ["spread_overridden_no_alternative"]
            avoid = set()
        else:
            warnings0 = []
    else:
        warnings0 = []
    rejected = []
    pick = None
    warnings = list(warnings0)

    if a.size == "XL" and state(a.claude_wk) == "RESERVE":
        out = {"action": "defer", "final_size": "XL",
               "why": "weekly headroom under 20% and XL cannot degrade twice",
               "spec_sha256": sha}
        print(json.dumps(out, indent=2))
        return 2

    for row, agent in CHAINS[a.size]:
        if row == "R3" and not codex_ok:
            rejected.append({"row": row, "agent": agent, "why": "no_index_row"})
            continue
        if agent in avoid:
            rejected.append({"row": row, "agent": agent, "why": "spread_avoided"})
            continue
        if agent == "cursor-agent":
            if a.cursor_mult > 2:
                rejected.append({"row": "CURSOR", "agent": agent, "why": "multiplier>2x"})
                continue
            if not a.cursor_model:
                rejected.append({"row": "CURSOR", "agent": agent, "why": "model_not_pinned"})
                continue
            if a.cursor_mult < 0:
                warnings.append("cursor_multiplier_unmeasured")
            effort = {"S": "low", "M": "medium", "L": "high"}[a.size]
            pick = {"agent": agent, "model": a.cursor_model, "effort": effort,
                    "row": "CURSOR", "emergency": True}
            break
        q = quota[agent]
        if state(q["wk"]) == "RESERVE" and a.size != "S":
            rejected.append({"row": row, "agent": agent, "why": "weekly_RESERVE"})
            continue
        if state(q["h5"]) == "RESERVE":
            rejected.append({"row": row, "agent": agent, "why": "h5_RESERVE"})
            continue
        effort = EFFORT[a.size][agent]
        if effort is None:
            rejected.append({"row": row, "agent": agent, "why": "not_eligible_for_XL"})
            continue
        if state(q["h5"]) == "LOW" and not (a.size == "XL" and row == "R1"):
            effort = DOWN[effort]
            warnings.append("%s_h5_LOW_downgraded_to_%s" % (agent, effort))
        model = {"R1": "opus", "R2": "sonnet", "R3": "default"}[row]
        entry = {"agent": agent, "model": model, "effort": effort, "row": row}
        if row == "R3" and a.size == "L":
            warnings.append("R3_below_L_bar")
        if row == "R2" and a.size == "XL":
            warnings.append("XL_degraded")
        pick = entry
        break

    if pick is None:
        print(json.dumps({"action": "defer", "final_size": a.size,
                          "why": "no eligible row", "rejected": rejected,
                          "spec_sha256": sha}, indent=2))
        return 2
    if a.self_agent and a.self_agent != pick["agent"]:
        for row, agent in CHAINS[a.size]:
            if agent == a.self_agent and row != "CURSOR":
                rq = quota.get(agent)
                if rq is not None and state(rq["wk"]) != "RESERVE" and state(rq["h5"]) != "RESERVE":
                    if not (row == "R3" and not codex_ok):
                        rejected.append({"row": pick["row"], "agent": pick["agent"],
                                         "why": "self_agent_preferred"})
                        em = EFFORT[a.size][agent]
                        pick = {"agent": agent,
                                "model": {"R1": "opus", "R2": "sonnet", "R3": "default"}[row],
                                "effort": em, "row": row, "preferred_self": True}
                break
        else:
            if a.self_agent == "local-llm":
                rejected.append({"row": "-", "agent": "local-llm", "why": "non_code_chores_only"})
    pick["cmd"] = cmd_for(pick["agent"], pick["model"], pick["effort"], a.cursor_model)
    if warnings:
        pick["warnings"] = warnings
    out = {"ts": int(time.time()), "spec_sha256": sha, "router_v": ROUTER_V,
           "table_v": TABLE_V, "engine": a.engine, "engine_v": a.engine_v,
           "prompt_sha256": a.prompt_sha, "choice": a.choice or a.size,
           "bumped": a.bumped, "final_size": a.size, "pick": pick,
           "rejected": rejected, "quota_before": quota,
           "done": "tests pass (caller checks)", "outcome": None,
           "escalations": 0, "override": None}
    print(json.dumps({"final_size": a.size, "pick": pick, "rejected": rejected,
                      "spec_sha256": sha, "done": out["done"]}, indent=2))
    try:
        os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
        with open(a.log, "a") as f:
            f.write(json.dumps(out) + "\n")
    except OSError as e:
        print("audit append failed: %s" % e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
