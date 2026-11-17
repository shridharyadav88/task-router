#!/usr/bin/env python3
"""verify_table.py — done-criterion for routing-table v2026-12 (stdlib only).
Exit 0 = table meets the refresh bar. Exit 1 = list failures.
Usage: python3 scripts/verify_table.py [--table references/routing-table.md]"""
import re
import sys

fails = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + ((" — " + detail) if detail and not cond else ""))
    if not cond:
        fails.append(name)


def main():
    tbl = sys.argv[sys.argv.index("--table") + 1] if "--table" in sys.argv else "references/routing-table.md"
    t = open(tbl).read()
    check("version-header-v2026-12", "v2026-12" in t)
    undated = [m for m in re.finditer(r"UNKNOWN(?!\s*\(?(dated|20\d\d))", t)]
    check("no-undated-UNKNOWN", not undated, "%d bare UNKNOWN" % len(undated))
    check("muse-row", "muse-spark-1.3" in t and "muse " in t.lower())
    check("opencode-row", "opencode" in t and "v2.3.0" in t and "deepseek" in t.lower())
    check("openrouter-row", "elephant-1" in t and "$10" in t)
    check("codex-default-named", "gpt-6-chat-thinking" in t)
    check("claude-measured", "2%" in t and "0%" in t and "160" in t)
    check("cursor-pools", "1%" in t and "Nov 17" in t)
    print("FAILURES: %d" % len(fails) if fails else "ALL CHECKS PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
