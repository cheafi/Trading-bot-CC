# Sector Logic — Architecture & Rules

## Overview

Every signal passes through the **Sector-Adaptive Decision Pipeline**:

```
Signal → Classify → Fit Score → Sector Adjust → Conflict Check → Confidence → Decision → Explain → Rank → Deliver
```

## Sector Buckets

| Bucket      | Examples        | Benchmark    | Key Drivers                       |
| ----------- | --------------- | ------------ | --------------------------------- |
| HIGH_GROWTH | NVDA, MSFT, CRM | QQQ/SOXX/IGV | Growth, innovation, AI narrative  |
| CYCLICAL    | XOM, NEM, CAT   | XLE/GDX/XLI  | Commodity, macro, rates, USD      |
| DEFENSIVE   | JNJ, NEE, PG    | XLV/XLU/XLP  | Rotation, VIX, yield, quality     |
| THEME_HYPE  | GME, MSTR, IONQ | SPY/BITO     | Sentiment, social heat, meme flow |

## Sector Stages

| Stage        | Meaning             | Score Impact |
| ------------ | ------------------- | ------------ |
| LAUNCH       | Early accumulation  | 6-7          |
| ACCELERATION | Momentum building   | 8.5 (best)   |
| CLIMAX       | Peak euphoria       | 4-5.5        |
| DISTRIBUTION | Smart money exiting | 2 (avoid)    |

## Leader Status

| Status         | Score Impact | Action Override         |
| -------------- | ------------ | ----------------------- |
| LEADER         | 9.0          | Full conviction allowed |
| EARLY_FOLLOWER | 6.5          | Normal sizing           |
| LAGGARD        | 3.0          | Downgrade TRADE→WATCH   |

## Sector-Specific Logic Packs

### HIGH_GROWTH

- **Boost**: Leader in acceleration, strong RS vs QQQ
- **Warn**: Crowding >0.6, climax volume + overbought, laggard chasing, >20% above 50MA
- **Channel**: `#growth-ai`

### CYCLICAL

- **Emphasize**: Commodity futures alignment, macro cycle, EMA 21/50
- **Warn**: Futures divergence (-1.5 score), wide ATR, weekend geo risk
- **Channel**: `#cyclical-macro`

### DEFENSIVE

- **Boost**: High VIX → defensive rotation opportunity
- **Warn**: Yield trap (high yield + bad balance sheet), overbought defensive
- **Channel**: `#defensive-rotation`

### THEME_HYPE

- **Phase-aware**: LAUNCH→bullish, ACCELERATION→boost, CLIMAX→caution(-1.0), DISTRIBUTION→avoid(-3.0)
- **Warn**: Leader weakening, laggard at climax(-2.0), social heat >80
- **Channel**: `#theme-speculation`

## Fit Scoring Weights (by sector)

| Factor        | HIGH_GROWTH | CYCLICAL | DEFENSIVE | THEME_HYPE |
| ------------- | ----------- | -------- | --------- | ---------- |
| setup_quality | 0.15        | 0.18     | 0.18      | 0.12       |
| sector_fit    | 0.20        | 0.14     | 0.12      | 0.15       |
| regime_fit    | 0.15        | 0.20     | 0.15      | 0.12       |
| stage_fit     | 0.13        | 0.10     | 0.08      | 0.20       |
| leader_fit    | 0.15        | 0.08     | 0.07      | 0.15       |
| timing_fit    | 0.08        | 0.15     | 0.10      | 0.15       |
| risk_fit      | 0.09        | 0.10     | 0.18      | 0.06       |
| execution_fit | 0.05        | 0.05     | 0.12      | 0.05       |

## Files

| File                                | Purpose                             |
| ----------------------------------- | ----------------------------------- |
| `src/engines/sector_classifier.py`  | Ticker → bucket + stage + leader    |
| `src/engines/fit_scorer.py`         | 8-factor weighted scoring           |
| `src/engines/sector_logic_packs.py` | Sector-specific adjustments         |
| `src/engines/confidence_engine.py`  | 4D confidence decomposition         |
| `src/engines/evidence_conflict.py`  | Conflict detection + alternatives   |
| `src/engines/decision_mapper.py`    | Score+confidence → action           |
| `src/engines/explainer.py`          | why_now / why_not / invalidation    |
| `src/engines/vcp_intelligence.py`   | 4-layer VCP analysis                |
| `src/engines/scanner_matrix.py`     | 20+ scanners in 5 categories        |
| `src/engines/multi_ranker.py`       | Discovery/Action/Conviction ranking |
| `src/engines/sector_pipeline.py`    | Full orchestration                  |
