# Golden Set v0 (10 tasks, Opus 5.5 labels, 2026-11-14)

Smoke-test only: enough to validate the Choice/Score/Noul split, NOT to fit per-engine theta (needs 30) or to switch elephant-9b on. Quota assumed OK, codex R3 assumed clearing the bar. `spec_sha256: TBD-<id>` = fill in when real specs are filed.

| ID | Task | Label | Expected pick | Why | Predicted Jev: Choice / Score(risk,ambiguity,touch,tests) / Noul |
|---|---|---|---|---|---|
| S1 | Add `--dry-run` to an argparse restic backup script | S | codex low | one file, one obvious flag | S / .2,.1,.1,.3 / no |
| S2 | Fix off-by-one in keep-N log rotation; failing test exists | S | codex low | test pins the fix | S / .1,.0,.1,.0 / no |
| M1 | systemd service + timer for nightly backup with healthchecks.io ping | M | codex medium | 3 files, known pattern | M / .3,.2,.3,.6 / no |
| M2 | Prometheus exporter for NUT/UPS stats, ~150 LOC, with tests | M | codex medium | new module, clear interface | M / .1,.2,.3,.3 / no |
| M3 | INI -> TOML config migration (`tomllib`), keep reading old INI | M | codex medium | back-compat edge cases | M / .4,.3,.4,.3 / no |
| M4 | Watchdog restarting unhealthy compose containers, with rate limiting | M | codex medium | restarts are reversible | M / .5,.3,.2,.6 / no |
| L1 | Split 1.5k-line home-automation script into a package, add tests | L | claude sonnet high | 8+ files, zero tests | L / .4,.3,.8,.9 / no |
| L2 | Async MQTT -> SQLite ingest with backoff, no loss on restart | L | claude sonnet high | concurrency + durability | L / .6,.4,.5,.5 / no |
| L3 | ZFS snapshot pruner with GFS retention | L (bump test) | claude sonnet high | code is M, deletes data: risk .9 bumps M -> L | M / .9,.2,.3,.6 / no => bumped |
| XL1 | ~20 compose services to k3s + Helm, sops secrets, Traefik ingress | XL | claude opus max | cross-cutting infra, 1 escalation cannot recover | XL / .8,.5,.9,.9 / no |

Noul check (add as set grows): XL1 rephrased as "make my homelab better" must return `clarify`, never XL.
