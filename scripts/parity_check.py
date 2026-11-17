#!/usr/bin/env python3
"""parity_check.py — evidence rig for table-driven routing (stdlib only).

Runs route.py over every task in a golden-set JSON with FROZEN quota flags and
reports agreement between each pick's agent/model/effort and the golden
`expected_pick`. Exit 0 iff agreement >= --min-agree (default 0.90).
Usage: python3 scripts/parity_check.py --golden references/golden-set.json
       [--route-py scripts/route.py] [--min-agree 0.9] [--out baseline.json]
Frozen quotas: all pools full/OK, codex default OK, cursor pinned cheap, mult 1.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


AGENT_ALIAS = {"claude": "claude-code", "codex": "codex", "cursor": "cursor-agent",
                "muse": "muse", "opencode": "opencode"}
CODEX_MODELS = {"default", "gpt-6-chat-thinking"}


def norm_expected(exp):
    exp = (exp or "").replace("/", " ").strip()
    if "clarify" in exp.lower():
        return "clarify", None, None
    parts = exp.split()
    if len(parts) == 3:
        ag, mo, ef = parts
        return AGENT_ALIAS.get(ag, ag), mo, ef
    if len(parts) == 2:
        ag, ef = parts
        ag = AGENT_ALIAS.get(ag, ag)
        return ag, ("default" if ag == "codex" else None), ef
    return None, None, None


def run_pick(route_py, spec_text, size, vague):
    with open("/tmp/parity-spec.txt", "w") as f:
        f.write(spec_text + "\n")
    cmd = [sys.executable, route_py, "--spec", "/tmp/parity-spec.txt",
           "--claude-wk", "1", "--claude-h5", "1",
           "--codex-wk", "1", "--codex-h5", "1",
           "--cursor-model", "test-pinned-cheap", "--cursor-mult", "1",
           "--log", "/tmp/parity-audit.jsonl"]
    if vague:
        cmd += ["--size", "M", "--noul"]
    else:
        cmd += ["--size", size]
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
    except ValueError:
        return {"action": "error", "stderr": r.stderr[-200:]}
    if "pick" in d:
        p = d["pick"]
        return {"agent": p["agent"], "model": p["model"], "effort": p["effort"],
                "row": p.get("row")}
    return d


def main():
    p = argparse.ArgumentParser(description="golden parity rig")
    p.add_argument("--golden", required=True)
    p.add_argument("--route-py", default=os.path.join(HERE, "route.py"))
    p.add_argument("--min-agree", type=float, default=0.9)
    p.add_argument("--out", default="")
    a = p.parse_args()
    gold = json.load(open(a.golden))
    tasks = gold["tasks"] if isinstance(gold, dict) else gold
    hits, total, rows = 0, 0, []
    for t in tasks:
        exp = t.get("expected_pick", "")
        got = run_pick(a.route_py, t["task"], t.get("label", "M"),
                       t.get("label") == "clarify")
        if "action" in got:
            match = (norm_expected(exp)[0] == "clarify" and got["action"] == "clarify")
            got_str = got["action"]
        else:
            got_str = "%s/%s/%s" % (got["agent"], got["model"], got["effort"])
            ea, em, ee = norm_expected(exp)
            if ea == "clarify":
                match = False
            elif (got["agent"], got["effort"]) != (ea, ee):
                match = False
            elif em is None:
                match = True
            elif got["agent"] == "codex":
                match = got["model"] in CODEX_MODELS
            else:
                match = got["model"] == em
        total += 1
        hits += bool(match)
        rows.append({"id": t["id"], "expected": exp, "got": got_str,
                     "match": bool(match)})
    agree = hits / total if total else 0
    print("agreement: %d/%d = %.3f" % (hits, total, agree))
    for r in rows:
        if not r["match"]:
            print("  MISS %s: expected %s, got %s" % (r["id"], r["expected"], r["got"]))
    if a.out:
        json.dump({"agreement": agree, "rows": rows}, open(a.out, "w"), indent=1)
    return 0 if agree >= a.min_agree else 1


if __name__ == "__main__":
    sys.exit(main())
