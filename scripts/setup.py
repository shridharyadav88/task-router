#!/usr/bin/env python3
"""task-router setup wizard: discover -> guide -> validate -> confirm -> write.

Flows:
  --discover            read-only inventory (binaries, models, quota sources)
  --guided              numbered picker (bundles + per-agent keep/drop), re-ask,
                        verify-in-loop, confirm, write (clobber needs --force)
  --from-answers FILE   non-interactive: validate answers.json against
                        answers.schema.json, verify-in-loop, confirm, write
  --validate-only FILE  check an answers.json without writing anything
  --write               legacy free-text prompts (kept for compatibility)
  --refresh             catalog drift report; never touches rows/chains
  --demo                dry-run route preview on the current table (zero writes)
Exit 0 = ok. Exit 2 = declined / validation failed / would clobber.
Exit 1 = tool error.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TABLE = os.path.join(HERE, "..", "references", "routing-table.json")
SCHEMA = os.path.join(HERE, "answers.schema.json")
AGENTS = ["claude-code", "codex", "cursor-agent", "muse", "opencode"]
BINARIES = {"claude-code": "claude", "codex": "codex",
            "cursor-agent": "cursor-agent", "muse": "muse",
            "opencode": "opencode", "copilot": "copilot"}
CLAUDE_ALIASES = ["fable", "opus", "sonnet", "haiku"]  # haiku verified live 2026-11-17
BUNDLES = {
    "light": ["codex"],
    "standard": ["claude-code", "codex"],
    "power": ["claude-code", "codex", "cursor-agent", "muse", "opencode"],
}


def sh(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "")[:6000]
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "unavailable: %s" % e


def discover():
    bins = {b: shutil.which(exe) for b, exe in BINARIES.items()}
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
            "bundles": BUNDLES,
            "quota_sources": {
                "claude/codex": "numeric fractions the caller passes per run "
                                "(dashboard or probe; UNKNOWN-safe when omitted)",
                "cursor": "user-supplied dashboard fraction (--cursor-frac) "
                          "or --provider-down; UNKNOWN-safe when omitted",
                "muse/opencode": "presence only (--provider-down to mark out)"},
            "table_format": 2}


def validate_answers(a):
    """Returns list of error strings (empty = valid). No writes."""
    errs = []
    if not isinstance(a, dict):
        return ["top level must be an object"]
    if a.get("contract") != "task-router-answers/1":
        errs.append("contract must be 'task-router-answers/1'")
    agents = a.get("agents")
    if not isinstance(agents, list) or not agents:
        errs.append("agents must be a non-empty list")
    else:
        for g in agents:
            if g not in AGENTS:
                errs.append("unknown agent: %r (must be one of %s)" % (g, "/".join(AGENTS)))
    cf = a.get("cursor_frac", None)
    if cf is not None and not (isinstance(cf, (int, float)) and 0 <= cf <= 1):
        errs.append("cursor_frac must be 0..1 or null")
    sp = a.get("spend_ceiling", 2.0)
    if not (isinstance(sp, (int, float)) and sp > 0):
        errs.append("spend_ceiling must be a positive number")
    return errs


def prune_table(base, keep):
    """Flag rows whose harness is not kept as disabled (rows stay for reference
    and re-enabling; chains stay intact so the table always validates)."""
    import copy
    t = copy.deepcopy(base)
    have = {r.get("agent") for r in t["rows"].values()}
    drop_agents = (have - set(keep)) - {"openrouter"}
    for r in t["rows"].values():
        if r.get("agent") in drop_agents:
            r["disabled"] = True
    return t, ""


def verify_table_file(path):
    r = subprocess.run([sys.executable, os.path.join(HERE, "verify_table.py"),
                        "--table", path], capture_output=True, text=True)
    ok = (r.returncode == 0 and "ALL CHECKS PASS" in r.stdout)
    tail = r.stdout.strip().splitlines()
    return ok, (tail[-1] if tail else r.stderr[-300:])


def build_table(base, answers):
    t = json.loads(json.dumps(base))  # deep copy
    t["table_format"] = 2
    t.setdefault("setup", {})
    t["setup"]["agents"] = answers["agents"]
    t["setup"]["bundle"] = answers.get("bundle", "custom")
    t["setup"]["spend_ceiling_usd"] = answers.get("spend_ceiling", 2.0)
    if answers.get("cursor_frac") is not None:
        t["setup"]["cursor_frac_declared"] = answers["cursor_frac"]
    t["setup"]["plan_notes"] = answers.get("plan_notes", "")
    if answers.get("spend_ceiling"):
        t["budget_usd_per_task"] = answers["spend_ceiling"]
    if answers.get("prune_missing", True):
        t, err = prune_table(t, answers["agents"])
        if err:
            return None, err
    return t, ""


def write_with_verify(t, path, force):
    if os.path.isfile(path) and not force:
        return 2, "refusing to clobber %s without --force" % path
    tmp = path + ".tmp-verify"
    with open(tmp, "w") as f:
        json.dump(t, f, indent=1)
    ok, tail = verify_table_file(tmp)
    os.remove(tmp)
    if not ok:
        return 2, "generated table FAILS verify (%s); nothing written" % tail
    with open(path, "w") as f:
        json.dump(t, f, indent=1)
    return 0, "wrote %s (verify green first try)" % path


def pick(prompt, options, default=None, multi=False):
    """Numbered picker. options = [(key, label)]. Returns key(s). `back` supported."""
    while True:
        print(prompt)
        for i, (k, lab) in enumerate(options, 1):
            print("  %d) %s" % (i, lab))
        dflt = " [%s]" % default if default is not None else ""
        try:
            v = input("choose%s (or 'back'): " % dflt).strip()
        except EOFError:
            return None
        if v.lower() == "back":
            return "back"
        if v == "" and default is not None:
            return default
        try:
            if multi:
                idx = [int(x) for x in v.replace(",", " ").split()]
                if all(1 <= i <= len(options) for i in idx) and idx:
                    return [options[i - 1][0] for i in idx]
            else:
                i = int(v)
                if 1 <= i <= len(options):
                    return options[i - 1][0]
        except ValueError:
            pass
        print("not understood %r — enter number(s) like 1,3 or 'back'." % v)


def guided_flow():
    d = discover()
    inst = [b for b in AGENTS if d["binaries"].get(b)]
    print("discovered agents on this machine: %s" % (", ".join(inst) if inst else "none"))
    b = pick("pick a bundle:",
             [("light", "light — cheapest pool only"),
              ("standard", "standard — claude + codex"),
              ("power", "power — all five harnesses")], default="standard")
    if b is None or b == "back":
        return 2, "aborted"
    agents = list(dict.fromkeys(BUNDLES[b] + [g for g in inst if g not in BUNDLES[b]]))
    print("agents in scope: %s" % ", ".join(agents))
    keep = pick("keep all, or tick a subset (e.g. 1,3)?",
                [(g, g) for g in agents] + [("all", "keep all")],
                default="all", multi=True)
    if keep is None or keep == "back":
        return 2, "aborted"
    if keep != "all":
        agents = [k for k in (keep if isinstance(keep, list) else [keep]) if k != "all"]
        if not agents:
            return 2, "empty agent set — nothing to route to"
    cf = None
    if "cursor-agent" in agents:
        while True:
            try:
                v = input("cursor pool fraction 0..1 from dashboard [blank = UNKNOWN-safe]: ").strip()
            except EOFError:
                return 2, "aborted"
            if v == "":
                break
            try:
                cf = float(v)
                if 0 <= cf <= 1:
                    break
            except ValueError:
                pass
            print("must be 0..1 or blank — try again.")
    try:
        spend = input("per-task spend ceiling USD [2.0]: ").strip() or "2.0"
        spend = float(spend)
        if spend <= 0:
            raise ValueError
    except (ValueError, EOFError):
        return 2, "spend ceiling must be a positive number"
    try:
        notes = input("plan notes [blank]: ").strip()
    except EOFError:
        notes = ""
    return {"contract": "task-router-answers/1", "agents": agents, "bundle": b,
            "cursor_frac": cf, "spend_ceiling": spend, "plan_notes": notes,
            "prune_missing": True}, ""


def main():
    p = argparse.ArgumentParser(description="task-router setup wizard")
    p.add_argument("--discover", action="store_true")
    p.add_argument("--guided", action="store_true")
    p.add_argument("--from-answers", default="")
    p.add_argument("--validate-only", default="")
    p.add_argument("--write", action="store_true")
    p.add_argument("--refresh", action="store_true")
    p.add_argument("--demo", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--table", default=DEFAULT_TABLE)
    a = p.parse_args()
    if sum([bool(a.discover), bool(a.guided), bool(a.from_answers),
            bool(a.validate_only), bool(a.write), bool(a.refresh),
            bool(a.demo)]) != 1:
        print("choose exactly one of --discover/--guided/--from-answers/"
              "--validate-only/--write/--refresh/--demo")
        return 2
    if a.discover:
        d = discover()
        print(json.dumps(d, indent=1))
        return 0
    if a.validate_only:
        try:
            ans = json.load(open(a.validate_only))
        except (OSError, ValueError) as e:
            print("unreadable answers file: %s" % e)
            return 2
        errs = validate_answers(ans)
        if errs:
            print("INVALID:")
            for e in errs:
                print("  - %s" % e)
            return 2
        print("answers OK (contract %s, agents %s)" % (ans["contract"], ans["agents"]))
        return 0
    if a.demo:
        spec = "/tmp/task-router-demo-spec.txt"
        with open(spec, "w") as f:
            f.write("add dark mode toggle\nDone = relevant tests pass.\n")
        r = subprocess.run([sys.executable, os.path.join(HERE, "route.py"),
                            "--spec", spec, "--size", "S",
                            "--claude-wk", "1", "--claude-h5", "1",
                            "--codex-wk", "1", "--codex-h5", "1",
                            "--log", "/tmp/task-router-demo-audit.jsonl"],
                           capture_output=True, text=True)
        try:
            d = json.loads(r.stdout)
            pk = d.get("pick", {})
            print("demo route: %s via %s (%s/%s) — %s" %
                  (pk.get("row"), pk.get("agent"), pk.get("model"),
                   pk.get("effort"), pk.get("cmd", "")))
            print("zero writes, zero quota spent (frozen full-quota demo).")
            return 0
        except ValueError:
            print("demo failed: %s" % r.stderr[-300:])
            return 1
    if a.refresh:
        try:
            with open(a.table) as f:
                current = json.load(f)
        except (OSError, ValueError) as e:
            print("cannot read table %s: %s" % (a.table, e))
            return 1
        d = discover()
        known = {m if isinstance(m, str) else m.get("slug")
                 for m in current.get("codex_models", {}).get("slugs", [])}
        fresh = {m["slug"] for m in d["codex_models"]} - known
        print("new codex slugs not in table: %s" % sorted(fresh))
        print("cursor slugs discovered: %d (catalogue only; new rows need the "
              "new-row gate, never auto-added)" % len(d["cursor_models"]))
        print("rows/chains untouched: refresh preserves hand edits by design.")
        return 0
    if a.write:
        return legacy_write(a)
    # --guided / --from-answers share validation + verify-in-loop + confirm.
    # A missing target table means first setup: template from the shipped table.
    template = a.table if os.path.isfile(a.table) else DEFAULT_TABLE
    if template != a.table:
        print("no table at %s yet — templating from the shipped table." % a.table)
    try:
        with open(template) as f:
            base = json.load(f)
    except (OSError, ValueError) as e:
        print("cannot read table %s: %s" % (template, e))
        return 1
    if a.from_answers:
        try:
            ans = json.load(open(a.from_answers))
        except (OSError, ValueError) as e:
            print("unreadable answers file: %s" % e)
            return 2
        errs = validate_answers(ans)
        if errs:
            print("answers INVALID, nothing written:")
            for e in errs:
                print("  - %s" % e)
            return 2
        answers = ans
    else:
        out = guided_flow()
        if isinstance(out, tuple) and out[0] in (0, 1, 2) and isinstance(out[1], str) and "aborted" in out[1]:
            print(out[1] + "; nothing written.")
            return out[0]
        answers, _ = out
    t, err = build_table(base, answers)
    if err:
        print("cannot build table: %s" % err)
        return 2
    print("ready to write %s for agents %s (spend ceiling %s)." %
          (a.table, answers["agents"], answers.get("spend_ceiling")))
    if not a.force:
        try:
            ok = input("write it? (yes/no) [no]: ").strip().lower()
        except EOFError:
            ok = "no"
        if ok not in ("yes", "y"):
            print("declined; nothing written.")
            return 2
        if os.path.isfile(a.table):
            print("refusing to clobber %s without --force." % a.table)
            return 2
    rc, msg = write_with_verify(t, a.table, True)
    print(msg)
    return rc


def build_table(base, answers):
    t = json.loads(json.dumps(base))  # deep copy
    t["table_format"] = 2
    t.setdefault("setup", {})
    t["setup"]["agents"] = answers["agents"]
    t["setup"]["bundle"] = answers.get("bundle", "custom")
    t["setup"]["spend_ceiling_usd"] = answers.get("spend_ceiling", 2.0)
    if answers.get("cursor_frac") is not None:
        t["setup"]["cursor_frac_declared"] = answers["cursor_frac"]
    t["setup"]["plan_notes"] = answers.get("plan_notes", "")
    if answers.get("spend_ceiling"):
        t["budget_usd_per_task"] = answers["spend_ceiling"]
    if answers.get("prune_missing", True):
        t, err = prune_table(t, answers["agents"])
        if err:
            return None, err
    return t, ""


def legacy_write(a):
    try:
        with open(a.table) as f:
            base = json.load(f)
    except (OSError, ValueError) as e:
        print("cannot read table %s: %s" % (a.table, e))
        return 1
    if os.path.isfile(a.table) and not a.force:
        print("refusing to clobber existing table without --force.")
        return 2
    try:
        spend = float(input("per-task spend ceiling USD [2.0]: ").strip() or "2.0")
        cfrac = input("cursor pool fraction 0..1 [blank = UNKNOWN-safe]: ").strip()
        cfrac = float(cfrac) if cfrac else None
        notes = input("plan notes [blank]: ").strip()
        ok = input("write? (yes/no) [no]: ").strip().lower()
    except (EOFError, ValueError):
        print("aborted (numbers must be numeric).")
        return 2
    if ok not in ("yes", "y"):
        print("declined; nothing written.")
        return 2
    if os.path.isfile(a.table) and not a.force:
        print("refusing to clobber existing table without --force.")
        return 2
    t = build_table(base, {"agents": ["claude-code", "codex", "cursor-agent",
                                      "muse", "opencode"],
                           "bundle": "legacy", "cursor_frac": cfrac,
                           "spend_ceiling": spend, "plan_notes": notes,
                           "prune_missing": False})
    rc, msg = write_with_verify(t[0], a.table, True)
    print(msg)
    return rc


if __name__ == "__main__":
    sys.exit(main())
