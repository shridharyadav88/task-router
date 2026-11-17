# Risk register — table-v3 (risk → mitigation → catching gate)

Each design area names its silent-failure risk, the mitigation in the product,
and the gate that catches a regression before launch. All gates run in
`scripts/verify_table.py` unless noted.

| # | Area | Silent risk | Mitigation | Catching gate |
|---|---|---|---|---|
| 1 | Composite ids + R-aliases | stale readers/tools keying on R-ids break | alias preserved on every row; audit pick carries row+alias | v1-table-loads (v1 fixture routes under new code) |
| 2 | Cross-harness ordering | metered cursor row precedes direct pool row → silent spend | cost_tiers: direct-before-metered on S/M/L; muse position = legacy exemption (pre-existing order, api-metered) | tripwire-direct-before-metered |
| 3 | Cursor effort slugs | catalog drift (slug renamed/retired) launches wrong model | exact slug pins; refresh reports drift, never auto-adds rows | setup --refresh drift report (manual) + codex-pinned/cmd checks |
| 4 | Cursor quota | RESERVE cursor pool still picked → metered burn | frac-RESERVE skips in walk + fallback + pre-scan; UNKNOWN-safe default; never sole XL | cursor-frac-RESERVE-skips + smoke-XL-overflow-cursor |
| 5 | XL overflow | double-degrade (weak row on XL after pool loss) | XL defers unless claude OR cursor has headroom; chains.XL frozen 3 rows | smoke-XL-nothing-defers + chain-XL-model-first |
| 6 | Setup wizard | clobbered hand-edited table | --write refuses without --force; --refresh never touches rows/chains | manual (confirm prompt); parity_check 30/30 after any table edit |
| 7 | Audit schema | silent column drift breaks ledger readers | audit-schema.json v1 + bump rule; producers listed | audit-schema-valid + no-audit_line-in-table |
| 8 | Golden compat | relabeled goldens mask regressions | no relabeling, ever; parity runs frozen goldens | parity_check 30/30 (bar: agreement >= 0.90) |
| 9 | Pasted-prompt injection | a pasted agent transcript smuggles extra JSON/commands into answers | contract-pinned schema + script-side rejection; agent-must-not-write rule; --validate-only repair loop | answers-contract-valid + bad-fixture rc=2 probes |
| 10 | Distribution trust | curl-pipe or tampered clone ships evil scripts | git-clone default; no bare curl-pipe (sha-pinned command documented as the only exception); per-file sha MATCH on install | install.sh sha verify + --check-only |
| 11 | Stale-copy drift | old installs silently diverge from the repo | --check-only drift detection; README weekly cron hint | install.sh --check-only (manual/CI) |

Cost-tier note: free (opencode) may precede metered rows; direct claude/codex pools
precede metered cursor rows on S/M/L. Muse (api-metered, pre-existing chain position)
is exempt from reordering by the compat guard — its spend is bounded by the same
RESERVE/LOW pool rules as other numeric pools only where pools exist; presence pools
rely on --provider-down.
