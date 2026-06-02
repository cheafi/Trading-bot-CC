# Nison Candlestick & Context Upgrade

**Single-book mode:** 《日本蜡烛图技术新解（典藏版）》 — Steve Nison principles only.

Clarity Console (CC) is being shifted from a **signal-heavy dashboard** to a **candlestick-and-context trading system** where pattern names are clues, not orders.

---

## 1. Product diagnosis

### Already aligned (keep)

| Area                                                        | Why it fits Nison                                |
| ----------------------------------------------------------- | ------------------------------------------------ |
| `live_dossier` support/resistance + MA stack                | Location and macro trend context exist           |
| `trade_plan` stop / invalidation / R:R                      | Risk-first geometry partially present            |
| `decision_truth_model` R:R gates (2.5 TRADE, 2.0 execution) | Weak R:R = no full-size trade                    |
| Board WAIT / regime gate                                    | Macro first — page gate overrides isolated cards |
| `random_walk_guardrails`                                    | Detection ≠ permission; humility layer           |
| Dossier unified decision + entry/stop/T1/T2                 | Execution framing with invalidation text         |

### Violates or conflicts (fix via this upgrade)

| Area                            | Gap                                         | Remedy                                          |
| ------------------------------- | ------------------------------------------- | ----------------------------------------------- |
| Scanner matrix PATTERN category | Score threshold = actionable                | Demote until `candlestick_context` checked      |
| Playbook rows                   | Pattern/strategy tags without context score | Add `nison_*` tags via `enrich_opportunity_row` |
| Dossier technicals tab          | RSI/MACD tiles without location narrative   | New **Candlestick & Context** block             |
| `why_buy` heuristics            | Indicator-led, not candle+location          | Route through `candlestick_analysis.pattern`    |
| Discovery hub                   | “Open dossier” on high scanner score alone  | `nison_demoted` + context label                 |

### Too signal-driven (demote, do not delete)

- Raw scanner score ≥ 7.5 → “actionable” without stop/context
- RSI/MACD factor chips as primary bull case
- VCP / breakout scanner headlines without macro backdrop
- Options flow grades as trade triggers
- AI dossier commentary when geometry weak

### Demote (label, don’t remove)

- Scanner PATTERN hits → **context check pending — monitor only**
- Mean-reversion RSI bounce without support proximity
- Momentum surge without trend alignment score ≥ 55
- Pilot/TRADE rows with `rr_below_trade_threshold`

### Upgrade (this pass)

- `candlestick_context.py` — six scores + composite labels
- `macro_trend.py` — MA stack + regime + chart-method stubs
- Dossier `candlestick_analysis` block + UI section
- Playbook row tags (`pattern_tag`, `context_tag`, `rr_tag`, `trend_tag`)
- Scanner `enrich_hit_for_ui` Nison metadata
- Dashboard optional `macro_trend_strip` on decision hub

---

## 2. New architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MACRO TREND ENGINE                       │
│  macro_trend.py — MA stack, regime, trendline/3LB/Renko stub │
└──────────────────────────┬──────────────────────────────────┘
                           │ backdrop
┌──────────────────────────▼──────────────────────────────────┐
│              PATTERN QUALITY ENGINE (heuristic)              │
│  RSI+support, MACD+volume, trend continuation — NOT 20 new   │
│  OHLC detectors; detection flagged is_heuristic=true         │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│           PATTERN CONTEXT ENGINE (primary weight)             │
│  Support/resistance distance, macro bias vs pattern direction │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│              RISK / REWARD ENGINE                             │
│  stop present, R:R ≥ 2.0 gate, support distance geometry      │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│     THESIS INVALIDATION / MARKET CHAMELEON                    │
│  chameleon_rule, upgrade_breaks — adapt when level breaks     │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│     DETECTION vs JUDGMENT                                   │
│  detection_vs_judgment: { detected, judgment, note }          │
└─────────────────────────────────────────────────────────────┘
```

### Module map

| Engine                | Module                                | Status                                      |
| --------------------- | ------------------------------------- | ------------------------------------------- |
| Macro trend           | `src/services/macro_trend.py`         | Implemented (stubs for 3LB/Renko/trendline) |
| Pattern quality       | `src/services/candlestick_context.py` | Heuristic from existing technicals          |
| Pattern context       | same                                  | Weighted above pattern name                 |
| Risk/reward           | same                                  | `score_risk_geometry` + gates               |
| Chameleon             | same                                  | `build_chameleon_rule`, `upgrade_breaks`    |
| Detection vs judgment | same                                  | `detection_vs_judgment` block               |

---

## 3. Score design

All scores 0–100. **Context and risk outweigh pattern quality.**

| Score                             | Meaning                        | Primary inputs                                         |
| --------------------------------- | ------------------------------ | ------------------------------------------------------ |
| Pattern Quality                   | Candle clue strength           | RSI zone, MACD, volume ratio, heuristic name           |
| Pattern Context                   | **Most important**             | Support/resistance distance, macro bias, regime        |
| Risk Geometry                     | Stop + R:R + support tightness | `trade_plan`, unified decision                         |
| Trend Alignment                   | Pattern vs macro trend         | `macro_trend.assess_macro_trend`                       |
| Invalidation Clarity              | Explicit break level           | Invalidation text, stop, support reference             |
| Execution Readiness (candlestick) | Composite deploy bar           | Context 30%, risk 25%, trend 20%, inv 15%, pattern 10% |

### Composite output labels

| Condition                          | Label                                       |
| ---------------------------------- | ------------------------------------------- |
| Pattern ≥55, context ≥55, exec ≥60 | **Strong pattern, strong context**          |
| Pattern ≥55, context <55           | **Pattern present, context weak**           |
| Pattern ≥55, exec <45              | **Strong candle, poor geometry**            |
| Pattern ≥50, low exec              | **Pattern present, not actionable**         |
| Reversal heuristic                 | **Reversal clue, not yet a trade**          |
| Bull pattern + bear macro          | **Bullish pattern inside bearish backdrop** |
| Invalidation hit (operator)        | **Thesis invalidated — adapt to market**    |

### Execution status (candlestick-specific)

- `ACTIONABLE` — exec ≥65, stop set, R:R ≥ 2.0
- `WATCH_FOR_TRIGGER` — exec ≥45, stop set
- `PATTERN_ONLY` — pattern detected, geometry/context insufficient
- `NOT_ACTIONABLE` — default

Distinct from `src/services/execution_readiness.py` (broker/handoff readiness).

---

## 4. Integrations (highest ROI)

### Dossier — `stock_intel.py`

Payload key: `candlestick_analysis` with sections:

- Pattern, Location, Macro backdrop, Stop/invalidation, R:R
- What upgrades/breaks it, Chameleon rule, Execution status

### Playbook — `decision_truth_model.enrich_opportunity_row`

Row fields:

- `nison_pattern_tag`, `nison_context_label`, `nison_rr_tag`, `nison_trend_tag`
- `nison_execution_status`, `nison_humility`

### Dashboard — `decision_hub.py`

Optional `macro_trend_strip` from cached `market_regime`.

### Discovery — `scanner_matrix.enrich_hit_for_ui`

- `nison_context_label`, `nison_demoted`, `nison_demote_reason`

### UI — `index.html`

Collapsible **Candlestick & Context** after Decision stack.

### Copy — `humility_labels.py` + `NISON_LABELS`

Nison-specific operator strings merged into guardrail vocabulary.

---

## 5. Copy style (Nison labels)

Canonical strings in `candlestick_context.NISON_LABELS`:

- pattern present, context weak
- reversal clue, not yet a trade
- location strengthens the signal
- strong candle, poor geometry
- bullish pattern inside bearish backdrop
- thesis invalidated — adapt to market
- detection ≠ judgment — verify context
- no stop = no trade
- weak R:R = no trade

---

## 6. Constraints honored

- No 20 new pattern detectors — heuristics from RSI, trend, S/R, volume
- Existing WAIT / page gate / Random Walk guardrails unchanged
- `flow_decision_surface._MOCK_WARNING` already updated (restart API if stale UI)
- IBKR contradictory READY states — deferred unless trivial

---

## 7. File-by-file plan

| File                                   | Action                                                |
| -------------------------------------- | ----------------------------------------------------- |
| `docs/NISON_CANDLESTICK_UPGRADE.md`    | This document                                         |
| `src/services/candlestick_context.py`  | **NEW** — scores, labels, dossier block builder       |
| `src/services/macro_trend.py`          | **NEW** — macro trend + market strip                  |
| `src/services/stock_intel.py`          | Wire `candlestick_analysis` in `_build_intel_payload` |
| `src/services/decision_truth_model.py` | Nison tags in `enrich_opportunity_row`                |
| `src/services/humility_labels.py`      | Re-export Nison keys; merge in playbook labels        |
| `src/services/decision_hub.py`         | `macro_trend_strip` field                             |
| `src/engines/scanner_matrix.py`        | Nison demotion in `enrich_hit_for_ui`                 |
| `src/api/templates/index.html`         | Dossier UI section + dashboard strip                  |
| `tests/test_candlestick_context.py`    | **NEW** — unit tests                                  |

### Deferred (future passes)

- Full OHLC candlestick pattern library (hammer body/wick ratios)
- Three-line break / Renko from daily bar store
- Trendline auto-draw on dossier chart
- IBKR session 1100 vs READY reconciliation
- Backtest calibration of context score weights

---

## 8. Operator workflow (Nison)

1. Read **macro backdrop** (regime + MA stack)
2. Ask **where** price sits vs support/resistance — not just pattern name
3. Require **stop + invalidation** before size
4. Check **R:R geometry** — weak geometry demotes to watch
5. Treat scanner hits as **detection**; dossier context as **judgment**
6. When invalidation breaks → **chameleon rule** — adapt, don’t defend

---

_Last updated: implementation pass for CC Nison upgrade._
