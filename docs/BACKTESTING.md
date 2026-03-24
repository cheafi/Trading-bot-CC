# 📊 Backtesting & Evaluation — TradingAI Bot v6

Framework for measuring whether strategies have a real edge.

---

## Why Backtesting Matters

The system runs 6 strategy families generating signals continuously. Backtesting answers:
- **Does the strategy work?** (positive expectancy after costs)
- **When does it work?** (which regimes, which markets)
- **How much risk?** (drawdown, consecutive losses, tail events)
- **Is it degrading?** (parameter decay, regime shift)

---

## Evaluation Metrics

### 📈 Return Metrics

| Metric | Formula | Good | Warning |
|--------|---------|:----:|:-------:|
| **Total Return** | End / Start - 1 | > benchmark | < 0 |
| **Annualized Return** | (1 + total)^(252/days) - 1 | > 15% | < 5% |
| **Sharpe Ratio** | (Return - Rf) / Volatility | > 1.0 | < 0.5 |
| **Sortino Ratio** | (Return - Rf) / Downside Dev | > 1.5 | < 0.7 |
| **Calmar Ratio** | Annual Return / Max Drawdown | > 1.0 | < 0.5 |

### 🎯 Trade Quality

| Metric | Formula | Good | Warning |
|--------|---------|:----:|:-------:|
| **Win Rate** | Wins / Total | > 50% | < 40% |
| **Payoff Ratio** | Avg Win / Avg Loss | > 1.5 | < 1.0 |
| **Profit Factor** | Gross Profit / Gross Loss | > 1.5 | < 1.0 |
| **Expectancy** | (Win% × AvgWin) - (Loss% × AvgLoss) | > 0.5% | < 0 |

### 🛡️ Risk Metrics

| Metric | Formula | Good | Warning |
|--------|---------|:----:|:-------:|
| **Max Drawdown** | Peak-to-trough decline | < 15% | > 25% |
| **VaR (95%)** | 5th percentile daily return | < 2% | > 3% |
| **CVaR (95%)** | Average loss beyond VaR | < 3% | > 5% |
| **Max Consecutive Losses** | Longest losing streak | < 6 | > 10 |

### ⚙️ Operational

| Metric | Purpose |
|--------|---------|
| **Average Holding Period** | Does it match strategy horizon? |
| **Turnover** | Transaction cost impact |
| **Slippage Sensitivity** | How much does 0.1% slip hurt? |
| **Ticker Concentration** | Over-exposed to one name? |
| **Regime Breakdown** | Returns by RISK_ON / NEUTRAL / RISK_OFF |

---

## Multi-Horizon Evaluation

### Short-Term (Days)

Test signals from: `auto_momentum_scan`, `realtime_price_alerts`, `opportunity_scanner`

| Measure | Method |
|---------|--------|
| Follow-through | Does a 3%+ spike lead to continuation? |
| Alert accuracy | Did price spikes correctly identify important moves? |
| Timing | Entry-to-peak latency |

### Medium-Term (Weeks)

Test signals from: `auto_swing_scan`, `auto_breakout_scan`, `auto_signal_scan`

| Measure | Method |
|---------|--------|
| Hit rate | Did score ≥ 75 signals reach their target? |
| R:R realized | Actual reward vs actual risk |
| Hold period | Did the expected hold window match reality? |

### Longer-Term (Months)

Test: Regime-driven allocation and portfolio-level behavior

| Measure | Method |
|---------|--------|
| Regime accuracy | Did RISK_OFF calls precede drawdowns? |
| Playbook alignment | Did strategy selection outperform static allocation? |
| Drawdown control | Was max drawdown reduced vs buy-and-hold? |

---

## Testing Framework

### Architecture

```
Historical Data (yfinance)
        │
        ▼
Feature Calculator (same as production)
        │
        ▼
Signal Generator (same rules, same thresholds)
        │
        ▼
Trade Simulator
├── Entry at signal price + slippage
├── Stop loss monitoring
├── Target exit logic
├── Time-based exit
└── Commission deduction
        │
        ▼
Results Analyzer
├── Per-strategy breakdown
├── Per-regime breakdown
├── Equity curve
├── Drawdown chart
└── Statistical significance tests
```

### Assumptions That Matter

| Assumption | Conservative Setting |
|-----------|---------------------|
| Slippage | 0.05–0.10% per trade |
| Commission | $1 per trade or 0.01% |
| Fill model | Next bar open (not intrabar) |
| Position sizing | Fixed fractional or Kelly-based |
| Look-ahead bias | None (strictly causal features) |
| Survivorship bias | Include delisted tickers if available |

---

## Walk-Forward Validation

```
┌────────┬────────┬────────┬────────┬────────┐
│ Train  │  Test  │ Train  │  Test  │ Train  │ ...
│ 6 mo   │ 1 mo   │ 6 mo   │ 1 mo   │ 6 mo   │
└────────┴────────┴────────┴────────┴────────┘

• Train on historical window → optimize parameters
• Test on out-of-sample window → measure real performance
• Roll forward → repeat
• Aggregate out-of-sample results → true backtest performance
```

---

## Common Pitfalls

| Pitfall | How to Avoid |
|---------|-------------|
| **Overfitting** | Walk-forward validation, keep rules simple |
| **Look-ahead bias** | Only use data available at signal time |
| **Survivorship bias** | Include delisted stocks if possible |
| **Ignoring costs** | Always deduct slippage + commissions |
| **Cherry-picking** | Report all strategies, not just the best one |
| **Regime blindness** | Segment results by RISK_ON / NEUTRAL / RISK_OFF |
| **Single-metric focus** | Don't optimize win rate alone; balance with drawdown + expectancy |

---

## Repo Components

| File | Lines | Purpose |
|------|------:|---------|
| `src/backtest/backtester.py` | Core | Historical simulation engine |
| `src/backtest/enhanced_backtester.py` | Extended | Walk-forward, Monte Carlo |
| `src/engines/signal_engine.py` | 1,244 | Signal generation (same code as live) |
| `src/algo/*` | ~5,750 | Strategy implementations |
| `src/core/models.py` | 767 | `BacktestDiagnostic`, `Signal`, etc. |

---

_Last updated: March 2026 · v6 Pro Desk Edition_
