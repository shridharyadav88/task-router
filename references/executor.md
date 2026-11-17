# Executor v1 Pipeline (approved 2026-11-14)

Orchestrator: `scripts/route_exec.py` (stdlib, zero model cost). One worker per attempt, one-shot, disposable worktree. Never nested sessions, never `--continue`/`--resume` (asserted in code).

## Entry requirements

- Executable done-criterion (test command) written by human/spec-author, never the worker. No criterion -> task stays recommend-only (docs/UI/config included).
- Git repo (codex needs one anyway). Spec <= ~48k chars, hash pinned at intake; hash change mid-task = new task.

## Pipeline (9 steps, Opus round-3 revision)

1. Size (Jev) -> `route.py` pick. `clarify`/`defer`/`spec_too_long` exits here.
2. Approve the done-criterion: "does this test encode the spec?" Human or one cheap call. Worker-written tests = self-grading, rejected.
3. Red-on-base, run TWICE. Variant `red` (default): must FAIL both, else reject. Variant `preserve` (refactors): must PASS both on base AND after, plus protected paths unchanged.
4. Snapshot: protected-path hashes + collected-test count (when `--collect-cmd` given) + clean-tree check.
5. Launch ONE worker in a disposable worktree (`git worktree add --detach`), hard caps + wall-clock timeout (S 10 / M 20 / L 40 / XL 90 min; claude also `--max-budget-usd`). Packet = PACKET.md in worktree (spec + rules: implement only, never edit tests/configs, stay in diff cap, finish with quiet targeted test run ~2KB output). Prompt references the file; full logs never cross agents.
6. Verify (all free): criterion green AND protected hashes equal AND count floor met AND diff within cap (S <=150 lines/5 files, M <=400/12, L <=1000/25, XL uncapped) AND lint (if given).
7. Fail -> deterministic triage (regex on exit code/stderr, no LLM): flaky (passes on unchanged-tree rerun) -> `human`; transient (429/timeout/OOM/net) -> reschedule, STILL counts to the cap; else same-size ranked fallback first, then escalate ONCE (+1 size) from base with the 4KB digest (spec path+sha, failing test IDs, last 40 failure lines).
8. Second fail -> `human` with pre-digested packet (spec hash, both attempts, log paths). Total 3 launches max, transient retries included; per-task $2 ceiling across attempts (actuals parsed, estimates enforce).
9. Log actuals: claude `total_cost_usd`, codex JSON tokens. No manual reconcile.

## Sandboxes (user decision: permissive, 2026-11-14)

Default modes everywhere; disposable worktree per attempt; no secrets in env; never `--dangerously-skip-permissions` on the host. Residual prompt-injection risk is caught by protected-paths + count floor + diff caps, not by trust. codex: `--sandbox workspace-write` (gateway contexts: `danger-full-access` with worktree + clean-tree + review, per codex skill).

## Failure ledger

Every provider RESERVE -> queue with timestamp, never spin. Attempt-2 contamination avoided: always from base. `human` owns flaky quarantine; flaky tests are excluded from the criterion by human edit, never by the worker.
