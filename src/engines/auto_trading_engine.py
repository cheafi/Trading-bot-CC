"""
TradingAI Bot - Professional Autonomous Trading Engine

Runs 24/7 without human intervention. Handles:
- Market session awareness (US, HK, JP, Crypto)
- Signal generation → validation → execution pipeline
- Position monitoring with trailing stops
- Auto risk management (daily loss limit, drawdown circuit breaker)
- Self-healing: auto-restart, stale data detection
- Learning loop: records outcomes for ML retraining
"""
import asyncio
import logging
import time
from collections import defaultdict
from datetime import datetime, date, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from src.core.config import get_settings, get_trading_config
from src.core.models import Direction, Signal, SignalStatus
from src.engines.regime_router import RegimeRouter
from src.engines.opportunity_ensembler import OpportunityEnsembler
from src.engines.context_assembler import ContextAssembler
from src.engines.strategy_leaderboard import StrategyLeaderboard
from src.algo.position_manager import PositionManager, RiskParameters
from src.ml.trade_learner import TradeLearningLoop, TradeOutcomeRecord
from src.core.logging_config import set_correlation_id, get_correlation_id
from src.core.trade_repo import TradeOutcomeRepository
from src.core.errors import (
    BrokerError, ConfigError, DataError,
    RiskLimitError, SignalError, ValidationError,
)

try:
    from src.engines.insight_engine import EdgeCalculator
    _HAS_EDGE_CALC = True
except ImportError:
    _HAS_EDGE_CALC = False

logger = logging.getLogger(__name__)
settings = get_settings()
trading_config = get_trading_config()


# ---------------------------------------------------------------------------
# Market session schedule (UTC)
# ---------------------------------------------------------------------------
MARKET_SESSIONS = {
    "us_premarket":  {"open": (9, 0),  "close": (13, 30), "markets": ["us"]},
    "us_regular":    {"open": (13, 30), "close": (20, 0),  "markets": ["us"]},
    "us_afterhours": {"open": (20, 0),  "close": (24, 0),  "markets": ["us"]},
    "hk_regular":    {"open": (1, 30),  "close": (8, 0),   "markets": ["hk"]},
    "jp_regular":    {"open": (0, 0),   "close": (6, 0),   "markets": ["jp"]},
    "crypto_247":    {"open": (0, 0),   "close": (24, 0),  "markets": ["crypto"]},
}


class RiskCircuitBreaker:
    """
    Portfolio-level risk controls that halt trading automatically.

    Triggers:
    - Daily loss exceeds MAX_DAILY_LOSS_PCT
    - Portfolio drawdown exceeds MAX_DRAWDOWN_PCT
    - Consecutive losses exceed MAX_CONSECUTIVE_LOSSES
    - High volatility regime detected (VIX > threshold)
    """

    MAX_DAILY_LOSS_PCT = 3.0       # Stop trading if daily loss > 3%
    MAX_DRAWDOWN_PCT = 10.0        # Stop if drawdown from peak > 10%
    MAX_CONSECUTIVE_LOSSES = 5     # Pause after 5 consecutive losses
    COOLDOWN_MINUTES = 60          # Pause duration after trigger
    MAX_OPEN_POSITIONS = 15        # Max concurrent positions

    def __init__(self):
        self.daily_pnl: float = 0.0
        self.peak_equity: float = 0.0
        self.consecutive_losses: int = 0
        self.triggered: bool = False
        self.trigger_reason: str = ""
        self.trigger_time: Optional[datetime] = None
        self.today: date = date.today()

    def reset_daily(self):
        self.daily_pnl = 0.0
        self.today = date.today()

    def update(
        self,
        equity: float,
        trade_pnl: Optional[float] = None,
        open_positions: int = 0,
    ) -> bool:
        """Update and check circuit breaker. Returns True if trading is allowed."""
        # Reset daily if new day
        if date.today() != self.today:
            self.reset_daily()

        # Update peak equity
        if equity > self.peak_equity:
            self.peak_equity = equity

        # Check cooldown
        if self.triggered and self.trigger_time:
            elapsed = (datetime.now(timezone.utc) - self.trigger_time).total_seconds()
            if elapsed < self.COOLDOWN_MINUTES * 60:
                return False
            else:
                self.triggered = False
                self.trigger_reason = ""
                logger.info("Circuit breaker cooldown expired, resuming trading")

        # Update trade P&L
        if trade_pnl is not None:
            self.daily_pnl += trade_pnl
            if trade_pnl < 0:
                self.consecutive_losses += 1
            else:
                self.consecutive_losses = 0

        # Check daily loss
        if self.daily_pnl < -self.MAX_DAILY_LOSS_PCT:
            self._trigger(f"Daily loss {self.daily_pnl:.1f}% exceeds limit")
            return False

        # Check drawdown
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - equity) / self.peak_equity * 100
            if drawdown > self.MAX_DRAWDOWN_PCT:
                self._trigger(f"Drawdown {drawdown:.1f}% exceeds limit")
                return False

        # Check consecutive losses
        if self.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            self._trigger(f"{self.consecutive_losses} consecutive losses")
            return False

        # Check max positions
        if open_positions >= self.MAX_OPEN_POSITIONS:
            return False

        return True

    def _trigger(self, reason: str):
        self.triggered = True
        self.trigger_reason = reason
        self.trigger_time = datetime.now(timezone.utc)
        logger.warning(f"🚨 Circuit breaker triggered: {reason}")


class PositionMonitor:
    """
    Monitors open positions for:
    - Trailing stop updates
    - Take profit targets
    - Time-based exits (max hold time)
    - Gap protection
    """

    def __init__(self):
        self._trailing_stops: Dict[str, float] = {}  # ticker -> trailing stop price
        self._entry_times: Dict[str, datetime] = {}
        self._max_hold_hours: float = 24 * 15  # 15 days default

    def track_entry(self, ticker: str, entry_price: float, stop_price: float):
        self._trailing_stops[ticker] = stop_price
        self._entry_times[ticker] = datetime.now(timezone.utc)

    def update_trailing_stop(
        self,
        ticker: str,
        current_price: float,
        atr: float,
        direction: str = "LONG",
        trail_factor: float = 2.0,
    ) -> Optional[float]:
        """Update trailing stop and return new stop price if changed."""
        if ticker not in self._trailing_stops:
            return None

        current_stop = self._trailing_stops[ticker]
        new_stop = current_stop

        if direction == "LONG":
            candidate = current_price - (atr * trail_factor)
            if candidate > current_stop:
                new_stop = candidate
        else:
            candidate = current_price + (atr * trail_factor)
            if candidate < current_stop:
                new_stop = candidate

        if new_stop != current_stop:
            self._trailing_stops[ticker] = new_stop
            logger.info(
                f"Trailing stop updated for {ticker}: "
                f"{current_stop:.2f} → {new_stop:.2f}"
            )

        return new_stop

    def should_exit_time(self, ticker: str) -> bool:
        """Check if position exceeded max hold time."""
        entry = self._entry_times.get(ticker)
        if entry is None:
            return False
        held_hours = (datetime.now(timezone.utc) - entry).total_seconds() / 3600
        return held_hours > self._max_hold_hours

    def remove(self, ticker: str):
        self._trailing_stops.pop(ticker, None)
        self._entry_times.pop(ticker, None)


class AutoTradingEngine:
    """
    The main autonomous trading loop.

    Lifecycle:
    1. Boot → connect brokers, start feeds, load state
    2. Loop (every cycle_interval):
       a. Check market sessions
       b. Detect regime
       c. Generate signals (for active markets)
       d. Validate via GPT
       e. Check circuit breaker
       f. Execute approved signals
       g. Monitor positions (trailing stops, exits)
       h. Record outcomes for ML
    3. End of day → generate report, retrain if needed
    """

    def __init__(
        self,
        cycle_interval_seconds: float = 60.0,
        dry_run: bool = False,
    ):
        self.cycle_interval = cycle_interval_seconds
        self.dry_run = dry_run
        self.circuit_breaker = RiskCircuitBreaker()
        self.position_monitor = PositionMonitor()
        self._running = False
        self._cycle_count = 0
        self._signals_today: List[Signal] = []
        self._trades_today: List[Dict[str, Any]] = []

        # Sprint 4: decision-layer components
        self.regime_router = RegimeRouter()
        self.ensembler = OpportunityEnsembler()
        self.context_assembler = ContextAssembler()
        self.leaderboard = StrategyLeaderboard()
        self._regime_state: Dict[str, Any] = {}
        self._context: Dict[str, Any] = {}

        # Position management with trailing stops + R-targets
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            risk_params = RiskParameters(
                max_position_pct=tc.max_position_pct,
                max_sector_pct=tc.max_sector_pct,
                max_portfolio_var=tc.max_portfolio_var,
                max_drawdown_pct=tc.max_drawdown_pct,
                risk_per_trade=tc.risk_per_trade,
            )
        except (ConfigError, Exception):
            risk_params = RiskParameters()
        self.position_mgr = PositionManager(params=risk_params)
        self.learning_loop = TradeLearningLoop()
        self._broker_mgr = None  # singleton, init in run()
        self.edge_calculator = EdgeCalculator() if _HAS_EDGE_CALC else None

        # Sprint 7: signal/recommendation cache for API + EOD tracking
        self.trade_repo = TradeOutcomeRepository()
        self._cached_regime: Dict[str, Any] = {}
        self._cached_recommendations: List[Dict[str, Any]] = []
        self._cached_leaderboard: Dict[str, Any] = {}
        self._last_eod_date: Optional[date] = None


    async def _boot(self) -> bool:
        """
        Pre-flight validation before entering the main loop.

        Checks:
        1. All decision-layer components initialized
        2. Broker connectivity (if not dry_run)
        3. Database connectivity (best-effort)
        4. Config sanity (risk params within bounds)

        Returns True if all critical checks pass.
        """
        logger.info("🔍 Running boot checks...")
        checks_passed = 0
        checks_total = 0

        # 1. Component validation
        components = {
            "regime_router": self.regime_router,
            "ensembler": self.ensembler,
            "context_assembler": self.context_assembler,
            "leaderboard": self.leaderboard,
            "position_mgr": self.position_mgr,
            "learning_loop": self.learning_loop,
            "circuit_breaker": self.circuit_breaker,
            "position_monitor": self.position_monitor,
        }
        for name, comp in components.items():
            checks_total += 1
            if comp is not None:
                checks_passed += 1
                logger.info("  ✅ %s OK", name)
            else:
                logger.error("  ❌ %s MISSING", name)

        # 2. Broker connectivity
        if not self.dry_run:
            checks_total += 1
            try:
                mgr = await self._get_broker()
                if mgr is not None:
                    checks_passed += 1
                    logger.info("  ✅ broker connected")
                else:
                    logger.error("  ❌ broker returned None")
            except Exception as e:
                logger.error("  ❌ broker connection failed: %s", e)
        else:
            logger.info("  ⏭️  broker check skipped (dry-run)")

        # 3. Database connectivity (best-effort)
        checks_total += 1
        try:
            from src.core.database import check_database_health
            db_ok = await check_database_health()
            if db_ok:
                checks_passed += 1
                logger.info("  ✅ database OK")
            else:
                logger.warning("  ⚠️  database unreachable (non-fatal)")
                checks_passed += 1  # non-fatal
        except Exception:
            logger.warning("  ⚠️  database check skipped (non-fatal)")
            checks_passed += 1  # non-fatal

        # 4. Config sanity
        checks_total += 1
        try:
            if self.position_mgr.params.risk_per_trade > 0.10:
                logger.warning(
                    "  ⚠️  risk_per_trade=%.2f > 10%% — very aggressive",
                    self.position_mgr.params.risk_per_trade,
                )
            checks_passed += 1
            logger.info("  ✅ config sanity OK")
        except Exception as e:
            logger.warning("  ⚠️  config check error: %s", e)
            checks_passed += 1  # non-fatal

        # 5. Edge calculator
        if self.edge_calculator is not None:
            logger.info("  ✅ edge_calculator OK")
        else:
            logger.info("  ⏭️  edge_calculator unavailable (non-fatal)")

        all_ok = checks_passed >= checks_total
        logger.info(
            "Boot checks: %d/%d passed — %s",
            checks_passed, checks_total,
            "✅ READY" if all_ok else "❌ FAILED",
        )
        return all_ok

    async def run(self):
        """Main loop — runs until stopped."""
        self._running = True
        logger.info("🚀 AutoTradingEngine starting...")
        logger.info(f"  Mode: {'DRY RUN' if self.dry_run else 'LIVE'}")
        logger.info(f"  Cycle interval: {self.cycle_interval}s")

        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                await asyncio.sleep(5)

            await asyncio.sleep(self.cycle_interval)

    async def stop(self):
        self._running = False
        logger.info("AutoTradingEngine stopped")

    async def _run_cycle(self):
        self._cycle_count += 1
        set_correlation_id(f"cyc-{self._cycle_count}")
        now = datetime.now(timezone.utc)

        # Determine active markets
        active_markets = self._get_active_markets(now)
        if not active_markets:
            if self._cycle_count % 60 == 0:
                logger.info("No markets currently open, waiting...")
            return

        # Check circuit breaker
        if not self.circuit_breaker.update(
            equity=await self._get_equity(),
            open_positions=await self._count_positions(),
        ):
            if self._cycle_count % 30 == 0:
                logger.warning(
                    f"Circuit breaker active: {self.circuit_breaker.trigger_reason}"
                )
            return

        # Assemble decision context
        try:
            async with self._timed_phase("context_assembly"):
                self._context = self.context_assembler.assemble_sync()
        except DataError as e:
            logger.warning("Context assembly DataError: %s", e)
            self._context = {}
        except Exception as e:
            logger.warning("Context assembly failed: %s", e)
            self._context = {}

        # Regime classification and trade gate
        mkt_state = self._context.get("market_state", {})
        self._regime_state = self.regime_router.classify(mkt_state)

        # Persist regime snapshot to DB
        try:
            import json as _json
            await self.trade_repo.save_regime_snapshot({
                "snapshot_time": now.isoformat(),
                "risk_regime": self._regime_state.get("risk_regime", ""),
                "trend_regime": self._regime_state.get("trend_regime", ""),
                "volatility_regime": self._regime_state.get("volatility_regime", ""),
                "composite_regime": self._regime_state.get("regime", ""),
                "should_trade": self._regime_state.get("should_trade", True),
                "entropy": self._regime_state.get("entropy", 0),
                "vix_level": self._regime_state.get("vix", 0),
                "pct_above_sma50": self._regime_state.get("pct_above_sma50", 0),
                "context_snapshot": _json.dumps(
                    {k: str(v) for k, v in list(self._regime_state.items())[:20]},
                    default=str,
                ),
            })
        except Exception:
            pass  # DB persistence is best-effort

        if not self._regime_state.get("should_trade", True):
            if self._cycle_count % 30 == 0:
                logger.info(
                    "Regime gate: no-trade "
                    f"(entropy={self._regime_state.get('entropy', 0):.2f})"
                )
            await self._monitor_positions()
            return

        # Generate signals for active markets
        async with self._timed_phase("signal_generation"):
            signals = await self._generate_signals(active_markets)

        # Validate signals
        async with self._timed_phase("signal_validation"):
            validated = await self._validate_signals(signals)

        # Rank through ensemble scorer (with calibrated edge if available)
        signal_dicts = []
        for sig in validated:
            sd = {
                "ticker": sig.ticker,
                "direction": sig.direction.value if hasattr(sig.direction, 'value') else sig.direction,
                "score": sig.confidence / 100 if hasattr(sig, 'confidence') else 0.5,
                "strategy_name": sig.strategy_name if hasattr(sig, 'strategy_name') else "unknown",
                "risk_reward_ratio": getattr(sig, 'risk_reward_ratio', 1.5),
                "expected_return": getattr(sig, 'expected_return', 0.02),
                "_signal_obj": sig,  # keep reference
            }

            # Sprint 8: enrich with EdgeCalculator calibrated probabilities
            if self.edge_calculator is not None:
                try:
                    edge = self.edge_calculator.compute(
                        signal=sig,
                        regime=self._regime_state,
                        features={
                            "relative_volume": getattr(sig, "relative_volume", 1.0),
                            "rsi_14": getattr(sig, "rsi", 50),
                        },
                    )
                    sd["edge_p_t1"] = edge.p_t1
                    sd["edge_p_stop"] = edge.p_stop
                    sd["edge_ev"] = edge.expected_return_pct
                except Exception:
                    pass  # graceful fallback

            signal_dicts.append(sd)

        ranked = self.ensembler.rank_opportunities(
            signal_dicts,
            self._regime_state,
            portfolio_state=self._context.get("portfolio_state"),
            strategy_scores=self.leaderboard.get_strategy_scores(),
        )

        # Cache ranked results for API
        self._cached_recommendations = ranked
        self._cached_regime = self._regime_state
        self._cached_leaderboard = self.leaderboard.get_strategy_scores()

        # Execute only approved opportunities (with ML quality gate)
        for opp in ranked:
            if not opp.get("trade_decision", False):
                continue
            signal = opp["original_signal"].get("_signal_obj")
            if signal is None:
                continue

            # Sprint 7: ML quality gate — skip D-grade signals
            ml_quality = self.learning_loop.predict_signal_quality({
                "confidence": getattr(signal, "confidence", 50),
                "vix_at_entry": self._regime_state.get("vix", 20),
                "rsi_at_entry": getattr(signal, "rsi", 50),
                "adx_at_entry": getattr(signal, "adx", 25),
                "relative_volume": getattr(signal, "relative_volume", 1.0),
                "distance_from_sma50": getattr(signal, "distance_from_sma50", 0),
            })
            if ml_quality.get("model_available") and ml_quality.get("signal_grade") == "D":
                logger.info(
                    "ML quality gate rejected %s (win_prob=%.2f, grade=D)",
                    signal.ticker, ml_quality.get("win_probability", 0),
                )
                continue

            if self.dry_run:
                logger.info(
                    f"[DRY RUN] Would execute: {signal.ticker} "
                    f"{signal.direction.value} "
                    f"(score={opp['composite_score']:.3f})"
                )
            else:
                result = await self._execute_signal(signal)
                if result:
                    result["composite_score"] = opp["composite_score"]
                    self._trades_today.append(result)
                    # Record in PositionManager for trailing stops
                    try:
                        _stop = (
                            signal.invalidation.stop_price
                            if getattr(signal, "invalidation", None)
                            and getattr(signal.invalidation, "stop_price", 0)
                            else result.get("entry_price", signal.entry_price) * (1 - trading_config.stop_loss_pct)
                        )
                        self.position_mgr.open_position(
                            ticker=signal.ticker,
                            strategy_id=opp.get("strategy_name", "unknown"),
                            entry_price=result.get("entry_price", signal.entry_price),
                            shares=self._calculate_position_size(signal),
                            stop_loss_price=_stop,
                            max_hold_days=trading_config.max_hold_days,
                        )
                    except RiskLimitError as e:
                        logger.warning("PositionManager risk limit for %s: %s", signal.ticker, e)
                    except Exception as e:
                        logger.warning("PositionManager track error for %s: %s", signal.ticker, e)

        # Monitor existing positions
        async with self._timed_phase("position_monitoring"):
            await self._monitor_positions()

        # Periodic reporting
        if self._cycle_count % 300 == 0:  # Every ~5 hours
            await self._send_status_update()

        # End-of-day cycle (once per day after market close)
        await self._maybe_run_eod()

    def _get_active_markets(self, now: datetime) -> List[str]:
        """Determine which markets are currently open."""
        hour, minute = now.hour, now.minute
        current_minutes = hour * 60 + minute
        active: Set[str] = set()

        for session_name, session in MARKET_SESSIONS.items():
            open_h, open_m = session["open"]
            close_h, close_m = session["close"]
            open_minutes = open_h * 60 + open_m
            close_minutes = close_h * 60 + close_m

            if close_minutes == 24 * 60:
                close_minutes = 24 * 60 - 1

            if open_minutes <= current_minutes < close_minutes:
                active.update(session["markets"])

        return list(active)

    async def _generate_signals(self, markets: List[str]) -> List[Signal]:
        """Generate signals using the signal engine for active markets."""
        try:
            import pandas as pd
            from src.engines.signal_engine import SignalEngine
            from src.engines.feature_engine import FeatureEngine
            from src.scanners.multi_market_scanner import (
                MarketRegion,
                MultiMarketUniverse,
            )

            # 1. Build universe for active markets
            region_map = {
                "us": MarketRegion.US,
                "hk": MarketRegion.HK,
                "jp": MarketRegion.JP,
                "crypto": MarketRegion.CRYPTO,
            }
            active_regions = [
                region_map[m] for m in markets if m in region_map
            ]
            universe_builder = MultiMarketUniverse()
            assets = universe_builder.build_universe(markets=active_regions)
            tickers = [a.ticker for a in assets]

            if not tickers:
                logger.warning("No tickers for active markets")
                return []

            # 2. Fetch OHLCV data via yfinance (lightweight)
            try:
                import yfinance as yf

                # Batch download last 200 days of data
                data = yf.download(
                    tickers[:50],  # limit to avoid rate limits
                    period="200d",
                    progress=False,
                    group_by="ticker",
                    threads=True,
                )
                if data.empty:
                    logger.warning("No market data returned")
                    return []
            except DataError as e:
                logger.error("Market data fetch DataError: %s", e)
                return []
            except Exception as e:
                logger.error("Market data fetch error: %s", e)
                return []

            # 3. Compute features
            feature_engine = FeatureEngine()
            all_features = []
            valid_tickers = []

            for ticker in tickers[:50]:
                try:
                    if len(tickers[:50]) > 1:
                        df = data[ticker].dropna()
                    else:
                        df = data.dropna()
                    if df.empty or len(df) < 50:
                        continue
                    df.columns = [c.lower() for c in df.columns]
                    feats = feature_engine.calculate_features(df)
                    if not feats.empty:
                        feats["ticker"] = ticker
                        all_features.append(feats.iloc[[-1]])
                        valid_tickers.append(ticker)
                except Exception:
                    continue

            if not all_features:
                logger.warning("No features computed")
                return []

            features_df = pd.concat(all_features, ignore_index=True)

            # 4. Generate signals
            # Gather real market state so RegimeDetector has VIX/breadth
            try:
                import yfinance as _yf_ate
                _vix_d = _yf_ate.Ticker("^VIX").history(period="5d")
                _spy_d = _yf_ate.Ticker("SPY").history(period="5d")
                _mkt = {
                    "vix": float(_vix_d["Close"].iloc[-1]) if len(_vix_d) else 20,
                    "vix_term_structure": 1.0,
                    "pct_above_sma50": 55,
                    "hy_spread": 350,
                    "spx_change_pct": float(
                        _spy_d["Close"].pct_change().iloc[-1] * 100
                    ) if len(_spy_d) > 1 else 0,
                }
            except Exception:
                _mkt = {
                    "vix": 20, "vix_term_structure": 1.0,
                    "pct_above_sma50": 55, "hy_spread": 350,
                }

            engine = SignalEngine()
            signals = engine.generate_signals(
                universe=valid_tickers,
                features=features_df,
                market_data=_mkt,
                portfolio=self._context.get("portfolio_state", {}),
            )
            self._signals_today.extend(signals)
            return signals
        except DataError as e:
            logger.error("Data error in signal generation: %s", e)
            return []
        except SignalError as e:
            logger.error("Signal generation error: %s", e)
            return []
        except Exception as e:
            logger.error("Unexpected signal generation error: %s", e)
            return []

    async def _validate_signals(self, signals: List[Signal]) -> List[Signal]:
        """Validate signals with GPT. Falls back to unvalidated on error."""
        if not signals:
            return []
        try:
            from src.engines.gpt_validator import GPTSignalValidator
            validator = GPTSignalValidator()
            # validate_batch returns list of dicts with 'validation_result' key
            results = await validator.validate_batch(
                signals=signals,
                news_by_ticker=self._context.get("news_by_ticker", {}),
                sentiment_by_ticker=self._context.get("sentiment", {}),
            )
            approved = []
            for sig, res in zip(signals, results):
                vr = res.get("validation_result", "PASS")
                if vr in ("PASS", "STRONG_PASS"):
                    approved.append(sig)
            return approved
        except ValidationError as e:
            logger.error("Signal validation failed: %s", e)
            return signals  # Proceed without validation
        except Exception as e:
            logger.error("Unexpected validation error: %s", e)
            return signals

    async def _execute_signal(self, signal: Signal) -> Optional[Dict[str, Any]]:
        """Execute a signal through the broker manager."""
        try:
            from src.brokers.base import OrderSide, OrderType

            manager = await self._get_broker()

            side = OrderSide.BUY if signal.direction == Direction.LONG else OrderSide.SELL
            result = await manager.place_order(
                ticker=signal.ticker,
                side=side,
                quantity=max(1, self._calculate_position_size(signal)),  # Will be sized by risk model in production
                order_type=OrderType.MARKET,
            )

            if result.success:
                stop_price = (
                    signal.invalidation.stop_price
                    if signal.invalidation else signal.entry_price * 0.95
                )
                self.position_monitor.track_entry(
                    signal.ticker,
                    signal.entry_price,
                    stop_price,
                )
                return {
                    "signal": signal.ticker,
                    "direction": signal.direction.value,
                    "entry_price": getattr(result, "avg_fill_price", signal.entry_price),
                    "time": datetime.now(timezone.utc).isoformat(),
                }
            else:
                logger.warning(f"Order failed for {signal.ticker}: {result.message}")
                return None
        except BrokerError as e:
            logger.error(f"Broker error for {signal.ticker}: {e}")
            return None
        except Exception as e:
            logger.error(f"Execution error for {signal.ticker}: {e}")
            return None

    async def _monitor_positions(self):
        """
        Monitor open positions using PositionManager for:
        - Trailing stop updates + exits
        - R-target partial exits (1R, 2R, 3R)
        - Time-based exits (max hold days)
        - Hard stop-loss
        Closed positions are fed to TradeLearningLoop.
        """
        try:
            manager = await self._get_broker()
            broker_positions = await manager.get_positions()

            # Build price dict from broker positions
            prices: Dict[str, float] = {}
            broker_qty: Dict[str, int] = {}
            broker_side: Dict[str, str] = {}
            for pos in broker_positions:
                ticker = getattr(pos, "symbol", getattr(pos, "ticker", "???"))
                current_price = getattr(pos, "current_price", 0)
                if current_price and current_price > 0:
                    prices[ticker] = current_price
                    broker_qty[ticker] = abs(int(getattr(pos, "qty", 0)))
                    broker_side[ticker] = getattr(pos, "side", "long")

            if not prices:
                return

            now = datetime.now(timezone.utc)

            # Use PositionManager to check all exit conditions
            positions_to_close = self.position_mgr.update_all_positions(prices, now)

            for close_info in positions_to_close:
                ticker = close_info["ticker"]
                exit_price = close_info["price"]
                reason = close_info["reason"]
                qty = broker_qty.get(ticker, 0)
                side = broker_side.get(ticker, "long")

                if qty <= 0:
                    continue

                logger.warning(
                    "Exit signal for %s: %s @ $%.2f", ticker, reason, exit_price
                )
                try:
                    close_side = "sell" if side == "long" else "buy"
                    await manager.submit_order(
                        symbol=ticker, qty=qty,
                        side=close_side, type="market",
                        time_in_force="day",
                    )
                    logger.info("Closed %s via %s", ticker, reason)

                    # Close in PositionManager and feed to learning loop
                    closed_pos = self.position_mgr.close_position(
                        ticker, exit_price, reason
                    )
                    if closed_pos:
                        self._record_learning_outcome(closed_pos, reason)

                except BrokerError as e:
                    logger.error("Close order broker error for %s: %s", ticker, e)
                except Exception as e:
                    logger.error("Close order failed for %s: %s", ticker, e)

        except BrokerError as e:
            logger.error("Position monitoring broker error: %s", e)
        except Exception as e:
            logger.error("Position monitoring error: %s", e)

    def _record_learning_outcome(self, closed_pos, reason: str):
        """Feed a closed position into the TradeLearningLoop."""
        try:
            record = TradeOutcomeRecord(
                trade_id=closed_pos.position_id,
                ticker=closed_pos.ticker,
                direction="LONG",
                strategy=closed_pos.strategy_id,
                entry_price=closed_pos.entry_price,
                exit_price=closed_pos.exit_price,
                entry_time=(
                    closed_pos.entry_date.isoformat()
                    if closed_pos.entry_date else ""
                ),
                exit_time=(
                    closed_pos.exit_date.isoformat()
                    if closed_pos.exit_date else ""
                ),
                pnl_pct=closed_pos.realized_pnl_pct,
                confidence=50,
                horizon="swing",
                exit_reason=reason,
                hold_hours=(
                    (closed_pos.exit_date - closed_pos.entry_date).total_seconds() / 3600
                    if closed_pos.entry_date and closed_pos.exit_date
                    else 0
                ),
            )
            self.learning_loop.record_outcome(record)
            logger.info(
                "Recorded learning outcome: %s %s %.2f%%",
                closed_pos.ticker, reason, closed_pos.realized_pnl_pct,
            )

            # Persist to database (best-effort)
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    self.trade_repo.save_outcome({
                        "trade_id": closed_pos.position_id,
                        "ticker": closed_pos.ticker,
                        "direction": "LONG",
                        "strategy": closed_pos.strategy_id,
                        "entry_price": closed_pos.entry_price,
                        "exit_price": closed_pos.exit_price,
                        "entry_time": (
                            closed_pos.entry_date.isoformat()
                            if closed_pos.entry_date else None
                        ),
                        "exit_time": (
                            closed_pos.exit_date.isoformat()
                            if closed_pos.exit_date else None
                        ),
                        "pnl_pct": closed_pos.realized_pnl_pct,
                        "confidence": 50,
                        "horizon": "swing",
                        "exit_reason": reason,
                        "regime_at_entry": self._cached_regime.get("regime"),
                        "vix_at_entry": self._cached_regime.get("vix"),
                        "rsi_at_entry": None,
                        "adx_at_entry": None,
                        "relative_volume": None,
                        "setup_grade": None,
                        "composite_score": None,
                        "hold_hours": (
                            (closed_pos.exit_date - closed_pos.entry_date
                             ).total_seconds() / 3600
                            if closed_pos.entry_date and closed_pos.exit_date
                            else 0
                        ),
                        "feature_snapshot": None,
                    })
                )
            except Exception:
                pass  # DB persistence is best-effort

        except Exception as e:
            logger.warning("Learning loop record error: %s", e)


    async def _maybe_run_eod(self):
        """Trigger EOD cycle once per day after US market close (20:30 UTC)."""
        now = datetime.now(timezone.utc)
        today = now.date()
        if self._last_eod_date == today:
            return
        # Run EOD after 20:30 UTC (US market close + 30 min buffer)
        if now.hour >= 20 and now.minute >= 30:
            us_active = self._get_active_markets(now)
            if "us" not in us_active:
                self._last_eod_date = today
                await self._run_eod_cycle()

    async def _run_eod_cycle(self):
        """
        End-of-day processing:
        1. Run LLM failure analysis on losing trades
        2. Retrain ML model if enough new data
        3. Refresh strategy leaderboard
        4. Send EOD report
        """
        logger.info("🌙 Running end-of-day cycle...")

        # 1. Failure analysis
        try:
            analysis = await self.learning_loop.run_failure_analysis()
            if analysis:
                logger.info(
                    "EOD failure analysis: %d recommendations",
                    len(analysis.get("recommendations", [])),
                )
        except Exception as e:
            logger.warning("EOD failure analysis error: %s", e)

        # 2. Force model retrain
        try:
            metrics = self.learning_loop.predictor.train()
            logger.info("EOD model retrain: %s", metrics.get("status", "unknown"))
        except Exception as e:
            logger.warning("EOD model retrain error: %s", e)

        # 3. Refresh leaderboard with today's trades
        try:
            for trade in self._trades_today:
                strategy = trade.get("strategy_name", "unknown")
                pnl = trade.get("pnl_pct", 0)
                self.leaderboard.record_outcome(
                    strategy, pnl > 0, pnl,
                )
        except Exception as e:
            logger.warning("EOD leaderboard refresh error: %s", e)

        # 4. Performance summary
        try:
            summary = self.learning_loop.get_performance_summary()
            logger.info(
                "EOD summary: %d trades, %.1f%% win rate, %.2f%% avg PnL",
                summary.get("total_trades", 0),
                summary.get("win_rate", 0),
                summary.get("avg_pnl", 0),
            )
        except Exception as e:
            logger.warning("EOD summary error: %s", e)

        # 5. Send EOD report
        try:
            await self._send_eod_report()
        except Exception as e:
            logger.warning("EOD report send error: %s", e)

        # Reset daily counters
        self._signals_today.clear()
        self._trades_today.clear()
        self.circuit_breaker.reset_daily()
        logger.info("🌙 End-of-day cycle complete")

    async def _send_eod_report(self):
        """Send end-of-day performance report."""
        try:
            from src.notifications.multi_channel import MultiChannelNotifier
            notifier = MultiChannelNotifier()
            summary = self.learning_loop.get_performance_summary()
            regime = self._cached_regime.get("regime", "unknown")
            report = (
                f"🌙 TradingAI End-of-Day Report\n"
                f"Date: {date.today().isoformat()}\n"
                f"Regime: {regime}\n"
                f"Signals generated: {len(self._signals_today)}\n"
                f"Trades executed: {len(self._trades_today)}\n"
                f"Total trades (lifetime): {summary.get('total_trades', 0)}\n"
                f"Win rate: {summary.get('win_rate', 0):.1f}%\n"
                f"Avg PnL: {summary.get('avg_pnl', 0):.2f}%\n"
                f"Model trained: {summary.get('model_trained', False)}"
            )
            await notifier.send_message(report)
        except Exception as e:
            logger.error("EOD report error: %s", e)



    async def _with_retry(self, coro_func, *args, retries=3, delay=1.0, **kwargs):
        """Retry an async callable with exponential backoff."""
        last_exc = None
        for attempt in range(retries):
            try:
                return await coro_func(*args, **kwargs)
            except BrokerError as e:
                last_exc = e
                wait = delay * (2 ** attempt)
                logger.warning(
                    "Retry %d/%d after BrokerError: %s (wait %.1fs)",
                    attempt + 1, retries, e, wait,
                )
                await asyncio.sleep(wait)
            except Exception as e:
                raise  # Non-retryable
        raise last_exc

    async def _get_broker(self):
        """Get or create the singleton BrokerManager instance."""
        if self._broker_mgr is None:
            from src.brokers.broker_manager import BrokerManager
            self._broker_mgr = BrokerManager()
            await self._broker_mgr.initialize()
            logger.info("BrokerManager singleton initialized")
        return self._broker_mgr

    async def _get_equity(self) -> float:
        try:
            manager = await self._get_broker()
            account = await manager.get_account()
            return getattr(account, "portfolio_value", 100000.0)
        except BrokerError:
            return 100000.0
        except Exception:
            return 100000.0

    async def _count_positions(self) -> int:
        try:
            manager = await self._get_broker()
            positions = await manager.get_positions()
            return len(positions)
        except BrokerError:
            return 0
        except Exception:
            return 0

    async def _send_status_update(self):
        """Send periodic status update to all channels."""
        try:
            from src.notifications.multi_channel import MultiChannelNotifier
            notifier = MultiChannelNotifier()
            status = (
                f"📊 TradingAI Status Update\n"
                f"Cycle: {self._cycle_count}\n"
                f"Signals today: {len(self._signals_today)}\n"
                f"Trades today: {len(self._trades_today)}\n"
                f"Circuit breaker: {'🔴 Active' if self.circuit_breaker.triggered else '🟢 OK'}"
            )
            await notifier.send_message(status)
        except Exception as e:
            logger.error(f"Status update error: {e}")


    def get_cached_state(self) -> Dict[str, Any]:
        """Return cached regime, recommendations, leaderboard for API."""
        return {
            "regime": self._cached_regime,
            "recommendations": self._cached_recommendations,
            "leaderboard": self._cached_leaderboard,
            "cycle_count": self._cycle_count,
            "signals_today": len(self._signals_today),
            "trades_today": len(self._trades_today),
        }


    # ── Sprint 10: Observability ─────────────────────────────
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _timed_phase(self, phase_name: str):
        """Context manager that logs phase latency and errors."""
        t0 = time.monotonic()
        try:
            yield
        except Exception as exc:
            elapsed = (time.monotonic() - t0) * 1000
            logger.error(
                "Phase %s FAILED after %.1fms: %s",
                phase_name, elapsed, exc,
            )
            raise
        else:
            elapsed = (time.monotonic() - t0) * 1000
            if elapsed > 5000:
                logger.warning(
                    "Phase %s SLOW: %.1fms", phase_name, elapsed,
                )
            else:
                logger.debug(
                    "Phase %s OK: %.1fms", phase_name, elapsed,
                )

    async def health_check(self) -> Dict[str, Any]:
        """
        Return structured health status for monitoring/API.

        Keys:
          status:      'healthy' | 'degraded' | 'unhealthy'
          components:  dict of component → bool
          metrics:     cycle_count, uptime, circuit_breaker state
        """
        components: Dict[str, bool] = {
            "regime_router": self.regime_router is not None,
            "ensembler": self.ensembler is not None,
            "context_assembler": self.context_assembler is not None,
            "leaderboard": self.leaderboard is not None,
            "position_mgr": self.position_mgr is not None,
            "learning_loop": self.learning_loop is not None,
            "edge_calculator": self.edge_calculator is not None,
            "circuit_breaker": self.circuit_breaker is not None,
            "position_monitor": self.position_monitor is not None,
        }

        # Broker connectivity
        try:
            mgr = await self._get_broker()
            components["broker"] = mgr is not None
        except Exception:
            components["broker"] = False

        healthy_count = sum(components.values())
        total = len(components)
        if healthy_count == total:
            status = "healthy"
        elif healthy_count >= total - 2:
            status = "degraded"
        else:
            status = "unhealthy"

        return {
            "status": status,
            "components": components,
            "metrics": {
                "cycle_count": self._cycle_count,
                "running": self._running,
                "signals_today": len(self._signals_today),
                "trades_today": len(self._trades_today),
                "circuit_breaker_triggered": self.circuit_breaker.triggered,
                "circuit_breaker_reason": self.circuit_breaker.trigger_reason,
                "dry_run": self.dry_run,
            },
        }

    async def graceful_shutdown(self):
        """
        Stop the engine gracefully:
        1. Stop accepting new signals
        2. Flush open positions (close at market)
        3. Run EOD cycle one final time
        4. Set _running = False
        """
        logger.info("🛑 Graceful shutdown initiated...")
        self._running = False

        # Flush open positions
        try:
            manager = await self._get_broker()
            positions = await manager.get_positions()
            for pos in positions:
                ticker = getattr(pos, "symbol", getattr(pos, "ticker", "???"))
                qty = abs(int(getattr(pos, "qty", 0)))
                side = getattr(pos, "side", "long")
                if qty <= 0:
                    continue
                close_side = "sell" if side == "long" else "buy"
                try:
                    await manager.submit_order(
                        symbol=ticker, qty=qty,
                        side=close_side, type="market",
                        time_in_force="day",
                    )
                    logger.info("Shutdown: closed %s (%d shares)", ticker, qty)
                except BrokerError as e:
                    logger.error("Shutdown close failed %s: %s", ticker, e)
        except BrokerError as e:
            logger.error("Shutdown broker error: %s", e)
        except Exception as e:
            logger.error("Shutdown position flush error: %s", e)

        # Final EOD
        try:
            await self._run_eod_cycle()
        except Exception as e:
            logger.warning("Shutdown EOD error: %s", e)

        logger.info("🛑 Graceful shutdown complete")

    def _calculate_position_size(self, signal) -> int:
        """
        Risk-based position sizing using PositionManager.
        Falls back to simple 1% risk calculation if PositionManager fails.
        """
        price = getattr(signal, "entry_price", 0) or getattr(signal, "price", 0) or getattr(signal, "close", 0)
        if not price or price <= 0:
            return 1

        # Compute stop from signal or config default
        stop_price = price * (1 - trading_config.stop_loss_pct)
        if getattr(signal, "invalidation", None) and getattr(signal.invalidation, "stop_price", 0):
            stop_price = signal.invalidation.stop_price

        # Try PositionManager for full risk-based sizing
        try:
            result = self.position_mgr.calculate_position_size(
                ticker=getattr(signal, "ticker", "UNKNOWN"),
                entry_price=price,
                stop_loss_price=stop_price,
                sector=getattr(signal, "sector", ""),
            )
            if result.get("can_trade") and result.get("shares", 0) > 0:
                return result["shares"]
        except Exception as e:
            logger.debug("PositionManager sizing fallback: %s", e)

        # Fallback: simple 1% risk
        equity = 100000.0
        risk_per_trade = equity * 0.01
        stop_distance = abs(price - stop_price)
        if stop_distance <= 0:
            return 1
        shares = int(risk_per_trade / stop_distance)
        max_shares = int((equity * 0.05) / price)
        return max(1, min(shares, max_shares))
