# Roadmap

> Current version: **6.0.0** · Updated: 2026-04-20
>
> This roadmap reflects planned improvements. Timelines are estimates, not
> commitments. Priorities may shift based on user feedback and contributor
> availability.

---

## ✅ Completed (v6.0)

- [x] Regime-aware signal engine (9 regimes)
- [x] 4 signal strategy families (swing, breakout, momentum, mean reversion)
- [x] Discord bot with 64 slash commands
- [x] 23 automated background tasks
- [x] Portfolio brief with catalyst enrichment
- [x] Compare overlay for multi-instrument analysis
- [x] Options research lab (synthetic chains)
- [x] Performance lab (equity curve, drawdown, Sharpe)
- [x] Walk-forward backtesting with Monte Carlo
- [x] Edge calibration (P(win), EV, MAE)
- [x] Strategy learning loop with GBM retraining
- [x] Trust metadata on every output
- [x] 5 broker integrations (Paper, Alpaca, Futu, IBKR, MT5)
- [x] Market Intel REST API
- [x] Research artifact archival system
- [x] Repository cleanup and security hardening

---

## 🔄 In Progress

### Signal Quality & Strategy Depth
- [ ] VCP (Volatility Contraction Pattern) — dedicated detector with contraction
      quality scoring, pivot validation, and volume dry-up confirmation
- [ ] Breakout quality scoring — distinguish real expansion from false breakouts
- [ ] Pullback entry grading — retracement quality vs. breakdown risk
- [ ] Strategy-style labeling on every Discord alert
- [ ] Signal decay tracking — measure alert freshness and timing lag

### Discord UX
- [ ] Bilingual alerts (English + Traditional Chinese) on all signal cards
- [ ] Alert severity tiers (🔴 Urgent / 🟡 Important / 🔵 Informational)
- [ ] Alert deduplication — suppress duplicate signals within cooldown window
- [ ] "Why Now" and "Why Not" fields on every signal card
- [ ] Invalidation conditions displayed clearly

### Risk & Regime
- [ ] Portfolio heat dashboard — concentration, correlation, sector exposure
- [ ] Regime-based signal throttling — reduce alerts in hostile environments
- [ ] Drawdown circuit breaker alerts in Discord
- [ ] Tail-risk event escalation notifications

---

## 📋 Planned (Next)

### Decision Quality
- [ ] Symbol Dossier v2 — full single-ticker research surface
- [ ] Historical analog matching — find similar past setups
- [ ] Post-trade review loop — outcome tracking and reflection
- [ ] Signal history browser — searchable archive of past alerts
- [ ] "When NOT to trade" guidance — regime + calendar awareness

### Market Intelligence
- [ ] Earnings calendar integration with pre/post-event risk framing
- [ ] FRED macro data integration (rates, employment, inflation)
- [ ] Sector rotation heatmap
- [ ] Fund flow / ETF flow context layer
- [ ] Unusual options activity overlay

### Platform & Infrastructure
- [ ] Operator console — system health, task status, error rates
- [ ] Structured logging with correlation IDs
- [ ] Prometheus metrics for signal generation latency
- [ ] Graceful degradation when upstream APIs fail
- [ ] Multi-broker reconciliation tooling

### Learning & Education
- [ ] Strategy explainer pages — what each strategy does, when it works, when it fails
- [ ] Progressive user guides — beginner → intermediate → advanced workflows
- [ ] Score interpretation guide — what confidence levels actually mean
- [ ] Trade journal integration — export signals + outcomes for review

---

## 🔮 Future Exploration

These ideas need more research before committing:

- [ ] Real options chain integration (replacing synthetic provider)
- [ ] Multi-asset expansion (crypto futures, FX, commodities)
- [ ] Reinforcement learning for position sizing
- [ ] Community signal sharing and voting
- [ ] Mobile-friendly dashboard
- [ ] Webhook-based conditional alert engine

---

## How Priorities Are Decided

1. **Does it improve decision quality?** — Signal accuracy, risk awareness,
   explainability
2. **Does it reduce harm?** — Fewer false positives, better invalidation,
   clearer disclaimers
3. **Does it improve adoption?** — Setup clarity, onboarding, documentation
4. **Does it improve reliability?** — Error handling, graceful degradation,
   monitoring
5. **Does it improve maintainability?** — Code quality, test coverage,
   modularity

---

## Contributing to the Roadmap

Have a suggestion? Open a GitHub Issue with the `enhancement` label and explain:
- What problem it solves
- Who benefits
- Why it matters now vs. later

See [CONTRIBUTING.md](CONTRIBUTING.md) for the full contribution guide.
