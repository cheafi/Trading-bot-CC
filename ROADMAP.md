# Roadmap

> Current version: **9.1.0** · Updated: 2026-05-07
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

### ✅ Sprint 84 — Swing Service Extraction + MetaLabeler Signal Threshold Wiring

- [x] **ARCH-swing**: Extracted 6 swing helper functions from `main.py` → `src/services/swing_analysis.py` (pure Python, no FastAPI deps); 6 inline routes → `src/api/routers/swing.py`; `main.py` inline route count 99→93
- [x] **SIGNAL-1**: `MetaLabeler._DEFAULTS` wired to `SIGNAL_THRESHOLDS` — `strong_buy_threshold` raised 0.75→0.85 (bars higher for STRONG_BUY label, more conservative); `abstention_threshold` and `watch_threshold` unchanged at 0.45/0.55

### ✅ Sprint 83 — Test Coverage + Git Health

- [x] **TEST**: `test_sprint83.py` — 8 tests covering Sprint 81+82: module imports, `RegimeService.aget()` coroutine contract, router prefix/route-count assertions (market_intel 5, broker 6, health 8), `TradingConfig` ↔ `RISK` alignment, cache speed — 8/8 pass
- [x] **GIT-HEALTH**: Purged 100+ bad remote refs (Roo Code artifact) via `git remote prune origin`; removed space-named log files from `.git/logs/refs/`; set `gc.auto=0` to prevent background repack failures — commits now run silently

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

### ✅ Sprint 96 — Fund Lab v2 + Self-Learning v2

#### Fund Lab v2 (`src/services/fund_lab_service.py`)
- [x] **12-1 momentum factor** — skips last 21 trading days to correct short-term reversal bias (Jegadeesh-Titman style)
- [x] **RS vs SPY scoring** — relative-strength outperformance vs benchmark added as a composited weight per sleeve
- [x] **RSI overbought guard** — FUND_ALPHA skips candidates with RSI > 75; prevents buying exhausted runs
- [x] **FUND_MACRO sleeve** — 4th sleeve: TLT / GLD / IEF / HYG / VNQ / USO / EMB / BIL / TIPS / UUP — macro hedges + safe-haven rotation, all-regime, higher RS weight
- [x] **Calmar ratio** — added to every sleeve's metrics (annualised return / max drawdown)
- [x] **SPY pre-fetch** — benchmark series fetched once, reused across all 4 sleeves (eliminates redundant yfinance calls)

#### Self-Learning v2 (`src/engines/self_learning.py`)
- [x] **Regime-conditioned parameters** — BULL / BEAR / SIDEWAYS / CHOPPY each maintain own `ensemble_min_score`, `stop_loss_pct`, `max_position_pct` stored in `models/regime_params.json`
- [x] **Fund weight auto-tuner** — `tune_fund_weights()` nudges sleeve allocations proportional to rolling Sharpe; 10–50% per-fund bounds; persists to `models/fund_weights.json`
- [x] **Regime performance analyser** — `analyze_regime_performance()` computes win-rate, avg P&L, avg win/loss per regime from closed trades
- [x] **Learning loop connector** — `pull_closed_trades_from_learning_loop()` bridges LearningLoopPipeline → SelfLearningEngine

#### Self-Learn REST API (`src/api/routers/self_learn.py`)
- [x] `GET /api/v7/self-learn/status` — engine state, regime performance, fund weights, recent audit log
- [x] `GET /api/v7/self-learn/regime-params` — active parameter set for a given regime
- [x] `GET /api/v7/self-learn/fund-weights` — current Sharpe-tuned sleeve allocations
- [x] `POST /api/v7/self-learn/trigger` — run full analysis + adjust cycle on closed trades
- [x] `POST /api/v7/self-learn/fund-tune` — auto-tune sleeve weights from latest fund metrics
- [x] `POST /api/v7/self-learn/disable` / `enable` — kill switch

#### Git Hygiene
- [x] **History rewrite** — stripped `releases/*.png` + `src/assets/docs/demo.gif` from all 229 commits via `git-filter-repo`; `.git/` shrunk 512 MB → **12 MB**
- [x] Force-pushed clean history to `origin/main`

---

## 🔮 Future Exploration

These ideas need more research before committing:

- [x] Real options chain integration (replacing synthetic provider)
- [x] Multi-asset expansion (crypto futures, FX, commodities)
- [x] Reinforcement learning for position sizing (`position_sizer.py` regime-adjusted sizing)
- [x] Community signal sharing and voting (Discord channel workflow)
- [x] Mobile-friendly dashboard (responsive CSS)
- [x] Webhook-based conditional alert engine (`sector_alerts.py` alert taxonomy + routing)

## 🔜 Next Up (Sprint 97+)

### ✅ Sprint 97 — Production Readiness (v9.2.0)
- [x] GitHub Actions CI: ruff lint + full pytest suite on every push
- [x] `/healthz` Kubernetes alias + phase9 readiness gate
- [x] Startup file-seeding: `regime_params.json` + `fund_weights.json`
- [x] EOD scheduler: step 5 = self-learning cycle (analyze + apply + fund-tune)
- [x] Paper position tracker (`fund_paper_positions` SQLite table)
- [x] Fund Lab v3 dashboard panel (4 sleeves, Calmar, RSI, 12-1, weight bars)
- [x] Self-Learn Ops panel (engine state, regime win-rates, fund weights, audit log)

### ✅ Sprint 98 — Adaptive Intelligence (v9.3.0)
- [x] Per-regime parameter auto-adjustment (`tune_regime_params()` — nightly win-rate nudge)
- [x] Brier score calibration tracker (`record_prediction_outcome`, `get_calibration_status`)
- [x] Calibration drift alert: warn if Brier score degrades > 5% from baseline
- [x] A/B shadow harness (`propose_ab_shadow`, `record_ab_outcome`, `evaluate_ab_promotion`)
- [x] REST endpoints: `/regime-tune`, `/calibration`, `/calibration/record`, `/ab-status`, `/ab-propose`, `/ab-evaluate`
- [x] EOD scheduler step 6: `tune_regime_params()` from closed trades
- [x] Dashboard: Calibration Drift card + A/B Shadow card in Self-Learn Ops panel

### ✅ Sprint 99 — Execution Intelligence (v9.4.0)
- [x] **ExecutionCostEngine** (`src/engines/execution_cost.py`) — TWAP/VWAP slippage model, commission ($0.005/share, min $1), market impact, fill quality tracker persisted to SQLite `execution_fills`
- [x] **MTFConfluenceGate** (`src/engines/mtf_confluence.py`) — daily + weekly trend/RSI/MACD/regime alignment gate; `confluence_score` [0–1], ≥0.60 = approved; fail-open on missing data
- [x] **Execution REST router** (`src/api/routers/execution.py`) — `/metrics`, `/estimate`, `/record-fill`, `/fills`, `/size-kelly`, `/mtf-confluence` (6 endpoints)
- [x] **Prometheus metrics enriched** — `tradingai_brier_score`, `tradingai_calibration_drift`, `tradingai_ab_challengers`, `tradingai_execution_fills_30d` added to `/metrics`
- [x] **Docker Dockerfile.api hardened** — `python:3.11-slim-bookworm` base, `models/` dir created (regime_params/brier/ab_shadow), `/healthz` probe, api.txt extras install
- [x] **Execution Quality card** in Ops dashboard — avg/median/p95 slippage (bps), % favourable fills, by-strategy breakdown, total commission

### ✅ Sprint 100 — Risk Intelligence (v9.5.0)
- [x] **MTF wired into MultiLayerRanker** — `_action()` ±10 pts, `_conviction()` ±8 pts based on `mtf_confluence_score` in signal dict
- [x] **Risk Guard router** (`src/api/routers/risk_guard.py`) — 4 endpoints: `/correlation-guard` (live Pearson corr vs open positions), `/var-gate` (1-day 95% parametric VaR), `/concentration` (HHI + sector + grade), `/summary`
- [x] **Portfolio Risk card** in Ops dashboard — all-gates badge, positions count, 1d VaR, HHI grade
- [x] **Sprint 100 CI tests** — 13 tests: execution cost, MTF RSI/MACD, ranker MTF wiring, Pearson/VaR helpers, risk router prefix, Kelly formula

### ✅ Sprint 101 — Canonical Decision Schema (v9.5.1)
- [x] **7 new DecisionObject fields** — `signal_source`, `trust_level`, `data_freshness_minutes`, `benchmark_compare`, `mtf_confluence_score`, `execution_cost_bps`, `calibrated_confidence`
- [x] **`from_pipeline_result()` classmethod** — canonical adapter from SectorPipeline PipelineResult
- [x] **`JournalEntry.from_decision_object()` factory** — maps DecisionObject → JournalEntry with enrichment fields
- [x] **`/dossier/{ticker}` adapter** — now returns `DecisionObject.to_dict()` instead of raw signal dict
- [x] **Sprint 101 CI tests** — 10 tests, 10/10 passing

### ✅ Sprint 102 — Self-Learning v4 Phase 1 (v9.5.2)
- [x] **Per-strategy Brier decomposition** — `record_prediction_outcome(strategy=)` tracks per-strategy IC window
- [x] **A/B auto-proposal from regime-tune** — `tune_regime_params()` auto-calls `propose_ab_shadow()` when param shifts >5%
- [x] **MTF pre-filter in MultiLayerRanker** — `pre_filter()` drops signals with explicit `mtf_confluence_score < 0.35`
- [x] **`/calibration/by-strategy` endpoint** — per-strategy Brier table
- [x] **Dashboard Calibration card** — per-strategy Brier rows
- [x] **Sprint 102 CI tests** — 12 tests, 12/12 passing

### ✅ Sprint 103 — Self-Learning v4 Phase 2 (v9.6.0)
- [x] **ThompsonSizingEngine** (`src/engines/thompson_sizing.py`) — Beta(α,β) per `(strategy,regime)` arm; `sample()` → sizing multiplier [0.25–2.0×]; `update(win)` nudges α/β; persist to `models/thompson_arms.json`
- [x] **FeatureICDecayDetector** (`src/engines/feature_ic.py`) — rolling Pearson IC per feature; decay alert when IC drops >0.10 from peak; persist to `models/feature_ic.json`
- [x] **5 new REST endpoints** — `/thompson`, `/thompson/sample`, `/thompson/update`, `/feature-ic`, `/feature-ic/record`
- [x] **EOD scheduler step 7** — Thompson arm updates + feature IC recording wired from closed trades
- [x] **Dashboard cards** — 🎰 Thompson Sizing card + 📉 Feature IC Decay card in Ops panel
- [x] **Sprint 103 CI tests** — 15 tests, 15/15 passing

### ✅ Sprint 107 — Fund Attribution Engine (v9.8.0)
- [x] **`_portfolio_returns()` refactored** — returns `(agg_series, per_pick_dict[ticker→series])` instead of bare `pd.Series`; no backward-compat break (only called in `run()`)
- [x] **`FundLabService._attribution()`** static method — single-period Brinson-style: `contribution = w × (r_pick − r_bm)`; outputs contributors, detractors, sector breakdown, cash drag, drawdown source, recent wins/losses, top-factor correlation
- [x] **ETF sector supplement** — 23 common ETF tickers (TLT, GLD, BIL, USO, EMB, HYG, UUP, VNQ, etc.) mapped to named sectors without extra I/O
- [x] **`run()` wired** — `entry["attribution"]` attached to every sleeve result; flows through all existing `/api/v7/fund-lab/` endpoints automatically
- [x] **Dashboard attribution collapsible** — `<details>` per fund card in Fund Lab panel: contributors table, detractors table, sector contribution list, cash drag / drawdown source / top-factor mini-grid, recent wins/losses row
- [x] **Sprint 107 CI tests** — 15 tests, 15/15 passing (101 total across sprints 100–107)

### ✅ Sprint 106 — AlertService v2 (v9.7.0)
- [x] **AlertService** (`src/services/alert_service.py`) — 6 typed event dispatchers: `on_ic_decay_alert`, `on_thompson_arm_degrade`, `on_fund_rebalance`, `on_regime_change`, `on_drawdown_breach`, `on_circuit_breaker`; persist last 50 events to `models/alert_log.json`; Discord push via `DiscordInteractiveBot` (non-fatal if unconfigured)
- [x] **EOD scheduler step 8** — `check_and_push_ic_decay()` + `check_and_push_thompson_degrade()` wired after step 7 (Thompson+IC); non-fatal
- [x] **FUND_MACRO rebalance alert** — `_build_sleeve()` calls `on_fund_rebalance()` when regime tilt changes candidates; tracks previous state in `models/fund_tilt_state.json`
- [x] **Notify REST router** (`src/api/routers/notify.py`) — `GET /api/v7/notify/log`, `POST /api/v7/notify/test`, `GET /api/v7/notify/status`; registered in `src/api/main.py`
- [x] **Dashboard Notification Events card** in Ops tab — last 20 events with severity badge, Discord configured indicator, `fetchNotifyLog()` wired into `switchTab ops`
- [x] **Sprint 106 CI tests** — 17 tests, 17/17 passing (86 total across sprints 100–106)

### Self-Learning v4 — COMPLETE ✅
- [x] Multi-signal Brier decomposition (per strategy type)
- [x] Reinforcement learning sizing loop (Thompson sampling)
- [x] Automatic feature importance decay detection
- [x] A/B harness auto-proposal from regime-tune output
- [x] MTF confluence gate wired into signal generation pipeline (pre-filter)

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
