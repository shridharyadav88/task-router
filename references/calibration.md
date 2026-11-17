# Calibration v1 (30 golden tasks, 2026-11-14)

Both engines scored all 30 specs (elephant $0.000544 total; Jev free). Fitted by grid search maximizing final-size agreement (Choice + risk-bump max 1 step + vague->clarify).

## Headline fits

| Engine | Choice agree | Vague gate | Risk theta | Final agree |
|---|---|---|---|---|
| elephant-9b | 23/30 | noul >= 0.5 (clean max 0.32, trap 0.89) | 1.65 | 26/30 |
| Jev 1.14 | 19/30 direct | yes-prob >= 0.8 (clean 0.35-0.74, trap 0.85) | 1.85 | 24/30 |

Plateaus: elephant theta 1.6-1.7, Jev theta 1.80-1.90. Old theta 0.7 was WRONG SCALE (0-1 assumed, engines emit 0-3): at 0.7 nearly every S task would have bumped.

## What the bump rule catches

Risk-bump fires exactly on L3 (1.94/1.94), L4 (2.48/1.8), L5 (2.58/1.82) and nowhere else at fitted thetas (nearest clean: M10 1.70 Jev, S8 1.22 elephant — thin margins, logged). No false bumps across 30.

## Residual misses (all Choice overshoot/undershoot — bump can't fix by design, never down)

- Jev reads one size high on M5, M6, M8, M9, M11 and L8 reads XL (low conf 0.25 except M8 0.84 — confidence does NOT discriminate; queued for human adjudication, may be label noise).
- Elephant undershoots L1, L4, L5, L7 to M (fixed by bump where risk allows: L4/L5; L1/L7 stay wrong — risk 0.71/1.16 below theta) and M2 to S; M6 overshoots to L.
- L1-touch reading discarded (malformed question in run script, confidence 0.19).

## Design changes from calibration

1. Bump signal = risk ONLY. tests-missing must never bump (S6 README tests 2.19 / S7 2.22 would false-bump a doc task).
2. Vague gates per-engine (elephant 0.5, Jev 0.8); combined verdict uses max.
3. Specs need the context footer (task + repo + done-criterion): bare one-liners score vague-hot on elephant (T1-terse 0.656 -> clarify).
4. M12 clarify-trap passes on both engines (elephant 0.889, Jev 0.85).

## Queued

- Human adjudication of the 11 Choice-miss tasks (label noise vs engine bias).
- T5a/T5b split. Elephant switch-on as default sizer with fitted theta (done in size.py: `--theta 1.65`; Jev callers use 1.85).
