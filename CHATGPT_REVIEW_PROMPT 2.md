# Code Review Prompt — Sprint 4 Planning

## Role
You are a senior quant-engineer and trading-systems architect.
Review the GitHub repository **cheafi/Trading-bot-CC** (branch `main`, HEAD `44bd415`) and produce a prioritised implementation plan for the next sprint.

## Repository Context

### What This System Is
A Discord/Telegram trading bot with:
- 54 slash commands, 23 background tasks, real-time signal generation
- Multi-strategy engine (14 strategies: momentum, trend-following, mean-reversion, swing, VCP, earnings, breakout)
- Broker integration (Alpaca, IBKR, Futu, MT5, paper)
- AI validation layer (GPT-4), backtesting engine, market data ingestors
- **92 Python files, ~66,700 lines total**

### Module Breakdown (lines of code)
| Module | Lines | Purpose |
|--------|-------|---------|
| src/notifications | 25,105 | Discord bot (5,600L), Telegram, multi-channel, report generator |
| src/engines | 7,536 | Signal engine, auto-trading, AI advisor, GPT validator, feature engine, strategy optimizer, + 5 new Sprint 3 modules |
| src/algo | 5,859 | 7 strategy files + position manager + strategy manager |
| src/scanners | 4,479 | Market scanners |
| src/brokers | 2,707 | Alpaca, IBKR, Futu, MT5, paper broker |
| src/ml | 2,535 | Feature pipeline, RL agents, trade learner |
| src/api | 2,199 | FastAPI dashboard + REST API |
| src/backtest | 1,933 | Backtester + enhanced backtester |
| src/ingestors | 1,786 | Market data, news, social, realtime feed |
| src/research | 1,899 | Research tools |
| src/performance | 1,490 | Performance tracking |
| src/core | 1,391 | Config, database, models (Pydantic) |
| src/strategies | 1,063 | Strategy definitions |
| src/services | 587 | Market data service |
| src/scheduler | 434 | APScheduler wrapper |

### Sprint History
| Sprint | Commit | Summary |
|--------|--------|---------|
| Sprint 1 | `4036c60` | Fixed 7 P0 bugs: strategy registry mismatch, OOS-driven optimizer, cross-sectional leakage, post-trade leakage, risk breakers, auto-trading VIX/SPY pass-through, MarketDataProvider |
| Sprint 2 | `b221816` | 6 enhancements: regime-weighted routing, MarketDataService.get_news(), consolidated yfinance (10/13 calls), top_count NameError fix, feature pipeline v2, 18 tests |
| Sprint 3 | `44bd415` | Institutional decision layer: 5 new engine modules, 9 new Pydantic models, scenario_plan contract fix, position sizing, _monitor_positions implementation, 29 tests |

### What Sprint 3 Added (current HEAD)

**5 New Engine Modules:**
1. `regime_router.py` (167L) — Probabilistic regime classifier using softmax over risk-on/neutral/risk-off, entropy calculation, should_trade flag, strategy multipliers based on VIX/breadth/HY-spread/realized-vol
2. `opportunity_ensembler.py` (258L) — 7-component weighted ensemble scorer (calibrated_pwin, expected_r, regime_fit, strategy_health, timing, risk_reward, conviction), correlation/event/uncertainty penalties, no-trade suppression layer
3. `expression_engine.py` (269L) — Instrument selector: stock vs CALL/PUT vs debit/credit spread, based on IV percentile, options liquidity (OI ≥ 500), bid-ask spread, hold period, portfolio allocation cap
4. `context_assembler.py` (229L) — Async context gatherer: market state (VIX, SPY, breadth), portfolio state (positions, sectors, cash), news by ticker, with caching (5min TTL)
5. `strategy_leaderboard.py` (224L) — Strategy ranking with lifecycle: blended OOS scoring (sharpe × 0.25 + expectancy × 0.20 + calmar × 0.15 + ...), status management (active → reduced → cooldown → retired after 90d)

**9 New Pydantic Models in models.py:**
- InstrumentType, SetupGrade, MistakeType, LearningTag (enums)
- OptionLeg, ExpressionPlan, TradeRecommendation, RegimeState, StrategyScore (data models)

**3 Inline Fixes:**
- signal_engine.py: scenario_plan keys fixed (base→base_case, bull_trigger→bull_case, bear_trigger→bear_case) to match report_generator consumer
- auto_trading_engine.py: quantity=1 → risk-based _calculate_position_size() (1% equity risk, 3% stop, 5% max position)
- auto_trading_engine.py: _monitor_positions() implemented with -3% hard stop-loss exit logic

**Tests:** 29/29 Sprint 3 passing + 9/10 Sprint 1+2 passing

## Known Remaining Gaps

### GAP 1: New Modules Are Orphaned (CRITICAL)
The 5 new Sprint 3 modules (`RegimeRouter`, `OpportunityEnsembler`, `ExpressionEngine`, `ContextAssembler`, `StrategyLeaderboard`) exist as standalone classes but have **zero import sites** in the rest of the codebase. They need to be wired into:
- `auto_trading_engine.py` — should use ContextAssembler + RegimeRouter + OpportunityEnsembler in its main loop
- `signal_engine.py` — should feed signals through the ensemble scorer
- `discord_bot.py` / `telegram.py` — regime state and trade recommendations should appear in user-facing output
- The `ExpressionEngine` needs options chain data which doesn't exist yet

### GAP 2: Learning Loop Still Disconnected
- `TradeLearningLoop` in `src/ml/trade_learner.py` (487L) has train/score/summarize but **no call sites** connecting it to execution outcomes
- `EdgeCalculator.load_calibration()` exists in insight_engine.py but is never called with real data
- No post-trade outcome feed: when a position closes, nothing records the result for learning

### GAP 3: API Endpoints Are Functional But Not Integrated
- `src/api/main.py` (737L) has health, status, signals, portfolio endpoints
- But portfolio endpoints return mock data when broker isn't connected
- No endpoint exposes TradeRecommendation, RegimeState, or StrategyLeaderboard data
- Dashboard templates exist but may reference old data structures

### GAP 4: Options Data Pipeline Missing
- `ExpressionEngine` needs IV percentile, open interest, bid-ask spread data
- No options chain data provider exists
- Broker integrations (Alpaca, IBKR) support options but aren't wired to feed the expression engine

### GAP 5: Position Management Gaps
- `_monitor_positions()` now has stop-loss, but no trailing stop, no time-based exits, no profit-target exits
- `PositionManager` in `src/algo/position_manager.py` has sophisticated scaling logic but isn't used by AutoTradingEngine
- No correlation between PositionManager's R-target exits and the broker layer

### GAP 6: Configuration / Environment
- All 5 new modules use hardcoded thresholds (VIX_CRISIS=35, MIN_OPTION_OI=500, etc.)
- No config integration — thresholds should come from Settings/TradingConfig
- No environment-specific overrides (paper vs live)

### GAP 7: Error Handling Patterns
- New modules use `except Exception` broadly
- No structured error types for trading-specific failures
- No circuit-breaker integration in new modules (CircuitBreaker exists in auto_trading_engine)

## What I Need From You

### 1. Architecture Review
- Review the 5 new Sprint 3 modules for design quality
- Identify any architectural anti-patterns or missing abstractions
- Assess whether the RegimeRouter → OpportunityEnsembler → ExpressionEngine pipeline is correctly designed

### 2. Integration Plan
- How should the new modules be wired into the existing auto_trading_engine loop?
- What's the minimal integration needed vs. the ideal end state?
- Which integration should happen first for maximum value?

### 3. Prioritised Sprint 4 Task List
Produce a numbered list of **concrete implementation tasks** with:
- **Priority**: P0 (must-ship) / P1 (should-ship) / P2 (nice-to-have)
- **Effort**: S (< 50 lines) / M (50-200 lines) / L (200-500 lines) / XL (500+ lines)
- **Files affected**
- **What to do** (specific enough to implement without ambiguity)

### 4. Risk Assessment
- What could break if we wire the new modules into the live engine?
- What safety mechanisms should be in place before going live?
- Are there any data dependencies that block progress?

## Format Requirements
- Be concrete and specific — reference actual file names, class names, method names
- Include code snippets for any non-obvious integration points
- Prioritise ruthlessly — we can only ship 5-7 things per sprint
- Flag anything that's "architecturally wrong" vs "works but suboptimal"
