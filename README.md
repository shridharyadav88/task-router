# task-router

Recommend-only router + script-orchestrated executor that sends each coding task to the cheapest capable agent — sized by a decision model, picked from a fixed lookup, verified by tests. The orchestrator is a stdlib script: zero model cost, never a live supervisor session, so nested agents can't burn two quotas at once.

The table generalizes: swap in your own `(agent, model, effort)` rows and quota pools.

## Problem

I pay for four AI coding subscriptions at once: Claude Pro, a Cursor plan, ChatGPT for Codex, plus a free local model. Each one meters usage differently. Five-hour windows here, weekly pools there, per-model multipliers somewhere else. Blow a weekly pool and you are locked out for days, including plain chat.

Without routing, every task goes to whichever agent is already open. That is usually the most expensive one. A heavy week burns the same caps your interactive work needs to survive on.

Chaining agents is worse. One paid agent supervising another paid CLI burns two subscriptions for a single task, and the outer session re-reads everything the inner one wrote as billable context. Two meters for one task, and the handoff drops half the reasoning in between.

The router fixes both with one move: size each task with a cheap decision model, send it to the cheapest setup that can actually do it, and never nest paid sessions. A free script does any orchestrating. A paid model only ever works. It never watches.

## How it works

```
spec -> size (elephant-9b, Jev cross-check) -> route.py pick -> ONE worker one-shot -> tests verify -> pass/log, or triage -> escalate once from base -> human packet
```

1. **Size** (`scripts/size.py`): elephant-9b via OpenRouter Decisions (`baseten/elephant-1`, ~$0.000016/call). Choice over {S, M, L, XL}; risk/vague signals on the 0-3 legend scale. Jev is the cross-check (`--jev-vague/--jev-size/--jev-conf`); vague uses max, size ties break to Jev below 0.6 confidence.
2. **Route** (`scripts/route.py`): deterministic lookup — size x quota x installed agents. Weekly pool first, 5-hour second, UNKNOWN counts as LOW, 20% weekly reserve, cross-provider fallback, `--avoid-agent` spreads batches.
3. **Execute** (`scripts/route_exec.py`, optional): red-on-base x2, protected-path hashes, count floor, diff caps, disposable worktree, 4KB escalation digest, $2/task ceiling, 3 launches max, `--continue`/`--resume` banned. `--dry-run` / `--self-test` verify gates with no quota.

## Routing table (AA Coding Agents Index, 2026-11-10 snapshot)

| Size | Primary | Fallback | Emergency | Effort |
|---|---|---|---|---|
| S | codex default | claude sonnet | cursor pinned-cheapest | low |
| M | codex default | claude sonnet | cursor pinned-mid | medium |
| L | claude sonnet | codex default (`below_bar`) | cursor pinned-top | high |
| XL | claude opus | claude sonnet + `XL_degraded` | — (`defer`) | max |

Within ~3 index points = tie, cheapest quota wins. XL always goes top row. Scores quoted are Max effort; map effort per agent, never globally.

## Calibration

30 labeled golden tasks (`references/golden-set-30.md`), both engines scored on all of them (`references/calibration.md`):

| Engine | Vague gate | Risk theta (0-3 scale) | Agreement |
|---|---|---|---|
| elephant-9b | noul >= 0.5 | 1.65 | 26/30 |
| Jev 1.14 | yes-prob >= 0.8 | 1.85 | 24/30 |

Bump rule: risk >= theta bumps up max one step, never down, never XL. Only risk bumps — tests-missing tunes verification, never size. Residual misses are Choice over/undershoots, queued for human adjudication.

## Quickstart

```bash
# 1. Size it
python3 scripts/size.py --spec SPEC.md
# {"size": "M", "final_size": "M", "vague_combined": 0.07, ...}

# 2. Route it (recommend-only)
python3 scripts/route.py --spec SPEC.md --size M
# {"pick": {"agent": "codex", "model": "default", "effort": "medium", ...}}

# 3. Execute it (needs a git repo + test command)
python3 scripts/route_exec.py --spec SPEC.md --size M \
  --criterion "pytest -q" --repo ~/myproject --budget 2.0
```

Batch routing with spread: add `--avoid-agent <id>` for providers already carrying 2 picks.

## Requirements

- Python 3 stdlib only. No dependencies to install.
- One coding-agent CLI for workers: `claude`, `codex`, and/or `cursor-agent` (opencode/copilot staged, binaries optional).
- `OPENROUTER_API_KEY` in the environment (or `~/.hermes/.env`) for sizing. Never commit keys — the scripts read env only.

## Layout

```
SKILL.md                  # the skill: triggers, procedure, gates, gotchas
references/routing-table.md   # index snapshot, quota states, spread rule
references/golden-set-30.md   # 30 calibrated tasks
references/executor.md        # v1 pipeline spec
references/calibration.md     # fits, misses, design changes
scripts/route.py          # recommend-only lookup
scripts/route_exec.py     # script-orchestrated executor
scripts/size.py           # elephant-9b sizing + Jev combiner
```

## Provenance

Grilled by Claude Opus 5.5 across 4 rounds (router design x2, token-vs-quality executor, 30-task labeling at high effort); hill-climbed with a blind 3-provider council to bar. Audit trail: append-only JSONL, hashes only, no spec text or secrets. MIT.
