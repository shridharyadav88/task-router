# Spec: routing-table v2026-12 rewrite (group 1 of pilot task-router-refresh)

## Problem
Router quotas are stale (est rows, UNKNOWN pools); codex default unmapped; no muse/opencode/openrouter rows. Tasks may land on wrong/over-quota agents.

## Solution
Publish routing-table v2026-12 with every pool measured or dated, codex default named, new muse + opencode + openrouter rows, $10/point cap. No logic changes to route.py/size.py except TABLE_V bump.

## Seams (agreed, frozen)
- `references/routing-table.json` (the table; sections: usable rows, size bars, effort map, lookup, quota states, subscription limits, probe evidence, local-llm boundary, spread rule, audit line).
- `scripts/route.py` TABLE_V constant only (2026-11-10 → 2026-12). INDEX scores untouched (never re-rank by hand).

## Done-criterion (executable, author-written)
`python3 scripts/verify_table.py` exits 0 (9 checks: version header, no undated UNKNOWN, muse/opencode/openrouter/codex-default/claude-measured/cursor-pools rows present, golden-30 agreement ≥90% run separately). RED proven: fails on v2026-11-10 table.

## Testing decisions
- verify_table.py = the test (external behavior: table contents), stdlib only.
- Golden-30: `route.py` run with measured quotas; agreement vs golden-set.json expected picks ≥90%.
- Prior art: existing script goldens (row 11).

## Out of scope
Re-fitting thetas, re-labeling goldens, changing CHAINS/EFFORT logic, model re-ranking, cursor dashboard multiplier math (none shown), codex interactive /status read.
