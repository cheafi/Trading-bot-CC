# Roadmap

> Current version: **7.2.0-dev** · Updated: 2026-05-04
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

## ✅ Completed (v7.2) — Agentic Deliberation Layer

Inspired by multi-agent trading research workflows (researcher / macro / risk / execution / critic), implemented with deterministic in-house engines and risk gates.

- [x] New agent API surface (`/api/v7/agents/run`, `/batch`, `/today`, `/status`)
- [x] Agent orchestrator service (`agent_orchestrator_service.py`) composing ExpertCouncil + regime + risk policy
- [x] Add dashboard panel for agent debate trace and dissent reasons (`index.html` Command tab right rail)
- [x] Add decision journal persistence for agent outputs (with outcome linkage) (`/api/v7/agents/run?...persist=true` + `/api/v7/agents/journal`)
- [x] Add per-agent reliability tracking by regime (IC/IR style)
- [x] Add execution-quality feedback loop (slippage + fill quality into critic agent)
- [x] Add offline replay harness for agent consensus drift tests

### ✅ Sprint 81 — Async Safety + Monolith Reduction + Data Transparency

- [x] **RISK-2**: Add `RegimeService.aget()` via `asyncio.to_thread` — async routers (`brief.py`, `watchlist.py`) no longer block the FastAPI event loop on yfinance fetches
- [x] **RISK-3**: Extract `/api/market-intel/*` (5 routes, ~150 lines) from `main.py` monolith → `src/api/routers/market_intel.py`; uses `get_regime(request)` instead of `_get_regime()` private coupling
- [x] **DATA-2**: Synthetic data warning banner added to Command tab (mirrors Today tab); `⚠ SYNTHETIC` shown when `today7.regime.synthetic` is truthy

### ✅ Sprint 82 — Config Consolidation + Monolith Reduction Continues

- [x] **CONFIG-1**: `TradingConfig.max_open_positions` default 15 → 10 (aligned with `RISK.max_positions`); `max_drawdown_pct` 0.10 → 0.15 (aligned with `RISK.max_drawdown_pct`) — single source of truth
- [x] **ARCH-broker**: Extract 6 `/broker/*` routes → `src/api/routers/broker.py`
- [x] **ARCH-health**: Extract 8 health/status/metrics routes → `src/api/routers/health.py`; `health_ready` uses `request.app.state` cleanly
- [x] **ARCH-count**: `main.py` inline routes: 118 (Sprint 80) → 113 (Sprint 81) → 99 (Sprint 82); −19 this sprint

### ✅ Sprint 80 — Safety Hardening + Architecture Correctness

- [x] **RISK-1**: Fix `RiskCircuitBreaker.daily_pnl` unit mismatch — normalize to `%` via `(daily_pnl / peak_equity * 100)` before comparing to `max_daily_loss_pct` (was silently comparing raw dollars to 3.0% float)
- [x] **RISK-4**: Canonicalize `max_open_positions` → `RISK.max_positions` (=10) across `RiskCircuitBreaker` (was 15), `TradeGate` (was 20), `MetaLabeler` (was 15) — single source of truth
- [x] **DATA-1**: Compute `realized_vol_20d` live from SPY 20-day annualised log-return std — removes hardcoded `0.15` stub in `MarketDataService.get_market_state()`
- [x] **ARCH-1**: Remove circular imports from `intel.py` (`from src.api.main import live_quote` + `_sanitize_for_json`) — replaced with inline `app.state.market_data` fetch and module-top `deps.py` alias
- [x] **ARCH-2**: Fix Discord bot hardcoded `localhost:8000` — now reads `API_BASE_URL` env var (set to `:8001` when using `_cc_instant.py` proxy)
- [x] **UI-1**: Remove duplicate Alpine `cc()` function from `index.html` — star/love/watchlist state and toggle methods merged into single canonical `cc()` definition
- [x] **UI-2**: Reorder dashboard tabs — Today is now the default first tab; Command moved to end of visible tab bar

### ✅ Sprint 79 — Agent Reliability + Execution Feedback

- [x] New reliability endpoint (`/api/v7/agents/reliability`) with IC/IR-style scoring and regime breakdown
- [x] Agent status now includes reliability sample count + top agents snapshot
- [x] Execution-quality estimator added to orchestrator (expected slippage bps + fill quality score)
- [x] Critic feedback loop now reacts to execution friction and can downgrade weak TRADE setups
- [x] Command tab adds agent reliability panel for live operator monitoring

### ✅ Sprint 78 — ROI Analysis + AI Self-Run Fund Lab

- [x] Self-run fund endpoint (`/api/v7/fund-lab/self-run`) using updated market data
- [x] Three tactical sleeves: `FUND_ALPHA`, `FUND_PENDA`, `FUND_CAT`
- [x] ROI analytics vs index: total return, annualized return, Sharpe, volatility, max drawdown, annualized alpha
- [x] Track Record UI panel for AI fund-vs-index comparison with configurable period/benchmark
- [x] Dynamic pick generation from momentum ranking (top-N per sleeve)

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
