#!/usr/bin/env python3
"""setup.py — setup wizard with auto-discovery for the task-router table.

Read-only discovery first, questions only for what cannot be discovered,
writes only with explicit confirmation. Never edits code.
Usage:
  python3 scripts/setup.py --discover [--json]
      Print discovered agents, models, and quota sources. No writes, no quota cost.
  python3 scripts/setup.py --write [--force] [--table PATH]
      Interactive: asks ONLY plan caps + spend ceiling + confirm, then writes a
      routing-table.json (table_format 2). Refuses to clobber without --force.
  python3 scripts/setup.py --refresh [--force] [--table PATH]
      Re-discovers, updates model catalogs, reports drift (new slugs never become
      rows automatically), preserves hand-edited rows/chains. Writes need --force.
Exit 0 = ok. Exit 2 = user declined / would clobber. Exit 1 = tool error.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TABLE = os.path.join(HERE, "..", "references", "routing-table.json")
BINARIES = ["claude", "codex", "cursor-agent", "muse", "opencode", "copilot"]
CLAUDE_ALIASES = ["fable", "opus", "sonnet", "haiku"]  # haiku verified live 2026-11-17


def sh(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "")[:6000]
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "unavailable: %s" % e


def discover():
    bins = {b: shutil.which(b) for b in BINARIES}
    cursor_models, codex_models = [], []
    if bins["cursor-agent"]:
        rc, out = sh([bins["cursor-agent"], "--list-models"])
        if rc == 0:
            for ln in out.splitlines():
                ln = ln.strip()
                if ln and not ln.startswith(("Available", "auto ")):
                    slug = ln.split()[0]
                    if slug != "auto":
                        cursor_models.append(slug)
    cache = os.path.expanduser("~/.codex/models_cache.json")
    if bins["codex"] and os.path.isfile(cache):
        try:
            d = json.load(open(cache))
            for m in d.get("models", []):
                lv = [l.get("effort") for l in m.get("supported_reasoning_levels", [])]
                codex_models.append({"slug": m.get("slug"),
                                     "default": m.get("default_reasoning_level"),
                                     "levels": lv})
        except (OSError, ValueError):
            pass
    return {"binaries": bins,
            "cursor_models": sorted(set(cursor_models)),
            "codex_models": codex_models,
            "claude_aliases": CLAUDE_ALIASES,
            "quota_sources": {
                "claude/codex": "numeric fractions the caller passes per run "
                                "(dashboard or probe; UNKNOWN-safe when omitted)",
                "cursor": "user-supplied dashboard fraction (--cursor-frac) "
                          "or --provider-down; UNKNOWN-safe when omitted",
                "muse/opencode": "presence only (--provider-down to mark out)"},
            "table_format": 2}


def build_table(base, answers):
    t = json.loads(json.dumps(base))  # deep copy
    t["table_format"] = 2
    t.setdefault("setup", {})
    t["setup"]["spend_ceiling_usd"] = answers.get("spend_ceiling", 2.0)
    if answers.get("cursor_frac") is not None:
        t["setup"]["cursor_frac_declared"] = answers["cursor_frac"]
    t["setup"]["plan_notes"] = answers.get("plan_notes", "")
    if "budget_usd_per_task" in t and answers.get("spend_ceiling"):
        t["budget_usd_per_task"] = answers["spend_ceiling"]
    return t


def ask(prompt, default=None):
    suf = " [%s]" % default if default is not None else ""
    try:
        v = input(prompt + suf + ": ").strip()
    except EOFError:
        return default
    return v if v != "" else default


def main():
    p = argparse.ArgumentParser(description="task-router setup wizard")
    p.add_argument("--discover", action="store_true")
    p.add_argument("--write", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--json", action="store_true")
    p.add_argument("--table", default=DEFAULT_TABLE)
    a = p.parse_args()
    if sum([a.discover, a.write, a.refresh]) != 1:
        print("choose exactly one of --discover, --write, --refresh")
        return 2
    if a.discover:
        d = discover()
        print(json.dumps(d, indent=1) if a.json else
              "\n".join("binary %-14s %s" % (k, v or "MISSING")
                        for k, v in d["binaries"].items()) +
              "\ncursor slugs: %d (%s...)" % (len(d["cursor_models"]),
                                                ", ".join(d["cursor_models"][:5])) +
              "\ncodex slugs: %s" % ", ".join(m["slug"] for m in d["codex_models"]) +
              "\nclaude aliases: %s" % ", ".join(d["claude_aliases"]))
        return 0
    try:
        with open(a.table) as f:
            current = json.load(f)
    except (OSError, ValueError) as e:
        print("cannot read table %s: %s" % (a.table, e))
        return 1
    if a.refresh:
        d = discover()
        known = {m if isinstance(m, str) else m.get("slug")
                 for m in current.get("codex_models", {}).get("slugs", [])}
        fresh = {m["slug"] for m in d["codex_models"]}
        print("new codex slugs not in table: %s" % sorted(fresh - known))
        print("cursor slugs discovered: %d (catalogue only; new rows need the "
              "new-row gate, never auto-added)" % len(d["cursor_models"]))
        print("rows/chains untouched: refresh preserves hand edits by design.")
        return 0
    # --write: ask only what discovery cannot know
    print("setup will write %s (table_format 2)." % a.table)
    if os.path.isfile(a.table) and not a.force:
        print("refusing to clobber existing table without --force.")
        return 2
    spend = ask("per-task spend ceiling USD", "2.0")
    cfrac = ask("cursor pool fraction 0..1 from dashboard (blank = UNKNOWN-safe)", "")
    notes = ask("plan notes (e.g. claude pro + cursor X-sub)", "")
    try:
        spend_f = float(spend)
        cfrac_f = float(cfrac) if cfrac != "" else None
    except ValueError:
        print("numbers only for spend/fraction.")
        return 2
    ok = ask("write table with spend=%.2f cursor_frac=%s? (yes/no)" %
             (spend_f, cfrac_f), "no")
    if (ok or "").lower() not in ("yes", "y"):
        print("declined; nothing written.")
        return 2
    if os.path.isfile(a.table) and not a.force:
        print("refusing to clobber existing table without --force.")
        return 2
    t = build_table(current, {"spend_ceiling": spend_f,
                              "cursor_frac": cfrac_f, "plan_notes": notes})
    with open(a.table, "w") as f:
        json.dump(t, f, indent=1)
    print("wrote %s (spend ceiling %.2f)." % (a.table, spend_f))
    return 0


if __name__ == "__main__":
    sys.exit(main())
