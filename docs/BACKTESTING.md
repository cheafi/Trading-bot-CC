# Backtesting & Strategy AI

> How the AI backtest engine works — architecture, commands, and self-learning mechanism.

---

## Overview

`src/engines/strategy_optimizer.py` (936 lines) is a fully self-contained AI backtesting engine. It:

1. **Simulates** 4 strategy families on real price history (yfinance)
2. **Validates** each strategy with walk-forward out-of-sample testing
3. **Sweeps** 81 parameter combinations to find robust settings
4. **Cross-checks** whether multiple strategies agree
5. **Stress-tests** with 500 Monte Carlo simulations
6. **Self-corrects** based on live signal accuracy vs backtest win rate
7. **Detects** which of 9 market regimes the stock is currently in
8. **Ranks** all 4 strategies and recommends the best fit

The singleton `get_optimizer()` is shared across all Discord commands and the `auto_strategy_learn` background task.

---

## 4 Simulated Strategies

### SWING
```
Entry:  Price touches SMA20 from above · RSI 40–55 · declining pullback volume
Exit:   Price reaches prior swing high · OR stop triggered
Stop:   Below SMA20 or most recent swing low
Hold:   5–15 days
```

### BREAKOUT
```
Entry:  Price closes above multi-week range high · Volume > 1.5× avg · RSI 55–75
Exit:   Measured move complete · OR stop triggered
Stop:   Below the base (consolidation low)
Hold:   10–30 days
```

### MOMENTUM
```
Entry:  EMA9 crosses above EMA21 · ADX > 25 · Relative strength top quartile
Exit:   EMA9 crosses below EMA21 (trailing)
Stop:   Below EMA21
Hold:   1–8 weeks (trailing)
```

### MEAN_REVERSION
```
Entry:  Price at lower Bollinger Band (−2σ) · RSI < 35 · Price > SMA200
Exit:   Price reaches SMA20 (midline)
Stop:   Below the recent swing low (give up on the bounce)
Hold:   2–7 days
```

---

## 9 Market Regimes

```python
REGIMES = [
    "bull_trending",          # steady uptrend, moderate volatility
    "bull_choppy",            # upward bias but whippy price action
    "bear_trending",          # steady downtrend
    "bear_choppy",            # downward bias + noise
    "high_volatility",        # large daily swings, VIX-like expansion
    "low_volatility",         # tight range, ADX falling, BB squeeze
    "sideways",               # no directional bias
    "breakout_environment",   # multiple stocks breaking resistance
    "mean_reversion_environment"  # repeated reversals at extremes
]
```

Regime is detected per-ticker using:
- 20-day realised volatility (ATR/price)
- Directional bias (EMA20 vs price)
- ADX (trend strength)
- Bollinger Band width (squeeze vs expansion)
- Rolling return vs SPY

---

## Backtest Engine Flow

```
run_full_backtest(ticker, period)
  │
  ├── 1. Fetch OHLCV (yfinance, period)
  ├── 2. _detect_regime(prices) → regime + confidence
  │
  ├── 3. For each strategy in [SWING, BREAKOUT, MOMENTUM, MEAN_REVERSION]:
  │       │
  │       ├── _simulate_strategy(prices, params, strategy_type)
  │       │     → trades list: [(entry_price, exit_price, return_pct), ...]
  │       │
  │       ├── _walk_forward_backtest(prices, strategy_type)
  │       │     → train_win_rate, oos_win_rate, oos_degradation
  │       │
  │       ├── _parameter_sweep(prices, strategy_type)
  │       │     → best_params, param_stability
  │       │
  │       ├── _cross_check(prices, strategy_type)
  │       │     → cross_check_score
  │       │
  │       ├── _monte_carlo(prices, trades, n=500)
  │       │     → mc_mean, mc_5th, mc_95th
  │       │
  │       ├── _get_correction_multiplier(strategy_type)
  │       │     → correction_multiplier (0.6–1.4)
  │       │
  │       └── final_score = raw_score × correction_multiplier
  │
  └── Sort by final_score → BacktestReport
```

---

## Walk-Forward Validation

Prevents overfitting by testing on unseen data.

```
Full price history (e.g. 252 trading days for "1y")

Fold 1:  [Train: 1–176]  [Test: 177–252]
Fold 2:  [Train: 1–132]  [Test: 133–176]
Fold 3:  [Train: 1–88]   [Test: 89–132]
Fold 4:  [Train: 1–44]   [Test: 45–88]

Average OOS win rate across 4 folds = out-of-sample estimate
OOS degradation = train_win_rate - oos_win_rate

Good: degradation < 10%
Warning: degradation 10–20%
Poor: degradation > 20%
```

---

## Parameter Sweep (81 Combinations)

Tests all combinations of:

| Parameter | Values Tested |
|-----------|--------------|
| `rsi_period` | 9, 14, 21 |
| `sma_period` | 20, 50, 100 |
| `vol_multiplier` | 1.2, 1.5, 2.0 |

3 × 3 × 3 = **27** combinations per strategy fold × 3 folds = **81 total** evaluations.

The winning parameter set is the one with highest OOS win rate. **Param stability** is the percentage of top-10 param sets that share the same direction (e.g. "all top sets prefer RSI 14"). High stability (> 70) means the strategy is robust, not overfit to one specific setting.

---

## Self-Correction Mechanism

The optimizer tracks every signal's outcome:

```
When a signal fires (e.g. BREAKOUT on NVDA):
  → Log: { ticker, strategy, entry, stop, target, timestamp }

After 10 trading days:
  → Check: did price hit target before stop?
  → Record: WIN or LOSS

Every 6 hours (auto_strategy_learn):
  → Compute live accuracy = wins / (wins + losses)
  → Compare to backtest win rate
  → Update correction multiplier:
       if live_accuracy > backtest_win_rate + 0.10 → multiplier ×1.4
       if live_accuracy > backtest_win_rate + 0.05 → multiplier ×1.2
       if within ±5%                               → multiplier ×1.0
       if live_accuracy < backtest_win_rate - 0.10 → multiplier ×0.8
       if live_accuracy < backtest_win_rate - 0.20 → multiplier ×0.6
```

This means if a strategy is performing better than backtested, its scores are boosted. If it's under-performing, scores are reduced — protecting you from over-trusting a degraded model.

Use `/strategy_report` to see the current correction state.

---

## Monte Carlo Stress Testing

500 simulation runs per strategy:

```
For each run:
  1. Take the actual list of trade returns from backtest
  2. Randomly shuffle the order (randomise entry sequence)
  3. Simulate equity curve
  4. Record total return

Result: distribution of 500 outcomes
  5th percentile  → worst-case realistic outcome
  50th percentile → median expected outcome
  95th percentile → best-case realistic outcome
```

A strategy that shows −30% at the 5th percentile despite a positive mean is riskier than one showing −5% at the 5th percentile.

---

## Discord Commands

### `/backtest TICKER [PERIOD]`
Full AI backtest. `PERIOD` defaults to `1y`. Options: `6mo`, `1y`, `2y`.

Output sections:
1. **Regime** — detected regime + confidence %
2. **Strategy Ranking** — all 4 strategies sorted by final score
3. **Best Strategy** — recommendation with reasoning
4. **Walk-Forward** — train vs OOS win rates with degradation flag
5. **Monte Carlo** — 5th / 50th / 95th percentile returns
6. **Best Params** — optimal RSI/SMA/VolMult settings
7. **Param Stability** — how robust is the optimal setting?
8. **Cross-Check** — do other strategies support the thesis?

### `/best_strategy TICKER`
Fast 6-month scan. Returns:
- Current regime
- Best-fit strategy name
- Score and win rate
- One-line reasoning

Best used as a quick pre-trade check.

### `/strategy_report`
Self-learning accuracy dashboard. Returns for each of the 4 strategies:
- Signals posted (count)
- Win rate (live)
- Backtest win rate (reference)
- Gap (over/under performing)
- Current correction multiplier
- Last 5 correction log entries with dates and reasons

---

## Auto-Learning Task

`auto_strategy_learn` (every 6 hours, weekdays only) automatically:

1. Picks 5 random stocks from the 50-stock universe
2. Runs `run_full_backtest()` on each with 1y period
3. Updates the accuracy log with any matured trade outcomes
4. Recalculates correction multipliers
5. Posts a summary to `#ai-signals`:

```
🤖 AI STRATEGY LEARN — Auto Update

5 stocks analysed: NVDA, AAPL, TSLA, MSFT, AMD
Best overall: BREAKOUT (avg score 71)

SELF-CORRECTION UPDATE:
  BREAKOUT    live 58% vs BT 55% → ×1.2 (slight outperform)
  MOMENTUM    live 41% vs BT 52% → ×0.8 (underperforming)
  SWING       live 50% vs BT 49% → ×1.0 (on track)
  MEAN_REV    live 44% vs BT 46% → ×1.0 (on track)

Optimizer confidence: HIGH
```

---

## Regime × Strategy Matrix

Strategy scores are boosted or penalised based on regime fit:

| Regime | SWING | BREAKOUT | MOMENTUM | MEAN_REV |
|--------|-------|----------|----------|----------|
| `bull_trending` | +10 | +15 | +15 | −5 |
| `bull_choppy` | +15 | +5 | 0 | +5 |
| `bear_trending` | −15 | −15 | −15 | +10 |
| `bear_choppy` | −10 | −15 | −15 | +5 |
| `high_volatility` | −10 | 0 | +5 | 0 |
| `low_volatility` | +5 | +10 | 0 | +10 |
| `sideways` | 0 | −5 | −10 | +15 |
| `breakout_environment` | 0 | +20 | +10 | −10 |
| `mean_reversion_env` | +5 | −15 | −10 | +20 |

---

Back to [README.md](../README.md)
