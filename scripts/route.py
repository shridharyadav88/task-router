#!/usr/bin/env python3
"""task-router: recommend-only deterministic lookup, table-driven (stdlib only).

Sizing is done OUTSIDE this script by Jev/elephant (Choice/Score/Noul).
This script maps final size x quota x installed -> cheapest capable pick,
reading rows/chains/effort from references/routing-table.json.
Behavior contract (frozen from the hardcoded v0.1.0, verified by parity):
separate weekly/5h pools, S punches through weekly RESERVE only,
downgrade on 5h LOW only, UNKNOWN counts as LOW (actionable),
spread pre-scan with override, self-agent post-scan, MAX_SPEC guard.
Exit 0 = recommendation. Exit 2 = clarify / defer / spec_too_long.
Exit 1 = error. Audit: one JSON dict per decision (hashes only).
"""
import argparse
import hashlib
import json
import os
import sys
import time

ROUTER_V = "0.4.0"
HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TABLE = os.path.join(HERE, "..", "references", "routing-table.json")

POOL_NUMERIC = {"claude", "codex"}
AGENT_POOL = {"claude-code": "claude", "codex": "codex", "muse": "muse",
              "opencode": "opencode", "cursor-agent": "cursor"}


_QRES, _QLOW = 0.2, 0.5  # overridden from the table's quota block


def state(v):
    if v is None or v < 0:
        return "LOW"  # UNKNOWN counts as LOW: actionable, never a skip
    if v < _QRES:
        return "RESERVE"
    if v < _QLOW:
        return "LOW"
    return "OK"


def set_thresholds(table):
    global _QRES, _QLOW
    _QRES = table["quota"]["reserve_below"]
    _QLOW = table["quota"]["low_below"]


def load_table(path):
    with open(path) as f:
        t = json.load(f)
    for k in ("table_v", "bars", "rows", "effort", "chains", "quota",
              "timeouts_min", "cmd", "downgrade"):
        if k not in t:
            raise ValueError("routing table missing key: " + k)
    for rid, r in t["rows"].items():
        if r.get("worker") is False:
            continue
        for k in ("agent", "model", "pool"):
            if k not in r:
                raise ValueError("row %s missing %s" % (rid, k))
    for sz, chain in t["chains"].items():
        if not chain:
            raise ValueError("chain %s is empty" % sz)
        for rid in chain:
            if rid not in t["rows"]:
                raise ValueError("chain %s references unknown row %s" % (sz, rid))
            r = t["rows"][rid]
            if r.get("worker") is False:
                raise ValueError("chain %s references non-worker %s" % (sz, rid))
            ag = r["agent"]
            if sz not in t.get("effort", {}) or ag not in t["effort"][sz]:
                raise ValueError("effort missing for %s/%s" % (sz, ag))
            if ag not in t["cmd"]:
                raise ValueError("cmd template missing for %s" % ag)
    return t


def main():
    p = argparse.ArgumentParser(description="task-router recommend-only lookup")
    p.add_argument("--spec", required=False, default="",
                   help="path to the task spec file")
    p.add_argument("--size", required=False, default="",
                   choices=["S", "M", "L", "XL", ""])
    p.add_argument("--choice", default="", help="raw Choice value (for audit)")
    p.add_argument("--noul", action="store_true", help="spec too vague -> clarify")
    p.add_argument("--self-agent", default="",
                   help="calling agent id: prefer it on ties")
    p.add_argument("--no-codex-ok", action="store_true",
                   help="R3 has no index row: codex fallback-only")
    p.add_argument("--claude-wk", type=float, default=-1.0)
    p.add_argument("--claude-h5", type=float, default=-1.0)
    p.add_argument("--codex-wk", type=float, default=-1.0)
    p.add_argument("--codex-h5", type=float, default=-1.0)
    p.add_argument("--quota-src", default="est",
                   help="provenance: est, measured, user-GT, metered-screenshot, probe, vendor-table")
    p.add_argument("--cursor-model", default="")
    p.add_argument("--avoid-agent", action="append", default=[],
                   help="spread rule: skip this provider if an alternative clears the bar")
    p.add_argument("--cursor-mult", type=float, default=-1.0)
    p.add_argument("--provider-down", action="append", default=[],
                   help="presence-pool agent assumed exhausted (muse/opencode/cursor)")
    p.add_argument("--engine", default="jev", choices=["jev", "elephant"])
    p.add_argument("--engine-v", default="")
    p.add_argument("--prompt-sha", default="")
    p.add_argument("--max-spec-chars", type=int, default=48000)
    p.add_argument("--table", default=DEFAULT_TABLE)
    p.add_argument("--log", default=os.path.expanduser(
        "~/.local/state/task-router/decisions.jsonl"))
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()

    try:
        table = load_table(a.table)
    except (OSError, ValueError) as e:
        print(json.dumps({"action": "error",
                          "why": "bad_table: " + str(e)[:150]}, indent=2))
        return 1
    set_thresholds(table)
    down = set(a.provider_down or [])
    quota_nums = {"claude": {"wk": a.claude_wk, "h5": a.claude_h5},
                  "codex": {"wk": a.codex_wk, "h5": a.codex_h5}}
    if "claude-code" in down or "claude" in down:
        quota_nums["claude"] = {"wk": 0.0, "h5": 0.0}
    if "codex" in down:
        quota_nums["codex"] = {"wk": 0.0, "h5": 0.0}

    if a.self_test:
        return self_test(table, a)

    if not a.size:
        print(json.dumps({"action": "error", "why": "size_required",
                          "note": "--size S|M|L|XL is required"}, indent=2))
        return 2

    if a.noul:
        print(json.dumps({"action": "clarify", "final_size": None,
                          "ask": ["goal in one line", "files/area touched",
                                  "done = which tests"],
                          "note": "never guess XL on a vague spec"}, indent=2))
        return 2
    try:
        with open(a.spec, "r", errors="replace") as f:
            text = f.read()
    except OSError as e:
        print("spec unreadable: %s" % e, file=sys.stderr)
        return 1
    if len(text) > a.max_spec_chars:
        print(json.dumps({"action": "spec_too_long",
                          "spec_chars": len(text),
                          "max_chars": a.max_spec_chars,
                          "note": "trim the spec, never truncate silently"}, indent=2))
        return 2
    sha = hashlib.sha256(text.encode()).hexdigest()[:16]
    codex_ok = not a.no_codex_ok

    quota = {"claude-code": {"wk": quota_nums["claude"]["wk"],
                             "h5": quota_nums["claude"]["h5"],
                             "src": a.quota_src},
             "codex": {"wk": quota_nums["codex"]["wk"],
                       "h5": quota_nums["codex"]["h5"], "src": a.quota_src}}
    for ag in ("muse", "opencode", "cursor-agent"):
        quota[ag] = {"state": "RESERVE(flagged_down)"
                     if ag in down else "OK", "src": a.quota_src}

    def pool_ok(agent, size):
        pool = AGENT_POOL[agent]
        if pool in POOL_NUMERIC:
            q = quota_nums[pool]
            if state(q["h5"]) == "RESERVE":
                return False
            if state(q["wk"]) == "RESERVE" and size != "S":
                return False
            return True
        return agent not in down

    def actionable(row, agent):
        if row == "R3" and not codex_ok:
            return False
        if agent == "cursor-agent" and (not a.cursor_model or a.cursor_mult > 2):
            return False
        if table["effort"][a.size].get(agent) is None:
            return False
        if agent in ("muse", "opencode") and agent in down:
            return False
        return True

    # spread rule: honor --avoid-agent only while an alternative stays actionable
    avoid = set(a.avoid_agent or [])
    chain_agents = [(r, table["rows"][r]["agent"])
                    for r in table["chains"][a.size]]
    if avoid and not any(actionable(r, ag) for r, ag in chain_agents
                         if ag not in avoid):
        if any(actionable(r, ag) for r, ag in chain_agents):
            warnings0 = ["spread_overridden_no_alternative"]
            avoid = set()
        else:
            warnings0 = []
    else:
        warnings0 = []
    rejected = []
    pick = None
    ranked = []
    warnings = list(warnings0)

    if a.size == "XL" and state(quota_nums["claude"]["wk"]) == "RESERVE":
        out = {"action": "defer", "final_size": "XL",
               "why": "weekly headroom under 20% and XL cannot degrade twice",
               "spec_sha256": sha}
        print(json.dumps(out, indent=2))
        return 2

    for row, agent in chain_agents:
        if table["rows"][row].get("worker") is False:
            continue
        entry = {"row": row, "agent": agent, "status": "skipped", "why": None}
        if row == "R3" and not codex_ok:
            entry["why"] = "no_index_row"
            rejected.append({"row": row, "agent": agent, "why": "no_index_row"})
            ranked.append(entry)
            continue
        if agent in avoid:
            entry["why"] = "spread_avoided"
            rejected.append({"row": row, "agent": agent, "why": "spread_avoided"})
            ranked.append(entry)
            continue
        if agent == "cursor-agent":
            if a.cursor_mult > 2:
                entry["why"] = "multiplier>2x"
                rejected.append({"row": "CURSOR", "agent": agent,
                                 "why": "multiplier>2x"})
                ranked.append(entry)
                continue
            if not a.cursor_model:
                entry["why"] = "model_not_pinned"
                rejected.append({"row": "CURSOR", "agent": agent,
                                 "why": "model_not_pinned"})
                ranked.append(entry)
                continue
            if a.cursor_mult < 0:
                warnings.append("cursor_multiplier_unmeasured")
            effort = {"S": "low", "M": "medium", "L": "high"}[a.size]
            pick = {"agent": agent, "model": a.cursor_model, "effort": effort,
                    "row": "CURSOR", "emergency": True}
            entry.update(status="picked", effort=effort)
            ranked.append(entry)
            break
        pool = AGENT_POOL[agent]
        if pool in POOL_NUMERIC:
            q = quota_nums[pool]
            if state(q["wk"]) == "RESERVE" and a.size != "S":
                entry["why"] = "weekly_RESERVE"
                rejected.append({"row": row, "agent": agent,
                                 "why": "weekly_RESERVE"})
                ranked.append(entry)
                continue
            if state(q["h5"]) == "RESERVE":
                entry["why"] = "h5_RESERVE"
                rejected.append({"row": row, "agent": agent, "why": "h5_RESERVE"})
                ranked.append(entry)
                continue
        else:
            if agent in down:
                entry["why"] = "pool_flagged_down"
                rejected.append({"row": row, "agent": agent,
                                 "why": "pool_flagged_down"})
                ranked.append(entry)
                continue
        effort = table["effort"][a.size].get(agent)
        if effort is None:
            why = ("not_eligible_for_XL" if a.size == "XL"
                   else "not_eligible_for_size")
            entry["why"] = why
            rejected.append({"row": row, "agent": agent, "why": why})
            ranked.append(entry)
            continue
        if pool in POOL_NUMERIC:
            if state(quota_nums[pool]["h5"]) == "LOW" and not (
                    a.size == "XL" and row == "R1"):
                effort = table["downgrade"].get(effort, effort)
                warnings.append("%s_h5_LOW_downgraded_to_%s" % (agent, effort))
        if agent == "opencode":
            model = effort  # effort slot carries the free model id
        else:
            model = table["rows"][row]["model"]
        entry_pick = {"agent": agent, "model": model, "effort": effort,
                      "row": row}
        for rid2, w in table.get("warnings", {}).items():
            if rid2 == row and a.size in w:
                warnings.append(w[a.size])
        pick = entry_pick
        entry.update(status="picked", effort=effort)
        ranked.append(entry)
        break

    # remaining chain rows become ranked fallbacks (evaluated, not launched)
    seen = {e["row"] for e in ranked}
    for row, agent in chain_agents:
        if row in seen or table["rows"][row].get("worker") is False:
            continue
        effort = table["effort"][a.size].get(agent)
        if agent == "cursor-agent" and (not a.cursor_model or a.cursor_mult > 2):
            why = "model_not_pinned" if not a.cursor_model else "multiplier>2x"
        elif row == "R3" and not codex_ok:
            why = "no_index_row"
        elif effort is None:
            why = "not_eligible_for_size"
        elif agent in avoid:
            why = "spread_avoided"
        elif not pool_ok(agent, a.size):
            why = "quota_reserve"
        else:
            why = None
        fe = {"row": row, "agent": agent, "status":
              "fallback" if why is None else "skipped", "why": why}
        if why is None:
            feff = effort
            pool = AGENT_POOL[agent]
            if pool in POOL_NUMERIC and state(quota_nums[pool]["h5"]) == "LOW" \
                    and not (a.size == "XL" and row == "R1"):
                feff = table["downgrade"].get(feff, feff)
            fe["effort"] = feff
            if agent == "cursor-agent":
                fe["model"] = a.cursor_model
            elif agent == "opencode":
                fe["model"] = feff
            else:
                fe["model"] = table["rows"][row]["model"]
        ranked.append(fe)

    if pick is None:
        print(json.dumps({"action": "defer", "final_size": a.size,
                          "why": "no eligible row", "rejected": rejected,
                          "spec_sha256": sha}, indent=2))
        return 2

    if a.self_agent and a.self_agent != pick["agent"]:
        for row, agent in chain_agents:
            if agent == a.self_agent and row != "CURSOR":
                if pool_ok(agent, a.size) and not (row == "R3" and not codex_ok):
                    rejected.append({"row": pick["row"], "agent": pick["agent"],
                                     "why": "self_agent_preferred"})
                    em = table["effort"][a.size].get(agent)
                    pick = {"agent": agent,
                            "model": table["rows"][row]["model"],
                            "effort": em, "row": row, "preferred_self": True}
                break
        else:
            if a.self_agent == "local-llm":
                rejected.append({"row": "-", "agent": "local-llm",
                                 "why": "non_code_chores_only"})

    agent = pick["agent"]
    if agent == "opencode":
        cmd = table["cmd"]["opencode"].replace("{model}", pick["model"])
    elif agent == "muse":
        cmd = table["cmd"]["muse"]
    elif agent == "cursor-agent":
        cmd = table["cmd"]["cursor-agent"].replace("{model}", pick["model"])
    else:
        cmd = table["cmd"][agent].replace("{model}", pick["model"]).replace(
            "{effort}", pick["effort"])
    pick["cmd"] = cmd
    if warnings:
        pick["warnings"] = warnings
    out = {"ts": int(time.time()), "spec_sha256": sha, "router_v": ROUTER_V,
           "table_v": table["table_v"], "engine": a.engine,
           "engine_v": a.engine_v, "prompt_sha256": a.prompt_sha,
           "choice": a.choice or a.size, "bumped": False, "final_size": a.size,
           "pick": pick, "rejected": rejected, "quota_before": quota,
           "done": "tests pass (caller checks)", "outcome": None,
           "escalations": 0, "override": None, "candidates": ranked}
    print(json.dumps({"final_size": a.size, "pick": pick, "rejected": rejected,
                      "candidates": ranked, "spec_sha256": sha,
                      "done": out["done"]}, indent=2))
    try:
        os.makedirs(os.path.dirname(a.log) or ".", exist_ok=True)
        with open(a.log, "a") as f:
            f.write(json.dumps(out) + "\n")
    except OSError as e:
        print("audit append failed: %s" % e, file=sys.stderr)
        return 1
    return 0


def self_test(table, a):
    errs = []
    if not table.get("table_v"):
        errs.append("no table_v")
    if set(table.get("chains", {})) != {"S", "M", "L", "XL"}:
        errs.append("chains != S/M/L/XL")
    with open("/tmp/route-selftest-spec.txt", "w") as f:
        f.write("add dark mode toggle\nDone = relevant tests pass.\n")
    import subprocess
    base = [sys.executable, os.path.join(HERE, "route.py"),
            "--table", a.table, "--spec", "/tmp/route-selftest-spec.txt",
            "--claude-wk", "1", "--claude-h5", "1",
            "--codex-wk", "1", "--codex-h5", "1",
            "--log", "/tmp/route-selftest-audit.jsonl"]
    r = subprocess.run(base + ["--size", "S"], capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        if (d.get("pick") or {}).get("row") != "R3":
            errs.append("S smoke did not pick R3: " + r.stdout[:120])
    except ValueError:
        errs.append("S smoke not JSON")
    r = subprocess.run(base + ["--size", "XL", "--claude-wk", "0.01",
                               "--claude-h5", "0.01"],
                       capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        if d.get("action") != "defer":
            errs.append("XL reserve did not defer: " + r.stdout[:120])
    except ValueError:
        errs.append("XL smoke not JSON")
    print(json.dumps({"self_test": "pass" if not errs else "fail",
                      "table_v": table.get("table_v"), "errors": errs}))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
