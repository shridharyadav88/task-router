---
name: task-router
description: Route any coding task to the cheapest capable agent.
version: 0.3.2
author: Hermes Personal
license: MIT
metadata:
  hermes:
    tags: [router, agents, quota, triage]
    related_skills: [claude-code, codex, opencode, hill-climb-council]
---

# Task Router

Router + script-orchestrated executor (v1): size with a decision model, pick the cheapest capable agent, run exactly ONE worker one-shot under deterministic gates, escalate at most once, else hand a pre-digested packet to a human. The orchestrator is a stdlib script: zero model cost, never a live supervisor session. Grilled by Claude Opus 5.5 in 3 rounds (2026-11-14); all round-1 holes and the v1 token-vs-quality grill are answered in `references/`.

Recommend-only mode stays available: `scripts/route.py` alone answers Q4-safe (no nested sessions ever).

## When to Use

- Any coding task where you must choose between claude-code, cursor-agent, codex, local-llm, opencode, muse (copilot staged, binary missing).
- User says route this, cheapest capable, save quota, or which agent/model/effort.
- Don't use for: non-code chores (use local-llm directly), an obvious S fix inside the calling agent (just do it), executing the pick (v0 recommends; the caller runs it).

## Verified Inventory (2026-11-14, this box)

| Agent | CLI | Auth | Models you can use |
|---|---|---|---|
| claude-code 2.1.322 | `claude` | Pro, pool shared chat+Code | `--model opus` = Opus 5.5 (proven this session), `sonnet`, `haiku`; `--effort low/medium/high/xhigh/max` |
| cursor-agent 2026.11.05 | `cursor-agent` | work login (X-sub) | 150+ ids via `--list-models`; pin exact id, never `auto`; Max-suffix costs more |
| codex 0.167.0 | `codex` | ChatGPT login | DEFAULT model only: omit `--model` (named models rejected on this plan). Resolve the default non-interactively: the priority:1 entry of `codex debug models` wins unless a `^model` key exists in ~/.codex/config.toml — an absent key means the built-in default applies. |
| local-llm | tracked wrapper | free | `coder-3b-q8` default, `coder-7b-q6k` harder; ~5 tok/s, 100-token cap: non-code chores only, never on a fallback path |
| opencode 2.3.0 | `opencode` (`~/.opencode/bin`) | free tier, no login needed | `opencode/<model>-free` models incl. deepseek; login only for paid providers |
| muse 1.4.11 | `muse` | API-key metered, no pool | `muse exec` + muse-spark-1.3 (reasoning-high verified); untrusted workspaces lose auto-delegation |
| copilot | NOT installed | — | dropped from rows; staged copy only |

Quota pools are shared and weekly-first: Claude Pro 5hr (>=5x Free) + weekly all-model cap (Fable via credits only); Cursor X-sub weekly pool shared w/ Grok with per-model multipliers; Codex ChatGPT 5hr + weekly (~$46 API value/wk measured Nov 2026). `/usage`, `/status`, cursor.com/dashboard are manual reads; the script takes ledger estimates and UNKNOWN counts as LOW.

## Benchmark Rule (never mix the two indices)

- Route ONLY on `(harness, model, effort)` rows from `references/routing-table.json` (table_format 2, table_v 2026-12; AA Coding Agents Index snapshot 2026-11-10). Rows are keyed by composite `harness:model` id with a stable R-alias for audit continuity (R1 claude/opus 61.7, R2 claude/sonnet 59.3, R3 codex/gpt-6-chat-thinking ~54, R4 muse, R5 opencode free, R7 claude/haiku, CURSOR pinned-last, plus cursor-opus-5-5 slug variants per size). Same model via different harnesses = adjacent rows; S/M/L order direct pools before metered cursor rows (tripwire-gated), XL allows model-first fallback (R1 → cursor-opus-max → R2). Edit the JSON to change routing — never the script; `route.py --self-test` proves the table loads; old v1 tables still load via alias synthesis.
- Within ~3 pts = tie, cheapest quota wins. Exception (Opus-grill decision): XL always goes R1.
- The AA Coding Index (model-only: Fable 5.1 81.6, Opus 5 78.0) is context only. Fable is #1 model but #8 harness: score the harness, not the model.

## Sizing (decision model sizes; the lookup picks)

- Choice over closed {S, M, L, XL} = size. Scores live on the 0-3 legend scale (NOT 0-1: both engines return expected level). Bump UP max 1 step, never down, when **risk >= theta** (elephant 1.65, Jev 1.85 — fitted on 30 goldens, `references/calibration.md`). Only the risk signal bumps: tests-missing tunes verification intensity, never size. Never bump XL. Noul (spec too vague) returns `clarify`, never XL; a forced run becomes M on a non-default provider. Vague gates are per-engine (Jev runs hot: clean tasks score 0.35-0.74): elephant noul >= 0.5, Jev yes-prob >= 0.8. Combined verdict uses max via `size.py --jev-*` flags.
- elephant-9b (`baseten/elephant-1`, $0.035/M in, 16k ctx) is the DEFAULT sizing engine via `scripts/size.py` (OpenRouter Decisions endpoint; user standing order). It returns calibrated probabilities per option — parse `answers.size.choice`, `answers.vague.noul` as P(vague), and `usage.cost` for the ledger. Jev (`jev_route`/`jev_evaluate`) is the cross-check: if elephant's choice confidence is low (<0.6) or its Noul is high, ask Jev too and take the conservative size. Per-engine theta, pin the exact model string from the response (e.g. `baseten/elephant-1-20261021`). Same Choice/Score/Noul primitives as Jev; never use it to write prose or code.
- Vague-split resolution (max rule): vague_final = max(elephant noul, jev yes-prob); >= 0.5 returns `clarify` (never XL on vague); 0.2-0.5 proceeds with a `sizing_uncertain` warning (+ human glance for L/XL). Size comes from elephant Choice unless its confidence < 0.6, when Jev Choice breaks the tie (logged). `size.py --jev-vague/--jev-size/--jev-conf` computes the combined verdict.

## Procedure

1. **Probe** (cache 1h): `which claude cursor-agent codex opencode muse` plus `claude -p ok --max-turns 1`, `codex login status`, `cursor-agent status`, `opencode models`, muse `exec` probe. Installer scripts may pin a major line (a v1-only installer refuses v2) — check upstream releases for a newer major before settling on the installed version. For a new agent CLI, prove the full chain before routing to it: binary version, model resolution (`model-profile show`-equivalent), one headless exec probe, auth state. TUI-only screens (interactive `/status`, dashboards) are not probes — read caches/configs instead and take the remainder as dated user ground truth. Ineligible agents are out. Completion: eligibility list.
2. **Guard length**: spec over ~48k chars (~12k tokens) returns `spec_too_long`. Completion: sha256 recorded, text never logged.
3. **Size** with `terminal(command="python3 <skill>/scripts/size.py --spec <f> --log <log>")` (elephant-9b via OpenRouter Decisions; reads `OPENROUTER_API_KEY` from `~/.hermes/.env`). Parse `answers.size.choice` + `answers.vague.noul` + `usage.cost`. Cross-check with `jev_route`/`jev_evaluate` when elephant confidence < 0.6 or vague > 0.5 — take the conservative size. Completion: final size + bumped flag.
4. **Recommend** via `terminal(command="python3 <skill>/scripts/route.py --spec <file> --size <S|M|L|XL> [--self-agent <id>] [--quota flags]")`. Pass `--quota-src <provenance>` (est|measured|user-GT|metered-screenshot|probe|vendor-table) matching how the quota numbers were obtained — omitting it silently logs src est over probed numbers. Batches: after 2 tasks land on one provider, pass `--avoid-agent <id>` for it (spread rule — different pools for parallel/sequential work); override is logged when no alternative clears the bar. Completion: JSON pick on stdout.
5. **Report** the pick (agent + exact model/effort string), why, each rejected row + why, quota snapshot, done-criterion. Done = tests pass, checked by the caller. Completion: user runs the pick.
6. **Log**: the script appends the decision JSONL line; the caller appends the outcome line (pass/fail, wall time) under the same spec_sha256. Completion: both lines share the hash.

## Failure Rules

- 429/quota error marks that provider RESERVE for its window; repick cross-provider (claude-chat == claude-code pool, chatgpt == codex pool; never retry same pool).
- Attempt 2 is the same-size ranked fallback from base; at most one size-up escalation after that; 2nd failure returns `human`.
- Weekly under 20% = RESERVE (S tasks only); UNKNOWN = LOW; XL defers only when BOTH claude and cursor pools lack headroom — otherwise XL overflows to cursor-opus-max.

## Verification

- `terminal(command="python3 <skill>/scripts/route.py --spec <f> --size M --log <tmp>")` prints JSON with agent/model/effort + row; the tmp log holds a valid JSON line.
- Smoke: golden L3 enters M and exits L (risk bump); the vague-XL1 variant exits `clarify`.
- `scripts/verify_table.py` checks `references/routing-table.json` (schema, chains, effort coverage, cost-tier tripwire, v1-table back-compat, golden parity smoke) — always run it with workdir set to the skill directory (e.g. `python3 scripts/verify_table.py` from there). An absolute script path from another cwd raises FileNotFoundError and proves nothing about the table.
- Setup: `scripts/setup.py --discover` (read-only: binaries, cursor slugs, codex cache, claude aliases) → `--write` asks only plan caps + spend ceiling + confirm and writes the table (needs `--force` to clobber) → `--refresh` updates catalogs, reports new-slug drift, never touches rows/chains.

## Executor v1 (script-orchestrated, zero model cost)

- Orchestrator `scripts/route_exec.py` (stdlib only) runs the pipeline in `references/executor.md`: intake -> red-on-base x2 -> snapshot -> ONE worker one-shot (caps + wall-clock timeout) -> deterministic verify -> cheap regex triage -> single escalation from base -> `human` packet. `--dry-run` and `--self-test` verify gates with no quota.
- Entry requires an executable done-criterion written by human/spec-author (never the worker); tasks without one stay recommend-only. Human always reviews before merge, so no frontier diff review.
- Load-bearing gates (all free): red-on-base, protected-path hashes, collected-count floor, diff caps by size, disposable worktree per attempt, 4KB escalation digest, per-task $2 ceiling, 3 launches total, `--continue`/`--resume` banned.
- Workers run PERMISSIVE (user decision 2026-11-14): default modes, disposable worktree, no secrets in env; never `--dangerously-skip-permissions` on the host. Residual risk (prompt injection editing tests) is caught by protected-paths + count floor + diff caps, not by trust.
- Timeouts: S 10 / M 20 / L 40 / XL 90 min (codex/cursor wall-clock; claude additionally `--max-budget-usd`). Ledger parses actual CLI usage (`total_cost_usd`, codex JSON tokens) and always writes `spent_tokens`; dollars are actual where reported, otherwise EST_BURN estimates flagged `usd_estimated: true` — never present estimates as actuals. Estimates only enforce the ceiling.
- Flaky (fail then pass on unchanged tree) -> `human`, never a worker retry. All-providers-RESERVE -> queue with timestamp.

## Invoke From Any Agent

- Claude Code: skill auto-loads; or run the script via `terminal` with the skill path.
- Cursor: `cursor-agent -p "Follow SKILL.md at <skill-path>, recommend only for SPEC"` with `--model` pinned to an explicit id.
- Codex: `codex exec -m <slug> "Follow <skill-path>/SKILL.md; recommend only, no edits"` (model pinned to `gpt-6-chat-thinking`, the plan default; reasoning effort via `-c model_reasoning_effort=`).
- Opencode/Copilot (staged): paste SKILL.md + `references/routing-table.json`; run the script with system python3.
- Silent-quota-burn risks are mapped per area with mitigation + catching gate in `references/risks.md` (cost tiers, cursor-frac, slug drift, XL overflow, setup clobber, audit drift, golden compat).

## Gotchas

- Quoted scores are Max effort; map effort per agent, never globally.
- Cursor `auto` and Max-suffix ids silently cost more; multiplier above 2x skips Cursor entirely.
- local-llm at ~5 tok/s cannot hold a diff; S code still goes to codex/claude, never local.
- One agent starting another CLI burns 2 quotas and drops context: v0 recommends, the caller executes, prefer `--self-agent` on ties.
- Never point `--log` at scratch/ (24h prune eats the audit trail — lost Nov-16 hill-climb run's decisions.jsonl + elephant.log). The default `~/.local/state/task-router/decisions.jsonl` is the durable ledger; overrides must also be durable paths.
- The audit line shape is a contract: the ledger has been one JSON dict per line since day one and downstream reads assume its keys. Before changing what the scripts log, read the ledger's first line and match its shape — a silent format change corrupts every historical parse.
- `jev_evaluate` score questions reject bare `type: score` — the schema needs an ordered `criteria` list of level descriptions (lowest first, e.g. `["none","low","medium","high"]`). Choice questions take a `criteria` map of option -> description. Noul takes neither. A schema error is a question-shape bug, not a tool outage: fix the shape once and retry.
- Elephant-9b `answers.<id>.noul` is a P(true) float, not a boolean — gate numerically (vague > 0.5 = clarify, never guess XL). Identity checks against `true`/`false` fail while the model answers correctly.
- The OpenRouter key lives in Bitwarden Secrets (`bws secret get` by key name), not in `~/.hermes/.env` on a fresh setup. If `size.py` reports `no OPENROUTER_API_KEY`, fetch it via `bws` and store it in `~/.hermes/.env` (keys-only listing to verify, never print the value).
- Quota reads are user ground truth until probed: TUI-only screens and login-walled dashboards enter the ledger dated and sourced, never as probe-verified. State used% and headroom% together — 'pool is full/empty' paraphrases and used↔remaining flips have both caused real misroutes; restate the user's numbers verbatim.
