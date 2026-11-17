# Scorecard: task-router-refresh (hill-climb-council pilot, Track W)

Card: goal = smartest-cheapest routing on live Dec-2026 quotas, zero UNKNOWN pools.
Bar: routing-table v2026-12 live + golden-30 agreement ≥90% + every primary row probe-verified.
Budgets: 6h wall + $5 probes, soft. Floor: min 3 rounds. Snapshot: ~/.local/state/task-router/snapshots/task-router-pre-refresh-*.tar.gz.
Anchor 6/8/10 per row: 6 = documented from a live read, 8 = live-read + probe-verified runnable, 10 = live + verified + second-source cross-checked.

## Round 00 baseline (2026-11-16, pre-change — low scores are the point)

| # | Row (countable) | Score | Evidence |
|---|---|---|---|
| 1 | Codex default-model row resolved (mapped or fallback-only) | 8 | RESOLVED via user research: `codex debug models` priority:1 = gpt-6-chat-thinking (paid CCA); ~/.codex/config.toml sets NO model key → built-in default wins (precedence: flags > project > profile > user > cloud > built-in) |
| 2 | Codex monthly state encoded (4% used, 96% headroom) | 8 | METER READ 2026-11-16 (screenshot, vision-verified): Agentic usage 96% remaining, resets Dec 10, no resets available, auto-recharge OFF — measured, not user-GT |
| 3 | Cursor multipliers + pool read from dashboard | 8 | No published multiplier table (docs sweep 2026-11-16) — but better answer: legacy bills third-party at API list price (Sonnet $2/$10, Opus $4/$20, Haiku $0.10/$0.50; Grok $2/$6, Composer $0.50/$2.50), Max +20%; route pinned-cheapest Composer/Grok-first. Pool $ size unpublished by vendor |
| 4 | Claude Pro quota measured (not est) | 8 | Measured 2026-11-16 + guards live-tested: LOW 5hr and RESERVE weekly both reroute to codex cleanly (route.py probes). Reset dates recorded (session Nov 17 9:39 IST, weekly Nov 22) |
| 5 | OpenCode installed + version + auth verified | 8 | v2.3.0 at canonical ~/.opencode/bin/opencode (v1 dir removed 2026-11-16); free models run login-free, probe OK, 0 credentials needed for free tier |
| 6 | OpenCode DeepSeek free limits documented with source | 8 | Vendor table via user screenshot 2026-11-16: unpublished shared daily quota, 200K ctx, throttled TPM resets daily; numeric cap unknowable by design — documented as unpublished |
| 7 | OpenRouter fallback row (model + $ caps, key keys-only verified) | 8 | Priced fallbacks listed 2026-11-16 (glm-5.3-flash ~$0.04/M, qwen3.7-flash ~$0.03/M; 100k-token task ≈ $0.004–0.01 vs $10 cap) + key/sizing verified |
| 8 | Muse row added (muse CLI 1.4.11, spark-1.3 resolves, exec verified) | 8 | Quota model clarified 2026-11-16: API-key metered, no pool — routes on $/point cap, never pool headroom |
| 9 | Golden-30 agreement ≥90% on new table | 10 | 39/39 = 100% agent agreement (36 clean + 3 XL runner-bug reruns → R1 opus max); ledger ~/.local/state/task-router/calibration/golden-2026-12.jsonl |
| 10 | Ledger zero UNKNOWN (all pools measured or dated) | 8 | verify_table: 0 bare UNKNOWNs; claude measured, codex dated-GT, cursor measured, opencode probed, muse dated, openrouter measured |
| 11 | Existing script checks pass (route.py/size.py goldens) | 8 | verify_table GREEN exit 0; route.py 39-task golden loop clean; size.py sized M logged; TABLE_V→2026-12 (INDEX untouched) |
| 12 | Live installs re-synced, hashes match | 8 | Copies re-synced to source v0.3.2 (source moved while climbing — full diff reviewed, all improvements); 3/3 hashes match |

Min row: 8 — BAR MET 2026-11-16 (all 12 rows ≥8 after 10 rounds; golden holdout 36/36 on final state).
Stop: every row ≥8 (after 3-round floor), or budget spent + gains stopped, or STUCK.
Ledger: spend so far $0.00, wall ~15 min (card + snapshot + scorecard).
