# Routing Table v2026-12 (snapshots read 2026-11-16)

Source indices (read-only, never re-rank by hand):

- AA Coding Agents Index 2026-11-10 = ROUTING index (agent+harness+effort rows).
- AA Coding Index (model-only) = context only, never routes.

## Usable rows (this box, verified 2026-11-16)

| Row | Agent | Model/Effort | AA Agents score | Can you run it |
|---|---|---|---|---|
| R1 | claude-code | `--model opus` + `--effort max` (Opus 5.5) | 61.7 (#1) | YES Pro (session 2% used, weekly 0%; reset Nov 17 9:39 IST) |
| R2 | claude-code | `--model sonnet` + `--effort high` (Sonnet 5.5) | 59.3 (#5) | YES Pro (same pool as R1) |
| R3 | codex | default model = gpt-6-chat-thinking, omit `--model`, `-c model_reasoning_effort=<low\|medium\|high>` | ~54 (codex-default family) | YES ChatGPT Free plan — METER READ 2026-11-16 (screenshot): Agentic usage limit 96% remaining, resets December 10; no limit resets available; automatic recharge OFF. No `model=` key in ~/.codex/config.toml → built-in default wins |
| R4 | muse | `muse exec` + model muse-spark-1.3 (resolves reasoning-high) | none in index | YES, verified 2026-11-16 (CLI 1.4.11, headless exec OK; untrusted workspaces lose auto-delegation). Cheap-smart per user; unindexed → S/M fallback, never sole XL. Quota: API-key metered, no pool (user-GT 2026-11-16) |
| R5 | opencode | v2.3.0 `opencode run --model opencode/deepseek-v4.1-flash-free` | none in index | YES login-free, verified 2026-11-16 (0 creds, probe OK). Free tier: unpublished shared daily quota, 200K ctx, throttled TPM, resets daily (vendor table via user screenshot 2026-11-16); S/M only (small models) |
| R6 | openrouter | elephant-1 sizing + paid fallback models, $ caps | n/a (sizing + pay-per-use) | YES key valid 2026-11-16 (HTTP 200, 435 models; no :free DeepSeek — free-DeepSeek lives on R5). Sizing: baseten/elephant-1-20261021 ($0.000004/probe). Priced fallbacks (list 2026-11-16): z-ai/glm-5.3-flash ~$0.04/M in, qwen/qwen3.7-flash ~$0.03/M in — a 100k-token task ≈ $0.004–0.01, far under the $10/point cap |
| — | cursor-agent | pinned id from `--list-models`, never `auto` | none in index | YES logged in; LEGACY Pro $20/mo (NOT X-sub): two monthly pools, reset Nov 17 — Cursor Models 1%, Other Models 1%. No published multiplier table; legacy bills third-party at API list price (e.g. Sonnet 5.5 $2/$10, Opus 5.5 $4/$20, Haiku 5.5 $0.10/$0.50 per 1M in/out; Grok 4.7 $2/$6, Composer 2.5 $0.50/$2.50) + Max Mode +20%. Route pinned-cheapest, prefer Composer/Grok end for S/M |

Near rows for context: Devin Fusion 61.5, Copilot Fusion 59.9, Antigravity Gemini 59.4, Muse Wonder Full 58.9, Fable 5.1 Max 57.6 (model-only #1 at 81.6: the harness/model split that proves the rule), Codex Sol Max 54.1, Opencode GLM-5.3 Max ~top-15.

## Size bars (index points a row must clear)

S >= 50, M >= 50, L >= top-3 (58.7: R1+R2 tie, R2 wins on quota), XL = top row only (R1; deliberate exception, confirmed: a failed XL costs more than the Opus premium).
Unindexed rows (R4/R5) never clear bars on score — they enter only as quota-fallbacks below, never as primaries.

## Effort map (per agent, never global)

| Size | claude-code `--effort` | codex `model_reasoning_effort` | muse | opencode | cursor-agent |
|---|---|---|---|---|---|
| S | low | low | low | deepseek-v4.1-flash-free | effort is inside the model id; pin exact id |
| M | medium | medium | medium | deepseek-v4.1-flash-free | same |
| L | high | high | high (provisional) | not eligible (small models) | same |
| XL | max (high if 5hr LOW) | not eligible | max (provisional) | not eligible | same |

## Lookup: size x quota x installed

Primary -> fallback -> emergency (different provider):

| Size | Primary | Fallback | Emergency |
|---|---|---|---|
| S | R3 codex low (4% used) | R4 muse low (cheap-smart) | R5 opencode free, then R2 claude low, then cursor pinned cheapest |
| M | R3 codex medium | R2 claude medium | R4 muse medium, then R5 opencode free, then cursor pinned mid |
| L | R2 claude high | R3 codex high | cursor pinned top (quota 99% headroom); R4 muse high provisional only |
| XL | R1 claude max | R2 claude high + `XL_degraded` warning | none: return `defer` |

`--self-agent` (the caller) jumps the queue among qualifying rows: prefer self, it keeps context and burns one pool.

## Quota states (measured 2026-11-16, no est rows left)

Weekly checked first: OK >= 0.5, LOW 0.2-0.5, RESERVE < 0.2 (skipped except S). Then 5hr: RESERVE < 0.2 skips the provider; LOW downgrades one effort level. Keep ~20% of weekly in reserve. 429/quota error marks that provider RESERVE for its window and repicks cross-provider (claude-chat == claude-code pool; chatgpt == codex pool). Max 1 escalation per task (different provider or +1 size); 2nd failure returns `human`.

Ledger (measured 2026-11-16):
`{"claude": {"wk": 1.0, "h5": 0.98, "src": "measured-/usage"}, "codex": {"monthly": 0.96, "reset": "Dec-10", "recharge": "off", "resets_available": 0, "src": "metered-screenshot"}, "cursor": {"models": 0.99, "other": 0.99, "grokbot": 1.0, "src": "measured-dashboard"}, "opencode": {"free": "unpublished-shared-daily-throttled-TPM", "ctx": "200K", "src": "vendor-table-screenshot"}, "muse": {"quota": "api-key-metered-no-pool", "src": "user-GT"}}`. Re-verify weekly; predicted-vs-actual burn refit continues per task.

## Subscription limits (docs + live reads 2026-11-16)

- Claude Pro (annual to 13-Mar-2027): rolling 5hr session + weekly all-model cap, one pool for chat + Code. Measured: session 2% (reset Nov 17 9:39 IST), weekly 0%, Fable 0%. Check `/usage`.
- Codex on ChatGPT Free plan — METERED 2026-11-16 (screenshot): Agentic usage limit 96% remaining, resets December 10; no limit resets available; automatic recharge OFF. Caps NOT publicly specified (ChatGPT: no fixed daily/weekly; 5hr account-specific, Cloud not included). No non-interactive CLI readout (`/status` TUI-only, `doctor` quota-blind). Named `--model` rejected on ChatGPT logins; default = gpt-6-chat-thinking (priority:1, no user override).
- Cursor LEGACY Pro $20/mo (dashboard bills monthly, reset Nov 17; annual-to-Feb-2027 note stands): two monthly pools — Cursor Models 1%, Other Models 1% measured. NO published multiplier table (searched 2026-11-16: docs confirm "model selection affects burn rate" but publish no legacy draw-rate table; pool $ size unpublished, dashboard shows % only). Third-party billed at API list price (docs table); Max Mode +20% on legacy. Rule: pinned-cheapest, Composer/Grok end first.
- OpenCode v2.3.0 (free): login-free `opencode/*-free` incl. deepseek-v4.1-flash-free (probe OK exit 0, 0 creds). Free tier: unpublished shared daily quota, 200K ctx, throttled TPM, resets daily (vendor table, user screenshot 2026-11-16).
- OpenRouter (sizing + paid fallback): key valid; elephant-1 Decisions 200 ($0.000004/probe). Cap $10/point; per-task ceiling on card.
- Muse 1.4.11 (muse-spark-1.3 contributor): headless exec verified; untrusted-workspace delegation caveat. Quota: API-key metered, no pool (user-GT 2026-11-16).

## Probe evidence (ran 2026-11-16)

- `claude --version` = 2.1.322; `claude -p /usage` = session 2%, weekly 0%/0% (7d 160 req/22 sess).
- `cursor-agent --version` = 2026.11.13; logged in shridhar@counselio.ai; dashboard screenshot = LEGACY Pro $20/mo, pools 1%/1%/0%. Docs sweep 2026-11-16 (cursor.com/docs/models-and-pricing, usage-limits, stackfreeks, planyield): legacy = two monthly pools; third-party at API list price; Max +20%; NO published per-model multiplier table — closed as document-with-API-ladder, not unknowable.
- `codex --version` = 0.167.0 (0.169.0 available, not installed); ChatGPT login; `codex debug models` priority:1 = gpt-6-chat-thinking; config sets no model key; exec OK (3.5k tokens, model-silent output).
- `opencode --version` = v2.3.0 at ~/.opencode/bin (v1 removed); free probe OK login-free; 13+ free models; local ollama/coder-7b-q6k visible in catalog. Free-tier limits: unpublished shared daily quota, 200K ctx, throttled TPM, resets daily (vendor table via screenshot 2026-11-16).
- `muse` = 1.4.11; `model-profile show muse-spark-1.3` OK (reasoning high); headless exec OK.
- OpenRouter: key valid (200/435); elephant-1 sizing probe S@0.92, $0.000004. Priced fallbacks 2026-11-16: glm-5.3-flash ~$0.04/M in, qwen3.7-flash ~$0.03/M in.
- Downgrade guards verified live 2026-11-16: route.py S with claude-h5 LOW → codex; M with claude-wk RESERVE → codex (reroutes cleanly, no crash).
- Owed: cursor per-model multipliers (none shown — closed as pinned-cheapest); codex interactive model-name glance (optional).

## local-llm boundary

coder-3b-q8 default, coder-7b-q6k harder; ~5 tok/s, 100-token cap. Jobs: commit messages, PR titles, log summaries <=100 tokens, golden-set labelling drafts. Never code, never on a fallback path.

## Spread rule (batches)

A single provider taking every ticket is a quota concentration risk (one pool drains, one outage blocks all). After 2 picks land on one provider in a batch, route the rest with `--avoid-agent <id>` so they prefer a different qualifying provider. The script honors avoids only while an alternative row stays actionable (clears the size bar, model pinned, multiplier <= 2x); otherwise it logs `spread_overridden_no_alternative` and uses the best row. Never invent an unqualified row to satisfy spread.

## Audit line (JSONL, append-only, no text/secrets/code)

`ts, spec_sha256, router_v, table_v, engine(+provider/version/prompt_sha), choice, score{risk,ambiguity,touch,tests}, noul, bumped, final_size, pick{agent,model,effort,row}, rejected[{row,why}], quota_before(src measured|dated-GT), outcome(pass/fail = tests pass), escalations, wall_s, outcome`. Caller appends the outcome line under the same spec_sha256. Weekly: predicted size vs actual escalations.
