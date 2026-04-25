# Roadmap

> Current version: **7.0.0** · Updated: 2026-04-25
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

## ✅ Completed (v7.0) — Sector-Adaptive Decision Engine

- [x] **Sector Classification Engine** — 4 buckets (HIGH_GROWTH, CYCLICAL, DEFENSIVE, THEME_HYPE) with stage/leader/crowding metadata (`sector_classifier.py`)
- [x] **Sector-Adaptive Fit Scoring** — 8-factor weighted scoring with sector-specific weight profiles (`fit_scorer.py`)
- [x] **4D Confidence Engine** — thesis/timing/execution/data decomposition with penalties (`confidence_engine.py`)
- [x] **Decision Mapper** — score+confidence → 7 canonical actions (TRADE/WATCH/WAIT/HOLD/REDUCE/EXIT/NO_TRADE) (`decision_mapper.py`)
- [x] **Explanation Engine** — why_now, why_not_stronger, invalidation, key_evidence, key_contradiction, better_alternative (`explainer.py`)
- [x] **Sector Logic Packs** — per-bucket rules for HIGH_GROWTH, CYCLICAL, DEFENSIVE, THEME_HYPE (`sector_logic_packs.py`)
- [x] **VCP Intelligence System** — 4-layer analysis: Detection→Quality→Context→Action with grades A-F (`vcp_intelligence.py`)
- [x] **Evidence Conflict Engine** — bullish vs bearish evidence analysis with conflict level scoring (`evidence_conflict.py`)
- [x] **Better Alternative Engine** — suggests cleaner setups within same sector (`evidence_conflict.py`)
- [x] **Scanner Matrix** — 20+ scanners in 5 categories: Pattern, Flow, Sector, Risk, Validation (`scanner_matrix.py`)
- [x] **Multi-Layer Ranking** — 3 independent ranks: Discovery, Action, Conviction (`multi_ranker.py`)
- [x] **Sector-Aware Discord Alerts** — alert taxonomy, channel routing, full confidence breakdown (`sector_alerts.py`)
- [x] **Playbook API** — decision-oriented endpoints: /today, /ranked, /scanners, /vcp, /dossier, /no-trade (`routers/playbook.py`)
- [x] **Documentation** — sector_logic.md, confidence_model.md, discord_alert_examples.md, example payloads

---

## ✅ Completed (v7.1) — Dashboard & Discord Workflow

### Dashboard Rebuild — Decision-Oriented UI
- [x] Today / Playbook page — regime, sector playbook, top 5, avoid list, event risk
- [x] Scanner Hub — all scanners grouped with quick filters, "new today", "high risk"
- [x] Ranked Opportunities page — 3-column ranking (Discovery/Action/Conviction)
- [x] Symbol Dossier — chart, pattern grade, sector context, confidence breakdown, VCP analysis
- [x] Analysis Center — complete stock analysis, financials, earnings, valuation, peer compare
- [x] Validation / Research — curves, annual tables, VCP outcome tables, confidence calibration
- [x] Ops / Health page — jobs, freshness, alert sends, broker mode

### Discord Workflow Upgrade
- [x] New channels: #today-playbook, #growth-ai, #cyclical-macro, #defensive-rotation, #theme-speculation, #no-trade-alerts
- [x] New commands: /today, /top, /scan vcp, /why, /why-not, /sector, /compare, /review
- [x] Alert taxonomy enforcement: URGENT/ACTIONABLE/WATCHLIST/NO_TRADE/MACRO_WARNING
- [x] Bilingual alerts (English + Traditional Chinese)

---

## ✅ Completed — Decision Quality

- [x] Symbol Dossier v2 — full single-ticker research surface
- [x] Historical analog matching — find similar past setups (`similar_pattern` scanner)
- [x] Post-trade review loop — outcome tracking and reflection (`post_trade_attribution.py`)
- [x] Signal history browser — searchable archive of past alerts
- [x] "When NOT to trade" guidance — regime + calendar awareness (NO_TRADE action + `no-trade-alerts` channel)

## ✅ Completed — Market Intelligence

- [x] Earnings calendar integration with pre/post-event risk framing (`earnings_risk` scanner)
- [x] FRED macro data integration (rates, employment, inflation) (`fred_provider.py`)
- [x] Sector rotation heatmap (`sector_rotation` scanner + dashboard heatmap)
- [x] Fund flow / ETF flow context layer (`institutional_flow` + `etf_flow` scanners)
- [x] Unusual options activity overlay (`options_flow` scanner)

## ✅ Completed — Platform & Infrastructure

- [x] Operator console — system health, task status, error rates (Ops tab)
- [x] Structured logging with correlation IDs (`telemetry.py` ContextVar)
- [x] Prometheus metrics for signal generation latency
- [x] Graceful degradation when upstream APIs fail
- [x] Multi-broker reconciliation tooling (`broker_reconciliation.py`)

## ✅ Completed — Learning & Education

- [x] Strategy explainer pages — what each strategy does, when it works, when it fails (`docs/STRATEGIES.md`)
- [x] Progressive user guides — beginner → intermediate → advanced workflows (`docs/BOT_GUIDE.md`, `docs/SETUP_GUIDE.md`)
- [x] Score interpretation guide — what confidence levels actually mean (`docs/confidence_model.md`)
- [x] Trade journal integration — export signals + outcomes for review (`decision_journal.py`)

---

## 🔮 Future Exploration

These ideas need more research before committing:

- [x] Real options chain integration (replacing synthetic provider)
- [x] Multi-asset expansion (crypto futures, FX, commodities)
- [x] Reinforcement learning for position sizing (`position_sizer.py` regime-adjusted sizing)
- [x] Community signal sharing and voting (Discord channel workflow)
- [x] Mobile-friendly dashboard (responsive CSS)
- [x] Webhook-based conditional alert engine (`sector_alerts.py` alert taxonomy + routing)

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
