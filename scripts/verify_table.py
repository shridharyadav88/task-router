#!/usr/bin/env python3
"""verify_table.py — done-criterion for routing-table.json (stdlib only).
Exit 0 = table meets the bar. Exit 1 = list failures.
Usage: python3 scripts/verify_table.py [--table references/routing-table.json]
Run with workdir = the skill directory.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TABLE = os.path.join(HERE, "..", "references", "routing-table.json")
GOLDEN = os.path.join(HERE, "..", "references", "golden-set.json")
fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name +
          ((" — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def run_route(table, args):
    cmd = [sys.executable, os.path.join(HERE, "route.py"), "--table", table,
           "--log", "/tmp/verify-audit.jsonl"] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return {"action": "error", "stderr": r.stderr[-200:]}


def main():
    tbl = (sys.argv[sys.argv.index("--table") + 1] if "--table" in sys.argv
           else DEFAULT_TABLE)
    try:
        with open(tbl) as f:
            t = json.load(f)
    except (OSError, ValueError) as e:
        print("FAIL table-load — %s" % e)
        return 1
    check("version-present", bool(t.get("table_v")), "no table_v")
    bars = t.get("bars", {})
    check("bars-four-sizes",
          all(k in bars and isinstance(bars[k], (int, float))
              for k in ("S", "M", "L", "XL")), str(sorted(bars)))
    rows = t.get("rows", {})
    for rid in ("R1", "R2", "R3", "R4", "R5", "CURSOR", "R6"):
        r = rows.get(rid) or {}
        check("row-%s" % rid,
              all(k in r for k in ("agent", "model", "pool")), rid)
    check("muse-row", (rows.get("R4") or {}).get("model") == "muse-spark-1.3")
    r5 = rows.get("R5") or {}
    check("opencode-row", "deepseek" in (r5.get("model") or ""),
          str(r5.get("model")))
    r6 = rows.get("R6") or {}
    check("openrouter-row-nonworker",
          r6.get("worker") is False and "elephant-1" in (r6.get("model") or ""))
    check("point-cap", t.get("point_cap_usd") == 10.0)
    check("codex-default-named",
          "gpt-6-chat-thinking" in (rows.get("R3") or {}).get("label", ""))
    chains = t.get("chains", {})
    check("chains-four-sizes", set(chains) == {"S", "M", "L", "XL"})
    for sz, ch in chains.items():
        check("chain-%s-valid" % sz,
              bool(ch) and all(rid in rows for rid in ch), str(ch))
    check("chain-S-opens-R3", (chains.get("S") or [None])[0] == "R3")
    check("chain-M-opens-R3", (chains.get("M") or [None])[0] == "R3")
    check("chain-L-opens-R2", (chains.get("L") or [None])[0] == "R2")
    check("chain-XL-top-only", chains.get("XL") == ["R1", "R2"])
    eff = t.get("effort", {})
    check("effort-SM-opencode-model",
          eff.get("S", {}).get("opencode") == r5.get("model") and
          eff.get("M", {}).get("opencode") == r5.get("model"))
    check("effort-LX-opencode-null",
          eff.get("L", {}).get("opencode") is None and
          eff.get("XL", {}).get("opencode") is None)
    q = t.get("quota", {})
    check("quota-thresholds",
          q.get("reserve_below") == 0.2 and q.get("low_below") == 0.5)
    tm = t.get("timeouts_min", {})
    check("timeouts", all(s in tm for s in ("S", "M", "L", "XL")))
    check("spread-rule", (t.get("spread_after") or 0) >= 2)
    # live smoke: full quota S -> R3; claude RESERVE XL -> defer
    with open("/tmp/verify-spec.txt", "w") as f:
        f.write("add dark mode toggle\nDone = relevant tests pass.\n")
    base = ["--spec", "/tmp/verify-spec.txt", "--claude-wk", "1",
            "--claude-h5", "1", "--codex-wk", "1", "--codex-h5", "1"]
    s = run_route(tbl, base + ["--size", "S"])
    check("smoke-S-picks-R3",
          (s.get("pick") or {}).get("row") == "R3", str(s)[:150])
    check("smoke-candidates-ranked",
          isinstance(s.get("candidates"), list) and len(s.get("candidates", [])) >= 2)
    x = run_route(tbl, base[:-4] + ["--claude-wk", "0.01", "--claude-h5", "0.01",
                                   "--size", "XL"])
    check("smoke-XL-reserve-defers", x.get("action") == "defer", str(x)[:150])
    try:
        g = json.load(open(GOLDEN))
        tasks = g["tasks"] if isinstance(g, dict) else g
        ids = [x["id"] for x in tasks]
        check("golden-30-unique", len(tasks) == 30 and len(set(ids)) == 30,
              "%d tasks" % len(tasks))
    except (OSError, ValueError, KeyError) as e:
        check("golden-30-unique", False, str(e)[:100])
    # no hardcoded rows left in route.py logic
    src = open(os.path.join(HERE, "route.py")).read()
    check("no-hardcoded-INDEX", "INDEX = {" not in src)
    check("no-hardcoded-CHAINS", "CHAINS = {" not in src)
    check("no-hardcoded-EFFORT", "EFFORT = {" not in src)
    print("FAILURES: %d (%s)" % (len(fails), ", ".join(fails)) if fails
          else "ALL CHECKS PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
