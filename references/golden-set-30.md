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

## New 20 (Opus 5.5-high)

| ID | Task | Label | Pick | Why | Jev |
|---|---|---|---|---|---|
| S3 | Add `--json` output flag to the disk-usage report script | S | codex/default/low | one file, stdlib `json` | S / .1,.1,.1,.4 / no |
| S4 | Fix wrong UTC offset in Jellyfin scan-log timestamps; failing test exists | S | codex/default/low | test pins the fix | S / .1,.0,.1,.0 / no |
| S5 | Add `After=network-online.target` + `Wants=` to existing restic systemd unit | S | codex/default/low | two-line unit edit | S / .2,.1,.1,.7 / no |
| S6 | Write README section for Pi-hole + Unbound setup from existing configs | S | codex/default/low | docs only, no code paths | S / .0,.2,.1,.0 / no |
| S7 | Add `HEALTHCHECK` hitting `/health` to the Flask dashboard Dockerfile | S | codex/default/low | one directive, known pattern | S / .1,.1,.1,.5 / no |
| S8 | smartctl wrapper exits non-zero when reallocated sectors > 0; test exists | S | codex/default/low | one branch, test covers it | S / .2,.1,.1,.1 / no |
| M5 | Grafana dashboard JSON + Prometheus alert rules for SMART health and disk temps | M | codex/default/medium | 2 files, known schemas | M / .2,.3,.3,.7 / no |
| M6 | Sync Sonarr/Radarr tags to qBittorrent categories via their APIs, with tests | M | codex/default/medium | new module, 3 clear APIs | M / .3,.3,.3,.4 / no |
| M7 | Refactor backup CLI into argparse subcommands, preserve behavior (preserve: tests green on base and after) | M | codex/default/medium | existing suite locks behavior | M / .2,.1,.4,.0 / no; preserve: green base+after |
| M8 | WireGuard peer generator CLI: keys, IP allocation, QR output, with tests | M | codex/default/medium | new module, handles keys locally | M / .4,.2,.3,.4 / no |
| M9 | Idempotent Ansible role installing node_exporter + promtail on 4 hosts | M | codex/default/medium | known role layout, reversible | M / .3,.2,.4,.7 / no |
| M10 | Caddy reverse proxy + DNS-01 certs for 6 internal services | M | codex/default/medium | one Caddyfile, known pattern | M / .4,.2,.3,.8 / no |
| M11 | Ping/HTTP checker sending ntfy alerts, flap dedupe, with tests | M | codex/default/medium | ~200 LOC, clear interface | M / .2,.3,.3,.4 / no |
| M12 | "Fix the network stuff, it's flaky" | M → clarify (Noul; never XL) | none: clarify | no target, no done-test; vague must never route XL | clarify / .4,.9,.6,.9 / clarify |
| L4 | Rewrite restic forget/prune retention across 3 repos | L (bumped from M on risk) | claude/sonnet/high | code is M, prune deletes snapshots: risk .8 bumps M->L | M / .8,.2,.3,.6 / no => bumped |
| L5 | Immich Postgres 15->17 upgrade script: dump/restore with rollback on failure | L (bumped from M on risk) | claude/sonnet/high | code is M, can corrupt the photo DB: risk .8 bumps M->L | M / .8,.3,.3,.8 / no => bumped |
| L6 | Async journald shipper from 5 hosts to Loki, backpressure, at-least-once delivery, tests | L | claude/sonnet/high | concurrency + durability | L / .5,.4,.5,.6 / no |
| L7 | Lab inventory: ARP/nmap scan + Proxmox API merge, emits mkdocs site, with tests | L | claude/sonnet/high | 3 integrations, 10+ files | L / .3,.5,.7,.9 / no |
| L8 | Merge ~12 bash backup scripts into one tested Python package, keep cron compat | L | claude/sonnet/high | many files, zero tests | L / .5,.3,.8,.9 / no |
| XL2 | Whole lab to IaC: Terraform Proxmox VMs/LXCs + Ansible + sops secrets + CI drift detection | XL | claude/opus/max | cross-cutting infra, one escalation can't recover it | XL / .8,.6,.9,.9 / no |
