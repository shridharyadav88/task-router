#!/usr/bin/env python3
"""task-router v1 executor: zero-model-cost orchestrator (stdlib only).

Runs the references/executor.md pipeline: intake -> red-on-base x2 -> snapshot
-> ONE worker one-shot -> deterministic verify -> regex triage -> single
escalation from base -> human packet. Exit 0 = pass, 2 = clarify/defer/reject/
human (machine-readable JSON on stdout), 1 = tool error.
--dry-run exercises real gates without launching any CLI (no quota).
--self-test builds a fixture repo and proves 4 scenarios (no quota).
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROUTE_PY = os.path.join(HERE, "route.py")
TABLE_JSON = os.path.join(HERE, "..", "references", "routing-table.json")


def _table_timeouts():
    try:
        with open(TABLE_JSON) as f:
            return json.load(f).get("timeouts_min", {})
    except (OSError, ValueError):
        return {}


TIMEOUT_MIN = _table_timeouts() or {"S": 10, "M": 20, "L": 40, "XL": 90}
TURNS = {"S": 5, "M": 10, "L": 15, "XL": 20}
DIFF_CAP = {"S": (150, 5), "M": (400, 12), "L": (1000, 25), "XL": (10 ** 9, 10 ** 9)}
EST_BURN = {"S": 0.10, "M": 0.30, "L": 0.80, "XL": 1.50}
NEXT = {"S": "M", "M": "L", "L": "XL", "XL": "XL"}
TRANSIENT_RE = re.compile(r"429|rate.?limit|timed?\s?out|ETIMEDOUT|ECONNRESET|EAI_AGAIN|socket hang|OOM|out of memory|exit (code )?137|killed", re.I)
DEFAULT_PROTECTED = ["pytest.ini", "pyproject.toml", "setup.cfg", "package.json",
                     "conftest.py", "tests", "__tests__", ".github/workflows"]


def run(cmd, cwd, timeout):
    p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         text=True, start_new_session=True)
    try:
        out, err = p.communicate(timeout=timeout)
        return p.returncode, out, err, False
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        out, err = p.communicate()
        return 124, out, err, True


def sha_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(65536), b""):
            h.update(b)
    return h.hexdigest()[:16]


def snapshot(repo, patterns):
    snap = {}
    for pat in patterns:
        p = os.path.join(repo, pat)
        if os.path.isfile(p):
            snap[pat] = sha_file(p)
        elif os.path.isdir(p):
            for root, _, files in os.walk(p):
                for fn in sorted(files):
                    fp = os.path.join(root, fn)
                    snap[os.path.relpath(fp, repo)] = sha_file(fp)
    return snap


def diff_stat(repo):
    rc, out, _, _ = run(["git", "diff", "--numstat", "HEAD", "--", "."], repo, 60)
    lines, files = 0, 0
    if rc == 0 and out.strip():
        for ln in out.strip().splitlines():
            parts = ln.split()
            if len(parts) >= 2:
                try:
                    lines += int(parts[0]) + int(parts[1])
                except ValueError:
                    lines += 0
                files += 1
    return lines, files


def collect_count(repo, collect_cmd):
    if not collect_cmd:
        return None
    import shlex
    rc, out, _, _ = run(shlex.split(collect_cmd), repo, 120)
    m = re.findall(r"(\d+) (tests?|items?) collected", out)
    if m:
        return int(m[-1][0])
    m2 = re.findall(r"^(\d+)", out.strip().splitlines()[-1] if out.strip() else "")
    return int(m2[0]) if m2 else None


def worker_cmd(pick, prompt, budget_left, timeout_s, codex_sandbox):
    ag, model, effort = pick["agent"], pick["model"], pick["effort"]
    if ag == "claude-code":
        return (["claude", "--model", model, "--effort", effort, "-p", prompt,
                 "--max-turns", str(TURNS.get("_", 10)), "--max-budget-usd",
                 str(round(budget_left, 2)), "--output-format", "json"], timeout_s, "claude")
    if ag == "codex":
        eff = {"low": "low", "medium": "medium", "high": "high", "max": "xhigh"}[effort]
        return (["codex", "exec", "-m", model, "--sandbox", codex_sandbox, "--json",
                 "-c", 'model_reasoning_effort="%s"' % eff, prompt], timeout_s, "codex")
    if ag == "muse":
        return (["muse", "exec", prompt], timeout_s, "muse")
    if ag == "opencode":
        return (["opencode", "run", prompt, "--model", model], timeout_s, "opencode")
    return (["cursor-agent", "--model", model, "-p", prompt], timeout_s, "cursor")


def parse_usage(kind, stdout):
    try:
        if kind == "claude":
            d = json.loads(stdout)
            return {"usd": d.get("total_cost_usd"), "turns": d.get("num_turns")}
        if kind == "codex":
            toks = 0
            for ln in stdout.splitlines():
                try:
                    d = json.loads(ln)
                except ValueError:
                    continue
                u = d.get("usage") or {}
                toks += (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
            return {"tokens": toks or None}
    except ValueError:
        pass
    return {}


def verify(repo, a, snap, base_count):
    """Returns (ok, reasons[]). All deterministic, no model."""
    reasons = []
    import shlex
    rc, out, err, _ = run(shlex.split(a.criterion), repo, TIMEOUT_MIN[a.size] * 60)
    tail = (out + err)[-2000:]
    if rc != 0:
        return False, ["criterion_failed rc=%d" % rc], tail
    if snapshot(repo, a.protected) != snap:
        return False, ["protected_paths_changed"], tail
    if base_count is not None:
        now = collect_count(repo, a.collect_cmd)
        if now is None or now < base_count:
            return False, ["count_floor %s < %s" % (now, base_count)], tail
    lines, files = diff_stat(repo)
    cap_l, cap_f = DIFF_CAP[a.size]
    if lines > cap_l or files > cap_f:
        return False, ["diff_cap %d lines/%d files" % (lines, files)], tail
    if a.lint_cmd:
        rc2, _, _, _ = run(shlex.split(a.lint_cmd), repo, 300)
        if rc2 != 0:
            return False, ["lint_failed"], tail
    return True, [], tail


def digest_file(path, spec_sha, fail_ids, tail):
    body = ("SPEC: %s sha=%s\nFAILING: %s\n--- tail40 ---\n%s" %
            (path, spec_sha, fail_ids, "\n".join(tail.splitlines()[-40:])))
    return body[:4096]


def main():
    p = argparse.ArgumentParser(description="task-router v1 executor")
    p.add_argument("--spec", required=True)
    p.add_argument("--size", required=True, choices=["S", "M", "L", "XL"])
    p.add_argument("--criterion", default="", help="test command, e.g. 'pytest -q tests/x.py'")
    p.add_argument("--repo", default=".")
    p.add_argument("--variant", default="red", choices=["red", "preserve"])
    p.add_argument("--collect-cmd", default="")
    p.add_argument("--lint-cmd", default="")
    p.add_argument("--protected", default=",".join(DEFAULT_PROTECTED))
    p.add_argument("--budget", type=float, default=2.0)
    p.add_argument("--codex-sandbox", default="workspace-write",
                   help="codex sandbox; use danger-full-access in gateway/service contexts")
    p.add_argument("--timeout-min", type=float, default=0)
    p.add_argument("--log", default=os.path.expanduser("~/.local/state/task-router/decisions.jsonl"))
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--dry-worker", default="pass", choices=["pass", "fail", "tamper", "bigdiff"])
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--self-agent", default="")
    p.add_argument("--no-codex-ok", action="store_true")
    p.add_argument("--cursor-model", default="")
    a = p.parse_args()
    a.protected = [s for s in a.protected.split(",") if s]
    if a.self_test:
        return self_test()
    if not a.criterion:
        print(json.dumps({"action": "recommend_only",
                          "why": "no executable criterion: stays v0"}, indent=2))
        return 2
    with open(a.spec, errors="replace") as f:
        spec = f.read()
    if len(spec) > 48000:
        print(json.dumps({"action": "spec_too_long"}, indent=2))
        return 2
    spec_sha = hashlib.sha256(spec.encode()).hexdigest()[:16]
    repo = os.path.abspath(a.repo)
    if run(["git", "rev-parse", "--show-toplevel"], repo, 30)[0] != 0:
        print(json.dumps({"action": "recommend_only", "why": "not a git repo"}, indent=2))
        return 2
    # pick via v0 lookup
    rcmd = [sys.executable, ROUTE_PY, "--spec", a.spec, "--size", a.size,
            "--log", a.log]
    if a.self_agent:
        rcmd += ["--self-agent", a.self_agent]
    if a.no_codex_ok:
        rcmd += ["--no-codex-ok"]
    if a.cursor_model:
        rcmd += ["--cursor-model", a.cursor_model]
    r = subprocess.run(rcmd, capture_output=True, text=True)
    try:
        pick_out = json.loads(r.stdout)
    except ValueError:
        print(json.dumps({"action": "error", "why": "router failed", "stderr": r.stderr[-500:]}))
        return 1
    if "pick" not in pick_out:
        print(json.dumps(pick_out, indent=2))
        return 2
    pick, size = pick_out["pick"], a.size
    # ranked fallback: first same-size fallback row (different provider) gets
    # attempt 2 from base; size-up escalation gets attempt 3 at most.
    fb = next((c for c in pick_out.get("candidates", [])
               if c.get("status") == "fallback"
               and c.get("agent") != pick["agent"]), None)
    fb_pick = ({"agent": fb["agent"], "model": fb["model"],
                "effort": fb["effort"], "row": fb["row"]} if fb else None)
    sized_up = False
    spent, attempts = 0.0, []
    wt_base = tempfile.mkdtemp(prefix="trex-base-")
    try:
        if run(["git", "worktree", "add", "--detach", wt_base, "HEAD"], repo, 120)[0] != 0:
            print(json.dumps({"action": "error", "why": "worktree failed"}))
            return 1
        # red-on-base x2 (real criterion, free)
        import shlex
        reds = []
        for _ in range(2):
            rc, _, _, _ = run(shlex.split(a.criterion), wt_base, 600)
            reds.append(rc)
        if a.variant == "red" and all(r == 0 for r in reds):
            return reject("criterion_green_on_base", spec_sha, a, spent, attempts)
        if a.variant == "preserve" and not all(r == 0 for r in reds):
            return reject("preserve_variant_base_not_green", spec_sha, a, spent, attempts)
        snap = snapshot(wt_base, a.protected)
        base_count = collect_count(wt_base, a.collect_cmd)
        # attempt loop (max 3 launches incl transient)
        cur_size, cur_pick = size, pick
        last_why, last_tail = [], ""
        for n in (1, 2, 3):
            if n > 1:
                # attempts 2+ restart from base; failure arrives only as a 4KB digest
                run(["git", "reset", "--hard", "HEAD"], wt_base, 120)
                run(["git", "clean", "-fd"], wt_base, 120)
                with open(os.path.join(wt_base, "DIGEST.md"), "w") as f:
                    f.write(digest_file(a.spec, spec_sha, last_why, last_tail))
            if a.dry_run:
                ok, why = dry_attempt(wt_base, a, snap, base_count, cur_size)
                usage, kind, tail = {}, "dry", ""
            else:
                ok, why, usage, kind, tail = live_attempt(wt_base, a, snap, base_count, cur_pick,
                                                         spec, a.budget - spent)
            last_why, last_tail = why, tail
            spent += usage.get("usd") or EST_BURN[cur_size]
            attempts.append({"n": n, "size": cur_size, "pick": cur_pick,
                             "ok": ok, "why": why, "usage": usage})
            if ok:
                return done(True, spec_sha, a, spent, attempts, None)
            if any(w.startswith("flaky") for w in why):
                return done(False, spec_sha, a, spent, attempts, "human")
            if spent >= a.budget:
                return done(False, spec_sha, a, spent, attempts, "budget_ceiling")
            if n == 1 and fb_pick is not None:
                cur_size, cur_pick = size, fb_pick
                fb_pick = None
                continue
            if n == 3 or sized_up:
                break
            cur_size, cur_pick = escalate(a, cur_size, cur_pick, spent, spec_sha)
            if cur_pick is None:
                return done(False, spec_sha, a, spent, attempts, "no_escalation_row")
            sized_up = True
        return done(False, spec_sha, a, spent, attempts, "human")
    finally:
        run(["git", "worktree", "remove", "--force", wt_base], repo, 120)


def escalate(a, size, pick, spent, spec_sha):
    ns = NEXT[size]
    if spent + EST_BURN[ns] > a.budget:
        return ns, None
    rcmd = [sys.executable, ROUTE_PY, "--spec", a.spec, "--size", ns, "--log", a.log]
    if a.no_codex_ok:
        rcmd += ["--no-codex-ok"]
    # force a different provider or +1 size: drop current agent via self-agent trick is
    # unnecessary; +1 size already changes the row. Same-agent different-size is allowed.
    r = subprocess.run(rcmd, capture_output=True, text=True)
    try:
        d = json.loads(r.stdout)
        if "pick" not in d:
            return ns, None
        return ns, d["pick"]
    except ValueError:
        return ns, None


def live_attempt(wt, a, snap, base_count, pick, spec, budget_left):
    pkt = ("Follow PACKET.md in this worktree exactly. If DIGEST.md exists, read it first: "
           "it is the previous attempt's failure, start from this base tree, do not repeat it. "
           "Rules: implement only the spec; "
           "NEVER edit tests/test config/lint config; keep the diff within %s-size limits; "
           "finish by running the criterion quietly (truncate output to ~2KB).\n" % a.size)
    with open(os.path.join(wt, "PACKET.md"), "w") as f:
        f.write(pkt + "\n--- SPEC ---\n" + spec)
    prompt = ("Follow PACKET.md in this worktree exactly. "
              "If DIGEST.md exists, read it first as the previous attempt's failure.")
    cmd, timeout_s, kind = worker_cmd(pick, prompt,
                                      budget_left, int((a.timeout_min or TIMEOUT_MIN[a.size]) * 60),
                                      a.codex_sandbox)
    import shlex
    rc, out, err, timed = run(cmd, wt, timeout_s)
    usage = parse_usage(kind, out)
    try:
        os.remove(os.path.join(wt, "PACKET.md"))
    except OSError:
        pass
    if timed:
        return False, ["timeout"], usage, kind, err[-2000:]
    ok, why, tail = verify(wt, a, snap, base_count)
    if ok:
        return True, [], usage, kind, ""
    # deterministic triage (no LLM)
    if TRANSIENT_RE.search(err + out):
        return False, ["transient:" + (why[0] if why else "worker_error")], usage, kind, tail
    rc2, _, _, _ = run(shlex.split(a.criterion), wt, 600)
    if rc2 == 0:
        return False, ["flaky:passes_on_rerun"], usage, kind, tail
    return False, ["criterion_failed"], usage, kind, tail


def dry_attempt(wt, a, snap, base_count, size):
    if a.dry_worker == "pass":
        return True, []
    if a.dry_worker == "tamper":
        tp = os.path.join(wt, "conftest.py")
        with open(tp, "w") as f:
            f.write("# worker touched this\n")
        ok, why, _ = verify_snap_only(wt, a, snap, base_count)
        os.remove(tp)
        return (False, ["gate_caught_tamper"] if not ok else ["GATE_MISS"])
    if a.dry_worker == "bigdiff":
        os.makedirs(os.path.join(wt, "junk"), exist_ok=True)
        for i in range(10):
            open(os.path.join(wt, "junk", "f%d.txt" % i), "w").write("x" * 1000)
        lines, files = diff_stat_untracked(wt)
        shutil.rmtree(os.path.join(wt, "junk"))
        cap_l, cap_f = DIFF_CAP[size]
        if files > cap_f:
            return False, ["gate_caught_bigdiff"]
        return False, ["GATE_MISS"]
    return False, ["criterion_failed rc=1"]


def verify_snap_only(wt, a, snap, base_count):
    if snapshot(wt, a.protected) != snap:
        return False, ["protected_paths_changed"], ""
    return True, [], ""


def diff_stat_untracked(wt):
    n = 0
    for root, _, files in os.walk(os.path.join(wt, "junk")):
        n += len(files)
    return n * 100, n


def reject(why, spec_sha, a, spent, attempts):
    out = {"action": "reject", "why": why, "spec_sha256": spec_sha,
           "spent_usd_est": round(spent, 2)}
    print(json.dumps(out, indent=2))
    audit(a, {"spec_sha256": spec_sha, "action": "reject", "why": why, "attempts": attempts})
    return 2


def done(ok, spec_sha, a, spent, attempts, route):
    toks = sum((x.get("usage", {}) or {}).get("tokens", 0) or 0 for x in attempts)
    est = any("usd" not in (x.get("usage", {}) or {}) for x in attempts)
    out = {"action": "pass" if ok else route, "spec_sha256": spec_sha,
           "spent_usd": round(spent, 2), "usd_estimated": est,
           "spent_tokens": toks, "budget": a.budget, "attempts": attempts}
    print(json.dumps(out, indent=2))
    audit(a, {"spec_sha256": spec_sha, "action": out["action"], "spent_usd": round(spent, 2),
              "attempts": attempts})
    return 0 if ok else 2


def audit(a, obj):
    try:
        d = os.path.dirname(a.log)
        if d:
            os.makedirs(d, exist_ok=True)
        obj = dict(obj, ts=int(time.time()), router_v="1", kind="exec")
        with open(a.log, "a") as f:
            f.write(json.dumps(obj) + "\n")
    except OSError as e:
        print("audit append failed: %s" % e, file=sys.stderr)


def self_test():
    """4 scenarios on a fixture git repo. No quota. Exit 0 iff all behave."""
    base = tempfile.mkdtemp(prefix="trex-selftest-")
    repo = os.path.join(base, "r")
    os.makedirs(repo)
    run(["git", "init", "-q"], repo, 30)
    run(["git", "config", "user.email", "t@t"], repo, 30)
    with open(os.path.join(repo, "conftest.py"), "w") as f:
        f.write("GUARD=1\n")
    with open(os.path.join(repo, "check.sh"), "w") as f:
        f.write("#!/bin/sh\ntest -f done.txt\n")
    os.chmod(os.path.join(repo, "check.sh"), 0o755)
    run(["git", "add", "."], repo, 30)
    run(["git", "commit", "-qm", "base"], repo, 30)
    results = {}

    class A:
        criterion = "./check.sh"
        collect_cmd = ""
        lint_cmd = ""
        protected = ["conftest.py"]
        size = "S"
    wt = tempfile.mkdtemp(prefix="trex-st-")
    run(["git", "worktree", "add", "--detach", wt, "HEAD"], repo, 60)
    try:
        import shlex
        # 1 green-on-base must REJECT
        rc, _, _, _ = run(shlex.split("./check.sh"), wt, 30) if False else (1, "", "", False)
        open(os.path.join(wt, "done.txt"), "w").write("x")
        rc, _, _, _ = run(["./check.sh"], wt, 30)
        results["green_base_detected"] = (rc == 0)
        os.remove(os.path.join(wt, "done.txt"))
        # 2 pass-path accepts
        snap = snapshot(wt, ["conftest.py"])
        open(os.path.join(wt, "done.txt"), "w").write("x")
        ok, _, _ = verify(wt, A(), snap, None)
        results["pass_accepted"] = ok
        # 3 tamper rejected
        with open(os.path.join(wt, "conftest.py"), "a") as f:
            f.write("# evil\n")
        ok, why, _ = verify(wt, A(), snap, None)
        results["tamper_rejected"] = (not ok and "protected_paths_changed" in why)
        run(["git", "checkout", "--", "conftest.py"], wt, 30)
        # 4 bigdiff rejected (S cap 5 files)
        os.makedirs(os.path.join(wt, "newdir"), exist_ok=True)
        for i in range(8):
            open(os.path.join(wt, "newdir", "f%d.py" % i), "w").write("x\n" * 50)
        run(["git", "add", "."], wt, 30)
        lines, files = diff_stat(wt)
        results["bigdiff_rejected"] = (files > DIFF_CAP["S"][1])
    finally:
        run(["git", "worktree", "remove", "--force", wt], repo, 60)
        shutil.rmtree(base, ignore_errors=True)
    print(json.dumps(results, indent=2))
    return 0 if all(results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
