# Confidence Model — 4D Decomposition

## Overview

Every signal gets a **4-dimensional confidence breakdown**, not a single score.

```
final_confidence = 0.35 × thesis + 0.30 × timing + 0.20 × execution + 0.15 × data - penalties
```

## Dimensions

### 1. Thesis Confidence (35%)

_Is the fundamental/technical case sound?_

- setup_quality × 0.4 + sector_fit × 0.3 + leader_fit × 0.3
- Boost: Leader in acceleration stage (+0.1)

### 2. Timing Confidence (30%)

_Is the timing right for entry?_

- timing_fit × 0.5 + stage_fit × 0.3 + regime_fit × 0.2
- Penalty: Climax stage (×0.7)

### 3. Execution Confidence (20%)

_Can the trade be executed cleanly?_

- execution_fit × 0.5 + risk_fit × 0.5
- Penalty: Wide ATR >4% (×0.8)

### 4. Data Confidence (15%)

_How reliable is the underlying data?_

- Base by freshness: live=0.9, delayed=0.6, stale=0.3
- Volume ratio confirms quality

## Penalties

| Condition              | Penalty   | Reason                |
| ---------------------- | --------- | --------------------- |
| Evidence conflicts     | 0.05 each | Contradictory signals |
| High score, bad regime | 0.10      | Capped confidence     |
| Theme late-stage       | 0.15      | Distribution risk     |

## Labels

| Confidence | Label     |
| ---------- | --------- |
| ≥ 0.80     | VERY_HIGH |
| ≥ 0.65     | HIGH      |
| ≥ 0.45     | MODERATE  |
| ≥ 0.25     | LOW       |
| < 0.25     | VERY_LOW  |

## Evidence Conflict Engine

Separately analyzes bullish vs bearish evidence:

| Conflict Level | Score   | Effect             |
| -------------- | ------- | ------------------ |
| LOW            | < 0.3   | No penalty         |
| MEDIUM         | 0.3-0.5 | -0.5 score penalty |
| HIGH           | 0.5-0.7 | -1.5 score penalty |
| EXTREME        | ≥ 0.7   | -2.5 score penalty |

## Display (Dashboard)

Don't show: `Confidence: 72%`

Show:

```
Thesis:    Strong  (86%)
Timing:    Weak    (52%)
Execution: Good    (79%)
Data:      High    (90%)
Final:     72% (Grade B)
Decision:  Watch / Pilot Size
Conflict:  Medium — 3 bearish vs 4 bullish signals
```

## Files

- `src/engines/confidence_engine.py` — Core 4D computation
- `src/engines/evidence_conflict.py` — Conflict detection
- `src/engines/fit_scorer.py` — Component scores feeding confidence
