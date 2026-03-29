# Trading Methodology

> How TradingAI Bot makes decisions — from signal to execution.

## 1. Signal Generation

Each engine cycle:
1. **Universe scan** — `UniverseBuilder` selects 500+ tickers across US, HK, JP, and crypto markets using a 3-stage pipeline (source → filter → prioritise).
2. **Strategy signals** — 8 registered strategies run independently: `momentum_breakout`, `vcp`, `mean_reversion`, `trend_following`, `short_term_trend_following`, `classic_swing`, `momentum_rotation`, `short_term_mean_reversion`.
3. **Signal validation** — Each signal includes entry/stop/target prices, confidence (0–100), and catalyst text.

## 2. Edge Calibration

The `EdgeCalculator` assigns calibrated probabilities to each signal:
- **P(T1)** — probability of hitting first profit target
- **P(stop)** — probability of hitting stop loss
- **EV** — expected value as a percentage
- **MAE** — maximum adverse excursion (worst drawdown before target)

Probabilities use **base-rate priors** per strategy, adjusted for:
- Current market regime (risk-on boosts, risk-off penalises)
- Volatility regime (high-vol widens MAE estimates)
- Volume confirmation (relative volume ≥ 2× boosts P(T1))

When 30+ calibration samples exist, empirical data replaces priors.

## 3. Regime Classification

The `RegimeRouter` classifies the market into 5 derived labels:
- **Risk regime** — risk_on / neutral / risk_off
- **Trend regime** — strong_uptrend / uptrend / range_bound / downtrend / strong_downtrend
- **Volatility regime** — low_vol / normal / high_vol / extreme_vol
- **Composite regime** — e.g. `risk_on_uptrend`, `crisis`, `high_entropy`
- **Trade gate** — should_trade boolean with reason

The regime controls sizing (via `size_scalar`: crisis=0, normal=1.0) and which strategies are favoured.

## 4. Ensemble Scoring

`OpportunityEnsembler` ranks all signals using 8 weighted components:

| Component | Weight | Source |
|-----------|--------|--------|
| Net expectancy | 30% | Signed EV from EdgeCalculator |
| Calibrated P(win) | 15% | P(T1) from EdgeCalculator |
| Expected R | 10% | Expected return / risk |
| Regime fit | 15% | Strategy × regime affinity |
| Strategy health | 10% | Leaderboard score (Bayesian) |
| Timing quality | 5% | Time of day, market session |
| Risk/reward | 10% | Entry → target / entry → stop |
| Conviction bonus | 5% | Multi-strategy agreement |

**Suppression rules** eliminate setups with:
- Composite score < 0.35
- Earnings within 48 hours
- Excessive sector concentration
- Signal cooldown / anti-flip violations

## 5. Position Sizing

7 multiplicative factors determine final size:
1. **Confidence multiplier** (signal confidence / 100)
2. **Regime multiplier** (size_scalar from RegimeState)
3. **Strategy health** (from leaderboard)
4. **Volatility adjustment** (inverse of ATR ratio)
5. **Portfolio heat** (reduces when many positions open)
6. **Half-Kelly** (from P(win) and win/loss ratio)
7. **Budget multiplier** (from PortfolioRiskBudget constraints)

Budget checks enforce: max 5% single-name, 30% sector, 25% high-beta, 10% earnings-48h, max 15 positions.

## 6. Execution

- Paper broker with realistic slippage + commission models
- Support for LONG and SHORT directions
- Trailing stops with R-based profit targets
- Position monitoring runs every cycle (even during no-trade)

## 7. Learning Loop

After each closed trade:
- `TradeLearningLoop` records outcome with full entry snapshot
- `TradeOutcomePredictor` retrains every 20 trades (GBM classifier)
- Regression models predict expected R-multiple, MAE, and hold time
- `StrategyLeaderboard` updates with Bayesian shrinkage
- `MetaEnsemble` optimises ensemble weights from outcomes

## 8. Trust Layer

Every output includes `TrustMetadata`:
- **Badge** — LIVE / PAPER / BACKTEST / RESEARCH
- **Freshness** — FRESH / AGING / STALE
- **Model version** — e.g. v6.38
- **PnL breakdown** — gross → net (fees, slippage)
- **Attribution** — what worked / what failed

## 9. Output Modes

Users can set their preferred verbosity via `/mode`:
- **Quick** — ticker + direction + price only
- **Pro** — full card with scores, regime, trust
- **Explainer** — everything + why-now narrative, scenarios, risks

---

*This document is auto-generated from the codebase structure. v6.38*
