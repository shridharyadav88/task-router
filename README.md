# task-router

Recommend-only router + script-orchestrated executor that sends each coding task to the cheapest capable agent — sized by a decision model, picked from a fixed lookup, verified by tests. The orchestrator is a stdlib script: zero model cost, never a live supervisor session, so nested agents can't burn two quotas at once.

The table generalizes: swap in your own `(agent, model, effort)` rows and quota pools.

## Install (one command)

```bash
git clone https://github.com/shridharyadav88/task-router.git
cd task-router
./scripts/install.sh        # copies the skill to Claude/Codex/opencode, verifies sha256, proves the table loads
./scripts/install.sh --check-only   # re-verify installs any time (catches drift/clobber)
./scripts/install.sh --uninstall    # remove all three copies
```

Requirements: python3 stdlib only, plus at least one coding-agent CLI
(`claude`, `codex`, `cursor-agent`).

## Your first routed task (5 minutes)

```bash
python3 scripts/setup.py --discover        # read-only: what agents/models you have
python3 scripts/setup.py --guided          # tick off agents (1,3,4), pick a bundle,
                                           # cursor fraction or blank, spend ceiling —
                                           # verify runs BEFORE anything is written
python3 scripts/setup.py --demo            # dry-run route preview, zero writes, zero quota
echo "add dark mode toggle" > task.txt
python3 scripts/route.py --spec task.txt --size S --claude-wk 1 --claude-h5 1 --codex-wk 1 --codex-h5 1
```

Prefer chatting to typing? Paste `SETUP_PROMPT.md` into your own agent
(Claude/Codex/Cursor chat): it interviews you, emits a fenced `answers.json`,
and you run `setup.py --from-answers answers.json` — same schema, same verify gate.
Validate any answers file any time: `setup.py --validate-only answers.json`.

## When the router answers (failure-mode table)

| Output | Meaning | Exact next command |
|---|---|---|
| `pick` + row/cmd | routed — run the printed command, or hand it to that agent | `codex exec …` (or your pick's `cmd`) |
| `clarify` | spec too vague to size — no quota spent | answer the 3 `ask` lines, re-run |
| `defer` (`no eligible row`) | every pool RESERVE/down for this size | wait for reset, or re-run with `--provider-down` removed / a smaller scope |
| `defer` (XL, both pools out) | claude + cursor pools lack headroom | wait, or split the task below XL |
| `spec_too_long` | spec over 48k chars — trim, never truncate | shorten the spec, re-run |
| `error` | bad input (unreadable spec, missing --size, bad table) | read `why`, fix the input |

## Problem

Most developers now pay for several AI coding subscriptions at once: a Claude plan, a Cursor plan, ChatGPT for Codex, plus whatever free tier or local model fills the gaps. Free tiers count too, and their limits are the tightest of all. Each plan meters usage differently. Five-hour windows here, weekly pools there, per-model multipliers somewhere else. Blow a weekly pool and you are locked out for days, including plain chat.

Without routing, every task goes to whichever agent is already open. That is usually the most expensive one. A heavy week burns the same caps interactive work needs to survive on.

Chaining agents is worse. One paid agent supervising another paid CLI burns two subscriptions for a single task, and the outer session re-reads everything the inner one wrote as billable context. Two meters for one task, and the handoff drops half the reasoning in between.

It helps single-agent setups too. Even with one subscription, the router matches each task to the right model for its complexity instead of running everything on the flagship. Simple tasks stop burning flagship tokens.

The router fixes all of it with one move: size each task with a cheap decision model, send it to the cheapest setup that can actually do it, and never nest paid sessions. A free script does any orchestrating. A paid model only ever works. It never watches.

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

30 labeled golden tasks (`references/golden-set.json`), both engines scored on all of them (`references/calibration.md`):

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
SETUP_PROMPT.md           # paste-in setup interview for your own agent
references/routing-table.json   # rows, chains, effort, bars, quotas, timeouts
references/golden-set.json      # 30 calibrated tasks
references/executor.md        # v1 pipeline spec
references/calibration.md     # fits, misses, design changes
references/risks.md           # per-area risk → mitigation → catching gate
references/audit-schema.json  # ledger schema (v1, 19 columns)
scripts/route.py          # recommend-only lookup
scripts/route_exec.py     # script-orchestrated executor
scripts/setup.py          # setup wizard: discover/guided/from-answers/demo
scripts/install.sh        # one-command installer (+ --check-only, --uninstall)
scripts/size.py           # elephant-9b sizing + Jev combiner
```

## Provenance

Grilled by Claude Opus 5.5 across 4 rounds (router design x2, token-vs-quality executor, 30-task labeling at high effort); hill-climbed with a blind 3-provider council to bar. Audit trail: append-only JSONL, hashes only, no spec text or secrets. MIT.
