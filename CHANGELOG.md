# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [9.0.1] — 2026-05-03

### Added
- **Performance Tracker table** — % return vs SPY + sector ETF per ticker, auto-loads on Track Record tab (Sprint 74)

### Fixed
- Render health check path corrected to `/health/live` in `render.yaml`

---

## [9.0.0] — 2026-04-26

### Added — Phase 9: Decision Intelligence Engines
- **StructureDetector** — HH/HL trend classification, S/R level detection, breakout quality scoring
- **EntryQualityEngine** — pre-trade gatekeeper assessing timing, structure, and risk/reward
- **BreakoutMonitor** — post-signal tracking of breakout success/failure with persistence
- **PortfolioGate** — position-level risk control (sector concentration, correlation, max exposure)
- **EarningsCalendar** — real earnings dates via yfinance with blackout zone enforcement
- **FundamentalData** — live financials (ROE, P/E, revenue growth, moat detection, quality score)
- **DecisionJournal** — persistent decision logging with expert accuracy tracking
- 9 Phase 9 API endpoints under `/api/v9/`
- Phase 9 engine health card in Ops dashboard tab
- Health endpoint reports `phase9_engines` status
- Expert council uses accuracy-weighted consensus scoring
- Dashboard: Phase 9 pills on overview, ranked, scanner, rejection tabs
- Dossier page: fundamentals grid, earnings calendar, chart structure cards
- 13 end-to-end tests covering all Phase 9 engines and pipeline

### Changed
- Version bumped from 6.1.0 → 9.0.0
- All silent `except: pass` in scanner wiring replaced with `logger.debug`
- Ops status now uses `APP_VERSION` (was hardcoded `2.1.0`)
- Expert council fundamental analyst errors now logged

---

## [6.0.0] — 2026-04-17

### Added
- Regime Scoreboard with 9-state classification and delta snapshots
- Signal cards with `setup_grade`, `approval_status`, `why_now`, `scenario_plan`
- Morning memo automation (Regime → Delta → Playbook → Top 5 → Scenarios)
- Progressive disclosure UX with interactive Discord buttons
- Compare Overlay service for multi-instrument analysis
- Options Research lab with synthetic chain support
- Portfolio Brief with catalyst enrichment
- Performance Lab with equity curve, drawdown, and Sharpe tracking
- Research artifact system with immutable JSON/CSV/MD bundles
- Market Intel API (read-only regime, VIX, breadth, rates)
- 64 Discord slash commands across 9 categories
- 23 automated background tasks
- 5 broker integrations (Paper, Alpaca, Futu, IBKR, MT5)
- Trust metadata on every output (badge, freshness, model version)
- Walk-forward backtesting with Monte Carlo simulation
- Edge calibration with P(win), EV, MAE calculations
- Strategy learning loop with GBM classifier retraining

### Changed
- Discord is now the primary notification and operating interface
- Migrated from Telegram-first to Discord-first architecture
- Upgraded to Pydantic v2 data models
- Standardized all market data through MarketDataService singleton

### Fixed
- Repository cleanup and security hardening (Sprint P0)
- Confidence calibration improvements
- Backtest realism (commissions, slippage, market hours simulation)

### Security
- Added `.env.example` with placeholder-only credentials
- Added SECURITY.md with secrets handling guidance
- All sensitive values excluded from version control

---

## [5.x and earlier]

Early development phases. See `docs/ARCHITECTURE.md` sprint history for details.
