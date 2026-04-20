# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
