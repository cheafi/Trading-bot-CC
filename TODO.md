# CC — Roadmap & Technical Debt Tracker

> Ordered by priority. P0 = must ship in ≤ 2 weeks. P1 = highest ROI within 1 month. P2 = differentiators.

---

## P0 — Immediate (≤ 2 weeks)

- [x] **README quick-start fix** — `cd TradingAI_Bot-main` → `cd Trading-bot-CC`
- [x] **Repo root cleanup** — move 30+ debug/sprint/patch scripts into `scripts/`, `dev/`, `archive/`
- [x] **Security hardening** — remove dangerous defaults from `.env.example` (Grafana admin/admin, pgAdmin, Jupyter token)
- [x] **Fill TODO.md** — this file

---

## P1 — High-ROI (≤ 1 month)

### Confidence Calibration Engine
- [x] Upgrade 4-layer confidence → calibrated with Brier score tracking
- [x] Add reliability diagram data collection
- [x] Implement abstention rule (confidence < threshold → NO TRADE)
- [x] Confidence decay over time (stale signal penalty)
- [x] Scikit-learn `CalibratedClassifierCV` or MAPIE conformal intervals
- [x] Per-horizon calibration (1D / 5D / 20D)

### Backtest Realism
- [x] Add commission model ($0.005/share, $0.65/contract, $1 minimum)
- [x] Add slippage model (ATR-based: 5bps + volume-scaled impact)
- [x] Market hours realism (no fills outside 09:30–16:00 ET)
- [x] Partial fill simulation
- [x] Walk-forward out-of-sample dashboard
- [x] Borrow/short cost model

### 5-Tier Decision Output
- [x] Replace Buy/Sell → STRONG BUY / BUY SMALL / WATCH / NO TRADE / HEDGE
- [x] Structured evidence table (reasons for, reasons against)
- [x] Invalidation map (what would kill this thesis)
- [x] Sizing recommendation based on confidence tier

### Expert Committee Schema v2
- [x] Fixed output schema: stance / strength / evidence / invalidation / time_horizon / risk_notes
- [x] Disagreement score across council
- [x] Consensus classification (strong consensus / lean / split / contested)
- [x] Expert track-record weighting (weight experts by past accuracy)

### Event-Aware Intelligence
- [x] SEC EDGAR: insider Form 4/3/5 ingestion (provider stub + canonical schema)
- [x] SEC 13F: institutional holdings (provider stub + canonical schema)
- [x] Congress financial disclosure parsing (House Clerk / Senate eFD)
- [x] FRED API: macro data integration (provider stub + 10 regime series)
- [x] CFTC COT: futures/options positioning structure (provider stub + schema)
- [x] Normalized event schema → feed into regime + confidence layers

### Shadow-Mode Live Evaluation
- [x] Paper-shadow all live recommendations for 4–8 weeks
- [x] Compare expected vs realized returns
- [x] Confidence vs hit-rate scatter by regime / sector / instrument
- [x] Auto-generate calibration drift alerts

---

## P2 — Differentiators (later)

### Symbol Dossier v2
- [x] Buy / Hold / Avoid verdict with confidence bucket
- [x] Evidence table + contradiction table
- [x] Event calendar (earnings, FOMC, CPI, NFP)
- [x] Insider / congress / fund flow panel
- [x] "What must happen next" + invalidation map
- [x] Scenario tree (bull/base/bear with probabilities)

### Operator Console
- [x] Live provider status + freshness by source — /status/data (real telemetry)
- [x] Model drift detection + calibration drift — CalibrationEngine.calibration_report()
- [x] PnL by regime heatmap
- [x] Signal acceptance funnel (generated → passed filter → sized → executed) — /status/signals (real)
- [x] Rejection reason breakdown — /status/signals rejection_reasons (real)
- [x] Current exposure map (sector / theme / correlation) — /api/v6/portfolio-heat
- [x] Circuit breaker state + broker reconciliation status

### Portfolio Risk Engine
- [x] Portfolio heat limit (total risk budget) — PortfolioHeatEngine
- [x] Sector / theme concentration limit — check_new_position()
- [x] Correlation cluster limit — correlated_cluster_count
- [x] Regime-based leverage cap — ThrottleState
- [x] Event risk blackout (earnings, FOMC, CPI, NFP) — positions_near_earnings
- [x] Spread / liquidity kill switch
- [x] Stale data kill switch — TelemetryTracker.get_data_freshness_ready()
- [x] Execution slippage ceiling

### System Architecture
- [ ] Decompose discord_bot.py (5,596 lines) into modules
- [ ] Separate engine boundaries from API monolith
- [ ] Provider freshness + stale-data kill switch
- [ ] CI/CD pipeline with test gates
- [ ] Render → proper deployment with health checks

---

## Scoring Targets

| Dimension | Current | Target |
|-----------|---------|--------|
| Product vision | 9/10 | 9.5/10 |
| UX / clarity | 8.5/10 | 9/10 |
| Explainability | 8.5/10 | 9.5/10 |
| Trading edge maturity | 5.5/10 | 7.5/10 |
| Risk-engine maturity | 6.5/10 | 8/10 |
| Production readiness | 6/10 | 7.5/10 |
| **Overall** | **7.6/10** | **8.5/10** |
