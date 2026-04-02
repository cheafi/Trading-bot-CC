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
from datetime import date, datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from src.algo.position_manager import PositionManager, RiskParameters
from src.core.config import get_settings, get_trading_config
from src.core.errors import (BrokerError, ConfigError, DataError,
                             RiskLimitError, SignalError, ValidationError)
from src.core.logging_config import get_correlation_id, set_correlation_id
from src.core.models import (Direction, Signal, SignalStatus,
                             TradeRecommendation)
from src.core.trade_repo import TradeOutcomeRepository
from src.core.trust_metadata import (NoTradeCard, PnLBreakdown,
                                     TradeAttribution, TrustBadge,
                                     TrustMetadata)
from src.engines.context_assembler import ContextAssembler
from src.engines.opportunity_ensembler import OpportunityEnsembler
from src.engines.portfolio_risk_budget import PortfolioRiskBudget
from src.engines.professional_kpi import CoverageFunnel, ProfessionalKPI
from src.engines.regime_router import RegimeRouter
from src.engines.strategy_leaderboard import StrategyLeaderboard
from src.ml.trade_learner import TradeLearningLoop, TradeOutcomeRecord
from src.scanners.universe_builder import UniverseBuilder

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
    - Daily loss exceeds max_daily_loss_pct
    - Portfolio drawdown exceeds max_drawdown_pct
    - Consecutive losses exceed max_consecutive_losses
    - High volatility regime detected (VIX > threshold)

    All thresholds are read from TradingConfig so users can tune
    via .env without touching code.
    """

    def __init__(
        self,
        max_daily_loss_pct: float = 3.0,
        max_drawdown_pct: float = 10.0,
        max_consecutive_losses: int = 5,
        cooldown_minutes: int = 60,
        max_open_positions: int = 15,
    ):
        # Configurable thresholds
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_drawdown_pct = max_drawdown_pct
        self.max_consecutive_losses = max_consecutive_losses
        self.cooldown_minutes = cooldown_minutes
        self.max_open_positions = max_open_positions

        # Runtime state
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
            if elapsed < self.cooldown_minutes * 60:
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
        if self.daily_pnl < -self.max_daily_loss_pct:
            self._trigger(f"Daily loss {self.daily_pnl:.1f}% exceeds limit")
            return False

        # Check drawdown
        if self.peak_equity > 0:
            drawdown = (self.peak_equity - equity) / self.peak_equity * 100
            if drawdown > self.max_drawdown_pct:
                self._trigger(f"Drawdown {drawdown:.1f}% exceeds limit")
                return False

        # Check consecutive losses
        if self.consecutive_losses >= self.max_consecutive_losses:
            self._trigger(f"{self.consecutive_losses} consecutive losses")
            return False

        # Check max positions
        if open_positions >= self.max_open_positions:
            return False

        return True

    def _trigger(self, reason: str):
        self.triggered = True
        self.trigger_reason = reason
        self.trigger_time = datetime.now(timezone.utc)
        logger.warning(f"🚨 Circuit breaker triggered: {reason}")


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
        # Sprint 24: circuit breaker reads from TradingConfig
        try:
            _tc = get_trading_config()
            self.circuit_breaker = RiskCircuitBreaker(
                max_daily_loss_pct=_tc.max_daily_loss_pct,
                max_drawdown_pct=_tc.max_drawdown_pct * 100,  # config is fraction
                max_consecutive_losses=_tc.max_consecutive_losses,
                cooldown_minutes=_tc.circuit_breaker_cooldown_min,
                max_open_positions=_tc.max_open_positions,
            )
        except (ConfigError, KeyError, ValueError):
            self.circuit_breaker = RiskCircuitBreaker()
        self._running = False
        self._cycle_count = 0
        self._signals_today: List[Signal] = []
        self._trades_today: List[Dict[str, Any]] = []

        # Sprint 4: decision-layer components
        self.regime_router = RegimeRouter()
        self.ensembler = OpportunityEnsembler()

        # Sprint 42: wire MarketDataService into ContextAssembler
        # so it uses get_vix/get_spy_return/get_market_breadth
        # instead of falling back to raw yfinance or defaults.
        try:
            from src.services.market_data import get_market_data_service
            _mds = get_market_data_service()
        except Exception:
            _mds = None

        self.context_assembler = ContextAssembler(
            market_data_service=_mds,
            broker_manager=getattr(self, 'broker_manager', None),
            news_service=getattr(self, 'news_service', None),
        )
        self.leaderboard = StrategyLeaderboard()
        self.universe_builder = UniverseBuilder()
        self.risk_budget = PortfolioRiskBudget()
        self.kpi = ProfessionalKPI()
        self._regime_state: Dict[str, Any] = {}
        self._context: Dict[str, Any] = {}

        # Position management with trailing stops + R-targets
        try:
            tc = get_trading_config()
            risk_params = RiskParameters(
                max_position_size_pct=tc.max_position_pct * 100,
                max_sector_exposure_pct=tc.max_sector_pct * 100,
                max_total_drawdown_pct=tc.max_drawdown_pct * 100,
                risk_per_trade_pct=tc.risk_per_trade * 100,
            )
        except (ConfigError, KeyError, ValueError, TypeError):
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

        # Sprint 24: equity cache to eliminate $100k fallback
        self._last_known_equity: float = 0.0
        self._equity_fetched_at: Optional[datetime] = None
        self._equity_stale_minutes: int = 15

        # Sprint 30: no-trade readiness snapshot
        self._no_trade_readiness: Dict[str, Any] = {}

        # Sprint 36: cached no-trade card
        self._no_trade_card = None

        # Sprint 31: signal cooldown + correlation guard
        try:
            _tc2 = get_trading_config()
            _cdh = _tc2.signal_cooldown_hours
            _afh = _tc2.anti_flip_hours
            _mcr = _tc2.max_correlated_held
            # Guard against mock / invalid types
            self._signal_cooldown_hours = (
                int(_cdh) if isinstance(_cdh, (int, float))
                else 4
            )
            self._anti_flip_hours = (
                int(_afh) if isinstance(_afh, (int, float))
                else 6
            )
            self._max_correlated = (
                int(_mcr) if isinstance(_mcr, (int, float))
                else 3
            )
        except (ConfigError, KeyError, ValueError, TypeError):
            self._signal_cooldown_hours = 4
            self._anti_flip_hours = 6
            self._max_correlated = 3
        from src.engines.signal_engine import SignalCooldown
        self._signal_cooldown = SignalCooldown(
            cooldown_hours=self._signal_cooldown_hours,
            anti_flip_hours=self._anti_flip_hours,
        )
        self._last_price_data: Dict[
            str, Any
        ] = {}  # ticker→close Series cache


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
        except (ImportError, OSError, ConnectionError) as e:
            logger.warning("  ⚠️  database check skipped (non-fatal): %s", e)
            checks_passed += 1  # non-fatal

        # 4. Config sanity
        checks_total += 1
        try:
            if self.position_mgr.params.risk_per_trade_pct > 10.0:
                logger.warning(
                    "  ⚠️  risk_per_trade_pct=%.1f%% > 10%% — very aggressive",
                    self.position_mgr.params.risk_per_trade_pct,
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

        # Sprint 24: reload position state from last run
        try:
            self.position_mgr.load_state()
            logger.info(
                "  ✅ position state loaded (%d open)",
                len(self.position_mgr.positions),
            )
        except Exception as e:
            logger.warning(
                "  ⚠️  position state load skipped: %s", e,
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
                self._touch_heartbeat()
            except Exception as e:
                logger.error(f"Cycle error: {e}", exc_info=True)
                await asyncio.sleep(5)

            await asyncio.sleep(self.cycle_interval)

    def _touch_heartbeat(self):
        """Write heartbeat file for Docker healthcheck."""
        try:
            import pathlib
            hb = pathlib.Path("/tmp/engine_heartbeat")
            hb.write_text(
                datetime.now(timezone.utc).isoformat()
            )
        except OSError:
            pass

    async def stop(self):
        self._running = False
        logger.info("AutoTradingEngine stopped")

    async def _run_cycle(self):
        self._cycle_count += 1
        set_correlation_id(f"cyc-{self._cycle_count}")
        now = datetime.now(timezone.utc)
        signals: List[Signal] = []
        ranked: List[TradeRecommendation] = []

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
        except (OSError, ConnectionError, RuntimeError) as e:
            logger.debug("Regime DB persist skipped: %s", e)

        if not self._regime_state.get("should_trade", True):
            await self._no_trade_cycle()
            return

        # Generate signals for active markets
        async with self._timed_phase("signal_generation"):
            signals = await self._generate_signals(active_markets)

        # Validate signals
        async with self._timed_phase("signal_validation"):
            validated = await self._validate_signals(signals)

        # Rank through ensemble scorer (with calibrated edge if available)
        # Sprint 30: use generate_recommendations() bridge
        recommendations = self._signals_to_recommendations(
            validated,
        )

        ranked = self.ensembler.rank_opportunities(
            recommendations,
            self._regime_state,
            portfolio_state=self._context.get("portfolio_state"),
            strategy_scores=self.leaderboard.get_strategy_scores(),
            regime_weights=self.regime_router.get_strategy_multipliers(
                self._regime_state
            ),
        )

        # Cache ranked results for API (JSON-safe)
        self._cached_recommendations = [
            rec.to_api_dict() for rec in ranked
        ]
        self._cached_regime = self._regime_state
        self._cached_leaderboard = self.leaderboard.get_strategy_scores()

        # Execute only approved opportunities (with ML quality gate)
        # Sprint 24: refuse new trades when equity is stale
        if self._is_equity_stale():
            logger.warning(
                "Equity data stale/missing — skipping "
                "new trade execution this cycle",
            )
            return

        for rec in ranked:
            if not rec.trade_decision:
                continue

            # Sprint 31: correlation guard — skip if
            # candidate is too correlated with held positions
            corr_ok, corr_reason = (
                self.position_mgr.check_correlation_guard(
                    rec.ticker,
                    price_data=self._last_price_data,
                    max_correlated=self._max_correlated,
                    threshold=0.70,
                )
            )
            if not corr_ok:
                logger.info(
                    "Correlation guard skipped %s: %s",
                    rec.ticker, corr_reason,
                )
                continue

            # Sprint 28: ML grade → size modulation (not just D-reject)
            # A=1.0, B=0.75, C=0.5, D=reject
            ml_quality = self.learning_loop.predict_signal_quality(
                rec.to_entry_snapshot(),
            )
            _ml_grade = ml_quality.get("signal_grade", "B")
            _ml_prob = ml_quality.get("win_probability", 0)
            if ml_quality.get("model_available"):
                rec.ml_grade = _ml_grade
                rec.ml_win_probability = _ml_prob
                if _ml_grade == "D":
                    logger.info(
                        "ML gate rejected %s (grade=D, p=%.2f)",
                        rec.ticker, _ml_prob,
                    )
                    continue
            # Store grade for sizing layer
            rec.ml_grade = _ml_grade

            if self.dry_run:
                logger.info(
                    "[DRY RUN] Would execute: %s %s (score=%.3f)",
                    rec.ticker, rec.direction, rec.composite_score,
                )
            else:
                result = await self._execute_recommendation(rec)
                if result:
                    result["composite_score"] = rec.composite_score
                    self._trades_today.append(result)
                    # Record in PositionManager for trailing stops
                    try:
                        _is_short = (
                            rec.direction == Direction.SHORT.value
                        )
                        _entry = result.get(
                            "entry_price", rec.entry_price,
                        )
                        if rec.stop_price and rec.stop_price > 0:
                            _stop = rec.stop_price
                        elif _is_short:
                            _stop = _entry * (
                                1 + trading_config.stop_loss_pct
                            )
                        else:
                            _stop = _entry * (
                                1 - trading_config.stop_loss_pct
                            )
                        self.position_mgr.open_position(
                            ticker=rec.ticker,
                            strategy_id=rec.strategy_id,
                            entry_price=_entry,
                            shares=rec.position_size_shares or 1,
                            stop_loss_price=_stop,
                            max_hold_days=trading_config.max_hold_days,
                            direction=(
                                "short" if _is_short else "long"
                            ),
                        )
                    except RiskLimitError as e:
                        logger.warning(
                            "PositionManager risk limit "
                            "for %s: %s", rec.ticker, e,
                        )
                    except Exception as e:
                        logger.warning(
                            "PositionManager track error "
                            "for %s: %s", rec.ticker, e,
                        )
                    # Sprint 24: persist state after open
                    self.position_mgr.save_state()

        # Sprint 35: record engine cycle into KPI tracker
        _traded = len(self._trades_today) > 0
        try:
            _funnel = CoverageFunnel(
                watched=len(
                    self.universe_builder.build(
                        markets=active_markets,
                        regime_state=self._regime_state,
                    ).tickers
                ) if active_markets else 0,
                eligible=len(signals),
                ranked=len(ranked),
                approved=sum(
                    1 for r in ranked if r.trade_decision
                ),
                rejected=sum(
                    1 for r in ranked if not r.trade_decision
                ),
                executed=len(self._trades_today),
            )
            self.kpi.record_cycle(
                traded=_traded, funnel=_funnel,
            )
        except Exception as e:
            logger.debug("KPI record_cycle error: %s", e)

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

    # ------------------------------------------------------------------
    # Sprint 30: No-trade cycle — do useful work even when regime
    # says don't trade (universe refresh, position monitoring,
    # readiness snapshot, regime telemetry)
    # ------------------------------------------------------------------

    async def _no_trade_cycle(self):
        """Run productive tasks when the regime gate blocks trading.

        Instead of wasting the cycle, we:
        1. Monitor existing positions (trailing stops still run)
        2. Refresh universe to keep caches warm
        3. Compute readiness snapshot (what we would trade)
        4. Log regime telemetry for analytics
        """
        if self._cycle_count % 30 == 0:
            logger.info(
                "Regime gate: no-trade "
                "(entropy=%.2f, regime=%s)",
                self._regime_state.get("entropy", 0),
                self._regime_state.get("regime", "unknown"),
            )

        # 1. Always monitor positions (stops/exits still active)
        await self._monitor_positions()

        # 2. Refresh universe (keep ticker list warm)
        try:
            active_markets = self._get_active_markets(
                datetime.now(timezone.utc),
            )
            if active_markets:
                spec = self.universe_builder.build(
                    markets=active_markets,
                    regime_state=self._regime_state,
                )
                self._no_trade_readiness = {
                    "timestamp": datetime.now(
                        timezone.utc,
                    ).isoformat(),
                    "regime": self._regime_state.get(
                        "regime", "",
                    ),
                    "entropy": self._regime_state.get(
                        "entropy", 0,
                    ),
                    "should_trade": False,
                    "universe_size": len(spec.tickers),
                    "markets": active_markets,
                    "reason": self._regime_state.get(
                        "no_trade_reason",
                        "high_entropy",
                    ),
                    "risk_regime": self._regime_state.get(
                        "risk_regime", "",
                    ),
                    "probabilities": {
                        k: round(v, 3)
                        for k, v in self._regime_state.items()
                        if k.startswith("prob_")
                        or k in (
                            "risk_on_uptrend",
                            "neutral_range",
                            "risk_off_downtrend",
                        )
                    },
                }
        except Exception as e:
            logger.debug("No-trade universe refresh: %s", e)
            self._no_trade_readiness = {
                "timestamp": datetime.now(
                    timezone.utc,
                ).isoformat(),
                "should_trade": False,
                "reason": str(e),
            }

        # Sprint 36: build + cache no-trade card
        try:
            self._no_trade_card = NoTradeCard.from_regime(
                self._regime_state,
                tickers=self._no_trade_readiness.get(
                    "tickers", [],
                ),
            )
        except (KeyError, TypeError, ValueError):
            pass

    # ------------------------------------------------------------------
    # Sprint 30: Signal → TradeRecommendation bridge
    # ------------------------------------------------------------------

    def _signals_to_recommendations(
        self, signals: List[Signal],
    ) -> List[TradeRecommendation]:
        """Convert validated signals to TradeRecommendations.

        Sprint 31: applies signal cooldown + anti-flip filter
        before conversion so we never whipsaw the same ticker.
        """
        # Sprint 31: cross-cycle dedup
        self._signal_cooldown.clear_expired()
        kept, blocked = self._signal_cooldown.filter_signals(
            signals,
        )
        for b in blocked:
            logger.info(
                "Signal blocked: %s %s — %s",
                b["ticker"], b["direction"], b["reason"],
            )
        self._signal_cooldown.record_batch(kept)

        recommendations = []
        for sig in kept:
            _edge = None
            if self.edge_calculator is not None:
                try:
                    _edge = self.edge_calculator.compute(
                        signal=sig,
                        regime=self._regime_state,
                        features={
                            "relative_volume": getattr(
                                sig, "relative_volume", 1.0,
                            ),
                            "rsi_14": getattr(sig, "rsi", 50),
                        },
                    )
                except (ValueError, KeyError, TypeError) as e:
                    logger.debug("Edge calc fallback: %s", e)

            rec = TradeRecommendation.from_signal(
                sig,
                edge=_edge,
                regime_state=self._regime_state,
            )
            recommendations.append(rec)
        return recommendations

    async def _generate_signals(self, markets: List[str]) -> List[Signal]:
        """Generate signals using the signal engine for active markets.

        Pipeline (Sprint 23 — staged universe):
        1. UniverseBuilder.build() → regime-aware, per-market capped,
           crypto-suffix-fixed ticker list
        2. yfinance batch download
        3. FeatureEngine per ticker
        4. SignalEngine.generate_signals()
        """
        try:
            import pandas as pd

            from src.engines.feature_engine import FeatureEngine
            from src.engines.signal_engine import SignalEngine

            # 1. Build universe via staged pipeline
            spec = self.universe_builder.build(
                markets=markets,
                regime_state=self._regime_state,
            )
            tickers = spec.tickers

            if not tickers:
                logger.warning("No tickers for active markets")
                return []

            # 2. Fetch OHLCV data via yfinance (lightweight)
            try:
                import yfinance as yf

                data = yf.download(
                    tickers,
                    period="200d",
                    progress=False,
                    group_by="ticker",
                    threads=True,
                )
                if data.empty:
                    logger.warning("No market data returned")
                    return []
            except DataError as e:
                logger.error(
                    "Market data fetch DataError: %s", e,
                )
                return []
            except Exception as e:
                logger.error(
                    "Market data fetch error: %s", e,
                )
                return []

            # 3. Compute features
            feature_engine = FeatureEngine()
            all_features = []
            valid_tickers = []

            for ticker in tickers:
                try:
                    if len(tickers) > 1:
                        df = data[ticker].dropna()
                    else:
                        df = data.dropna()
                    if df.empty or len(df) < 50:
                        continue
                    df.columns = [
                        c.lower() for c in df.columns
                    ]
                    feats = feature_engine.calculate_features(
                        df,
                    )
                    if not feats.empty:
                        feats["ticker"] = ticker
                        all_features.append(
                            feats.iloc[[-1]],
                        )
                        valid_tickers.append(ticker)
                except (
                    ValueError, KeyError, TypeError,
                ) as e:
                    logger.debug(
                        "Feature calc skipped for %s: %s",
                        ticker, e,
                    )
                    continue

            if not all_features:
                logger.warning("No features computed")
                return []

            # Sprint 31: cache close prices for correlation guard
            self._last_price_data = {}
            for ticker in valid_tickers:
                try:
                    if len(tickers) > 1:
                        close = data[ticker]["Close"].dropna()
                    else:
                        close = data["Close"].dropna()
                    if len(close) >= 20:
                        self._last_price_data[ticker] = close
                except (KeyError, TypeError):
                    pass

            features_df = pd.concat(
                all_features, ignore_index=True,
            )

            # 4. Generate signals
            # Sprint 26: reuse context assembler market_state
            # instead of a redundant yfinance fetch
            _ctx_mkt = self._context.get("market_state", {})
            _mkt = {
                "vix": _ctx_mkt.get("vix", 20),
                "vix_term_structure": _ctx_mkt.get(
                    "vix_term_slope", 1.0,
                ),
                "pct_above_sma50": int(
                    _ctx_mkt.get("breadth_pct", 0.55) * 100
                ),
                "hy_spread": _ctx_mkt.get("hy_spread", 350),
                "spx_change_pct": _ctx_mkt.get(
                    "spy_return_20d", 0,
                ),
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

    async def _execute_recommendation(
        self, rec: "TradeRecommendation",
    ) -> Optional[Dict[str, Any]]:
        """Execute a TradeRecommendation through the broker manager.

        All data (edge, strategy, sizing params) is read from the
        canonical TradeRecommendation object — no ad-hoc dicts.
        """
        try:
            from src.brokers.base import OrderSide, OrderType

            manager = await self._get_broker()

            side = (
                OrderSide.BUY
                if rec.direction == Direction.LONG.value
                else OrderSide.SELL_SHORT
            )
            qty = max(1, self._calculate_position_size(
                rec,
                edge_pwin=rec.edge_p_t1,
                edge_rr=rec.risk_reward_ratio,
                strategy_name=rec.strategy_id,
            ))
            rec.position_size_shares = qty

            result = await manager.place_order(
                ticker=rec.ticker,
                side=side,
                quantity=qty,
                order_type=OrderType.MARKET,
            )

            if result.success:
                _entry_price = getattr(
                    result, "avg_fill_price", rec.entry_price,
                )

                rec.executed = True
                rec.execution_time = datetime.now(timezone.utc)
                rec.fill_price = _entry_price

                # Sprint 36: attach trust metadata to entry
                _badge = (
                    TrustBadge.PAPER
                    if self.dry_run
                    else TrustBadge.LIVE
                )
                rec.trust = TrustMetadata.for_entry(
                    badge=_badge,
                    confidence=rec.signal_confidence,
                    source_count=len(
                        rec.source_strategies
                    ) or 1,
                    regime_label=self._cached_regime.get(
                        "regime", "",
                    ),
                    risk_regime=self._cached_regime.get(
                        "risk_regime", "",
                    ),
                ).to_dict()

                # Sprint 25: send trade-execution notification
                await self._notify_trade_executed(rec, _entry_price)

                return {
                    "ticker": rec.ticker,
                    "direction": rec.direction,
                    "strategy_name": rec.strategy_id,
                    "entry_price": _entry_price,
                    "time": rec.execution_time.isoformat(),
                    "confidence": rec.signal_confidence,
                    "composite_score": rec.composite_score,
                    "ml_grade": getattr(rec, "ml_grade", ""),
                    "regime_at_entry": self._cached_regime.get(
                        "regime", "",
                    ),
                    "entry_snapshot": rec.to_entry_snapshot(),
                    "trust": rec.trust,
                }
            else:
                logger.warning(
                    "Order failed for %s: %s",
                    rec.ticker,
                    getattr(result, "message", "unknown"),
                )
                return None
        except BrokerError as e:
            logger.error("Broker error for %s: %s", rec.ticker, e)
            return None
        except Exception as e:
            logger.error(
                "Execution error for %s: %s", rec.ticker, e,
            )
            return None

    async def _execute_signal(
        self, signal: Signal,
        opp: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Legacy wrapper: convert Signal+opp to TradeRecommendation.

        Kept for backward compatibility with callers that still
        pass raw Signal objects.  New code should use
        ``_execute_recommendation()`` directly.
        """
        rec = TradeRecommendation.from_signal(
            signal, regime_state=self._regime_state,
        )
        if opp:
            rec.composite_score = opp.get(
                "composite_score", 0,
            )
            rec.trade_decision = opp.get(
                "trade_decision", False,
            )
        return await self._execute_recommendation(rec)

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
            from src.brokers.base import OrderSide, OrderType

            manager = await self._get_broker()
            broker_positions = await manager.get_positions()

            # Build price dict from broker positions
            # Use quantity (canonical) with fallback to qty
            prices: Dict[str, float] = {}
            broker_qty: Dict[str, int] = {}
            broker_side: Dict[str, str] = {}
            for pos in broker_positions:
                ticker = getattr(pos, "symbol", getattr(pos, "ticker", "???"))
                current_price = getattr(pos, "current_price", 0)
                if current_price and current_price > 0:
                    prices[ticker] = current_price
                    broker_qty[ticker] = abs(int(
                        getattr(pos, "quantity",
                                getattr(pos, "qty", 0))
                    ))
                    _dir = getattr(pos, "direction",
                                   getattr(pos, "side", "long"))
                    broker_side[ticker] = _dir

            if not prices:
                return

            now = datetime.now(timezone.utc)

            # Use PositionManager to check all exit conditions
            positions_to_close = self.position_mgr.update_all_positions(
                prices, now
            )

            for close_info in positions_to_close:
                ticker = close_info["ticker"]
                exit_price = close_info["price"]
                reason = close_info["reason"]
                qty = broker_qty.get(ticker, 0)
                side = broker_side.get(ticker, "long")

                if qty <= 0:
                    continue

                logger.warning(
                    "Exit signal for %s: %s @ $%.2f",
                    ticker, reason, exit_price,
                )
                try:
                    close_side = (
                        OrderSide.SELL if side == "long"
                        else OrderSide.BUY_TO_COVER
                    )
                    await manager.place_order(
                        ticker=ticker,
                        side=close_side,
                        quantity=qty,
                        order_type=OrderType.MARKET,
                    )
                    logger.info("Closed %s via %s", ticker, reason)

                    # Update circuit breaker with trade PnL
                    closed_pos = self.position_mgr.close_position(
                        ticker, exit_price, reason
                    )
                    if closed_pos:
                        pnl = getattr(
                            closed_pos, "realized_pnl_pct", 0
                        )
                        self.circuit_breaker.update(
                            equity=await self._get_equity(),
                            trade_pnl=pnl,
                        )
                        self._record_learning_outcome(
                            closed_pos, reason
                        )
                        # Sprint 24: persist after close
                        self.position_mgr.save_state()
                        # Sprint 25: send exit notification
                        await self._notify_position_closed(
                            closed_pos, reason,
                        )

                except BrokerError as e:
                    logger.error(
                        "Close order broker error for %s: %s",
                        ticker, e,
                    )
                except Exception as e:
                    logger.error(
                        "Close order failed for %s: %s",
                        ticker, e,
                    )

        except BrokerError as e:
            logger.error("Position monitoring broker error: %s", e)
        except Exception as e:
            logger.error("Position monitoring error: %s", e)

    def _record_learning_outcome(self, closed_pos, reason: str):
        """Feed a closed position into the TradeLearningLoop."""
        try:
            # Resolve direction from position or default
            _dir = getattr(closed_pos, "direction", None)
            if not _dir:
                _dir = (
                    "LONG"
                    if getattr(closed_pos, "quantity", 1) >= 0
                    else "SHORT"
                )

            # Look up entry snapshot from _trades_today
            # Sprint 29: also extract ml_grade, composite_score,
            # regime_at_entry stored by Sprint 28 enrichment
            _snapshot = {}
            _conf = 50
            _ml_grade = ""
            _composite = 0.0
            _regime_at_entry = ""
            for t in self._trades_today:
                if t.get("ticker") == closed_pos.ticker:
                    _snapshot = t.get("entry_snapshot", {})
                    _conf = t.get("confidence", 50)
                    _ml_grade = t.get("ml_grade", "")
                    _composite = t.get("composite_score", 0.0)
                    _regime_at_entry = t.get(
                        "regime_at_entry", "",
                    )
                    break

            _hold = 0.0
            if closed_pos.entry_date and closed_pos.exit_date:
                _dt = closed_pos.exit_date - closed_pos.entry_date
                _hold = _dt.total_seconds() / 3600

            # Sprint 29: merge enriched fields into snapshot
            # so TradeOutcomeRecord has full decision context
            _snapshot["composite_score"] = (
                _composite or _snapshot.get("composite_score", 0)
            )
            _snapshot["ml_grade"] = (
                _ml_grade or _snapshot.get("ml_grade", "")
            )

            record = TradeOutcomeRecord(
                trade_id=closed_pos.position_id,
                ticker=closed_pos.ticker,
                direction=_dir,
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
                confidence=_conf,
                horizon="swing",
                market_regime=_regime_at_entry,
                exit_reason=reason,
                hold_hours=_hold,
                **_snapshot,
            )
            self.learning_loop.record_outcome(record)
            logger.info(
                "Recorded learning outcome: %s %s %.2f%%",
                closed_pos.ticker, reason, closed_pos.realized_pnl_pct,
            )

            # Sprint 34: update leaderboard from *closed* trade
            # (was in _run_eod_cycle using entry records)
            try:
                _pnl = closed_pos.realized_pnl_pct
                self.leaderboard.record_outcome(
                    closed_pos.strategy_id,
                    _pnl > 0,
                    _pnl,
                    regime=_regime_at_entry,
                    direction=_dir,
                    market=getattr(
                        closed_pos, "market", "us"
                    ),
                )
            except Exception as e:
                logger.warning(
                    "Leaderboard update error: %s", e,
                )

            # Sprint 35: record into professional KPI tracker
            try:
                _r_mult = (
                    closed_pos.realized_pnl_pct
                    / (trading_config.risk_per_trade * 100)
                    if trading_config.risk_per_trade > 0
                    else 0.0
                )
                self.kpi.record_trade(
                    pnl_pct=closed_pos.realized_pnl_pct,
                    r_multiple=_r_mult,
                    hold_hours=_hold,
                    predicted_wr=_composite,
                )
            except Exception as e:
                logger.debug("KPI record_trade error: %s", e)

            # Persist to database (best-effort)
            # Sprint 24: propagate real direction, confidence,
            # composite_score from the trade record / snapshot
            try:
                import asyncio as _aio
                _aio.get_event_loop().create_task(
                    self.trade_repo.save_outcome({
                        "trade_id": closed_pos.position_id,
                        "ticker": closed_pos.ticker,
                        "direction": _dir,
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
                        "confidence": _conf,
                        "horizon": "swing",
                        "exit_reason": reason,
                        "regime_at_entry": (
                            _regime_at_entry
                            or self._cached_regime.get("regime")
                        ),
                        "vix_at_entry": (
                            _snapshot.get("vix_at_entry")
                            or self._cached_regime.get("vix")
                        ),
                        "rsi_at_entry": _snapshot.get("rsi_at_entry"),
                        "adx_at_entry": _snapshot.get("adx_at_entry"),
                        "relative_volume": _snapshot.get("relative_volume"),
                        "setup_grade": (
                            _snapshot.get("setup_grade")
                            or _ml_grade
                        ),
                        "composite_score": _composite,
                        "hold_hours": _hold,
                        "feature_snapshot": _snapshot or None,
                    })
                )
            except (OSError, ConnectionError, RuntimeError) as e:
                logger.debug("Trade outcome DB persist skipped: %s", e)

        except Exception as e:
            logger.warning("Learning loop record error: %s", e)


    # ------------------------------------------------------------------
    # Sprint 25: trade-execution notifications
    # ------------------------------------------------------------------

    async def _notify_trade_executed(
        self, rec: "TradeRecommendation", fill_price: float,
    ):
        """Best-effort push notification on trade entry.

        Sprint 36: includes trust metadata (badge, regime,
        freshness, model version) in the notification dict.
        """
        try:
            from src.notifications.multi_channel import MultiChannelNotifier
            notifier = MultiChannelNotifier()
            await notifier.send_trade_alert({
                "ticker": rec.ticker,
                "direction": rec.direction,
                "quantity": rec.position_size_shares or 0,
                "fill_price": fill_price,
                "strategy": rec.strategy_id,
                "confidence": rec.signal_confidence,
                "stop_price": rec.stop_price,
                "composite_score": rec.composite_score,
                "time": (
                    rec.execution_time.isoformat()
                    if rec.execution_time else "now"
                ),
                "trust": rec.trust,
            })
        except Exception as e:
            logger.debug("Trade notification skipped: %s", e)

    async def _notify_position_closed(
        self, closed_pos, reason: str,
    ):
        """Best-effort push notification on position exit.

        Sprint 36: includes trust metadata with PnL breakdown
        (gross/net/fees/slippage) and trade attribution
        (what worked / what failed).
        """
        try:
            from src.notifications.multi_channel import MultiChannelNotifier
            notifier = MultiChannelNotifier()
            _hold = 0.0
            if closed_pos.entry_date and closed_pos.exit_date:
                _dt = closed_pos.exit_date - closed_pos.entry_date
                _hold = _dt.total_seconds() / 3600

            # Sprint 36: build PnL breakdown
            _gross = closed_pos.realized_pnl_pct
            _fees = getattr(
                closed_pos, "fees_pct", 0.05,
            )
            _slip = getattr(
                closed_pos, "slippage_pct", 0.02,
            )
            pnl_bd = PnLBreakdown.from_trade(
                gross_pnl_pct=_gross,
                fees_pct=_fees,
                slippage_pct=_slip,
                hold_hours=_hold,
                exit_reason=reason,
            )

            # Sprint 36: build trade attribution
            _dir = getattr(closed_pos, "direction", "LONG")
            if hasattr(_dir, "value"):
                _dir = _dir.value
            _regime_entry = ""
            for t in self._trades_today:
                if t.get("ticker") == closed_pos.ticker:
                    _regime_entry = t.get(
                        "regime_at_entry", "",
                    )
                    break
            attribution = TradeAttribution.from_closed_trade(
                pnl_pct=_gross,
                exit_reason=reason,
                regime_at_entry=_regime_entry,
                regime_at_exit=self._cached_regime.get(
                    "regime", "",
                ),
                hold_hours=_hold,
                entry_price=closed_pos.entry_price,
                exit_price=closed_pos.exit_price,
                stop_price=getattr(
                    closed_pos, "stop_price", 0,
                ),
                target_price=getattr(
                    closed_pos, "target_price", 0,
                ),
                direction=_dir,
            )

            _badge = (
                TrustBadge.PAPER
                if self.dry_run
                else TrustBadge.LIVE
            )
            trust = TrustMetadata.for_exit(
                badge=_badge,
                pnl=pnl_bd,
                attribution=attribution,
                regime_label=self._cached_regime.get(
                    "regime", "",
                ),
            )

            await notifier.send_exit_alert({
                "ticker": closed_pos.ticker,
                "exit_price": closed_pos.exit_price,
                "pnl_pct": closed_pos.realized_pnl_pct,
                "reason": reason,
                "hold_hours": _hold,
                "trust": trust.to_dict(),
                "pnl_breakdown": pnl_bd.to_dict(),
                "attribution": attribution.to_dict(),
            })
        except Exception as e:
            logger.debug("Exit notification skipped: %s", e)

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

        # 3. Leaderboard now updated on each closed trade
        # in _record_learning_outcome() — Sprint 34
        # (was: loop over _trades_today entries, which have
        #  no realized PnL — only entry snapshots)

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
        """Fetch equity from broker; cache last-known value.

        Sprint 24: eliminates $100k phantom fallback.  Returns
        cached equity on transient errors.  Returns 0.0 only if
        we have *never* successfully fetched.
        """
        try:
            manager = await self._get_broker()
            account = await manager.get_account()
            equity = getattr(account, "portfolio_value", 0.0)
            if equity > 0:
                self._last_known_equity = equity
                self._equity_fetched_at = datetime.now(timezone.utc)
            return equity if equity > 0 else self._last_known_equity
        except (BrokerError, ConnectionError, OSError, RuntimeError) as e:
            logger.debug("Equity fetch fallback to cache: %s", e)
            return self._last_known_equity

    def _is_equity_stale(self) -> bool:
        """True if we have never fetched equity or it's older than threshold."""
        if self._equity_fetched_at is None:
            return True
        age = (datetime.now(timezone.utc) - self._equity_fetched_at).total_seconds()
        return age > self._equity_stale_minutes * 60

    async def _count_positions(self) -> int:
        try:
            manager = await self._get_broker()
            positions = await manager.get_positions()
            return len(positions)
        except BrokerError:
            return 0
        except (ConnectionError, OSError, RuntimeError) as e:
            logger.debug("Position count fallback: %s", e)
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
        """Return cached engine state for API / dashboard.

        Sprint 26: expanded with market_state, equity, positions,
        circuit-breaker status, and PnL so the dashboard can
        display real data instead of hardcoded placeholders.
        """
        # Position / PnL snapshot from PositionManager
        _pm = self.position_mgr
        _open = len(_pm.positions)
        _total_trades = _pm.total_trades if hasattr(_pm, "total_trades") else 0
        _wins = _pm.winning_trades if hasattr(_pm, "winning_trades") else 0
        _win_rate = (_wins / _total_trades * 100) if _total_trades else 0

        return {
            "regime": self._cached_regime,
            "recommendations": self._cached_recommendations,
            "leaderboard": self._cached_leaderboard,
            "cycle_count": self._cycle_count,
            "signals_today": len(self._signals_today),
            "trades_today": len(self._trades_today),
            # Sprint 26: dashboard data
            "market_state": self._context.get("market_state", {}),
            "equity": self._last_known_equity,
            "open_positions": _open,
            "total_trades": _total_trades,
            "win_rate": _win_rate,
            "circuit_breaker": {
                "triggered": self.circuit_breaker.triggered,
                "reason": self.circuit_breaker.trigger_reason,
                "daily_pnl": self.circuit_breaker.daily_pnl,
                "consecutive_losses": (
                    self.circuit_breaker.consecutive_losses
                ),
            },
            "dry_run": self.dry_run,
            # Sprint 30: no-trade readiness snapshot
            "no_trade_readiness": self._no_trade_readiness,
            # Sprint 31: signal cooldown state
            "signal_cooldown_tickers": len(
                self._signal_cooldown._history,
            ),
            # Sprint 35: professional KPIs
            "pro_kpis": self._build_pro_kpis(),
            # Sprint 36: no-trade card
            "no_trade_card": (
                self._no_trade_card.to_dict()
                if self._no_trade_card else None
            ),
            # Sprint 37: professional KPI snapshot
            "kpi_snapshot": self._build_kpi_snapshot(),
        }

    def _build_pro_kpis(self) -> Dict[str, Any]:
        """Sprint 35: professional KPIs for dashboard/API.

        Surfaces: net expectancy, avg R, profit factor, max DD,
        no-trade rate, coverage funnel, and exposure summary.
        """
        kpis: Dict[str, Any] = {}
        try:
            # From leaderboard strategies
            all_strats = self.leaderboard._strategies
            total_trades = 0
            total_wins = 0
            total_pnl = 0.0
            all_pnl: List[float] = []
            for entry in all_strats.values():
                total_trades += entry.get("trades", 0)
                total_wins += entry.get("wins", 0)
                total_pnl += entry.get("total_pnl", 0.0)
                all_pnl.extend(entry.get("pnl_history", []))

            win_rate = (
                total_wins / total_trades
                if total_trades > 0 else 0
            )
            avg_pnl = (
                total_pnl / total_trades
                if total_trades > 0 else 0
            )
            wins_pnl = [p for p in all_pnl if p > 0]
            losses_pnl = [p for p in all_pnl if p <= 0]
            avg_win = (
                sum(wins_pnl) / len(wins_pnl)
                if wins_pnl else 0
            )
            avg_loss = (
                abs(sum(losses_pnl) / len(losses_pnl))
                if losses_pnl else 0
            )
            profit_factor = (
                sum(wins_pnl) / abs(sum(losses_pnl))
                if losses_pnl and sum(losses_pnl) != 0
                else 0.0
            )
            net_expectancy = (
                win_rate * avg_win
                - (1 - win_rate) * avg_loss
            )
            max_dd = min(all_pnl) if all_pnl else 0.0

            # Coverage funnel
            signals_generated = len(self._signals_today)
            trades_executed = len(self._trades_today)
            no_trade_count = getattr(
                self, "_no_trade_count", 0,
            )
            total_cycles = max(self._cycle_count, 1)
            no_trade_rate = no_trade_count / total_cycles

            kpis = {
                "net_expectancy": round(net_expectancy, 4),
                "avg_r": round(avg_pnl, 4),
                "profit_factor": round(profit_factor, 2),
                "max_drawdown_trade": round(max_dd, 4),
                "win_rate": round(win_rate, 4),
                "total_closed_trades": total_trades,
                "no_trade_rate": round(no_trade_rate, 4),
                "coverage_funnel": {
                    "signals_generated": signals_generated,
                    "trades_executed": trades_executed,
                    "no_trade_cycles": no_trade_count,
                },
            }
        except Exception as e:
            logger.debug("Pro KPI build error: %s", e)
            kpis = {"error": str(e)}

        return kpis

    def _build_kpi_snapshot(self) -> Dict[str, Any]:
        """Sprint 37: full KPI snapshot from ProfessionalKPI."""
        try:
            snap = self.kpi.compute()
            return snap.to_dict()
        except (AttributeError, TypeError, ValueError) as e:
            logger.debug("KPI snapshot error: %s", e)
            return {}

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
        }

        # Broker connectivity
        try:
            mgr = await self._get_broker()
            components["broker"] = mgr is not None
        except (BrokerError, ConnectionError, OSError) as e:
            logger.debug("Health check broker probe failed: %s", e)
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
            from src.brokers.base import OrderSide, OrderType

            manager = await self._get_broker()
            positions = await manager.get_positions()
            for pos in positions:
                ticker = getattr(
                    pos, "symbol", getattr(pos, "ticker", "???")
                )
                qty = abs(int(
                    getattr(pos, "quantity",
                            getattr(pos, "qty", 0))
                ))
                _dir = getattr(
                    pos, "direction",
                    getattr(pos, "side", "long"),
                )
                if qty <= 0:
                    continue
                close_side = (
                    OrderSide.SELL if _dir == "long"
                    else OrderSide.BUY_TO_COVER
                )
                try:
                    await manager.place_order(
                        ticker=ticker,
                        side=close_side,
                        quantity=qty,
                        order_type=OrderType.MARKET,
                    )
                    logger.info(
                        "Shutdown: closed %s (%d shares)",
                        ticker, qty,
                    )
                except BrokerError as e:
                    logger.error(
                        "Shutdown close failed %s: %s", ticker, e
                    )
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

    def _calculate_position_size(
        self, signal, edge_pwin: float = 0.0,
        edge_rr: float = 0.0,
        strategy_name: str = "",
    ) -> int:
        """
        Risk-based position sizing with unified multiplier chain.

        Sprint 28: final_size = base_risk
            × confidence_mult   (ML grade: A=1.0 B=0.75 C=0.5)
            × regime_mult       (risk-off=0.5, neutral=0.75, risk-on=1.0)
            × strategy_health   (leaderboard health score 0-1)
            × volatility_mult   (high VIX = reduce)
            × portfolio_heat    (many open positions = reduce)
            × kelly_mult        (half-Kelly when edge data available)
        """
        price = (
            getattr(signal, "entry_price", 0)
            or getattr(signal, "price", 0)
            or getattr(signal, "close", 0)
        )
        if not price or price <= 0:
            return 1

        # Compute stop from signal or config default
        # Sprint 27: direction-aware default stop
        _dir = getattr(signal, "direction", "LONG")
        if hasattr(_dir, "value"):
            _dir = _dir.value
        _is_short = (_dir == "SHORT")

        if _is_short:
            stop_price = price * (1 + trading_config.stop_loss_pct)
        else:
            stop_price = price * (1 - trading_config.stop_loss_pct)
        # TradeRecommendation has stop_price directly;
        # legacy Signal has invalidation.stop_price
        _direct_stop = getattr(signal, "stop_price", 0)
        if _direct_stop and _direct_stop > 0:
            stop_price = _direct_stop
        elif (
            getattr(signal, "invalidation", None)
            and getattr(signal.invalidation, "stop_price", 0)
        ):
            stop_price = signal.invalidation.stop_price

        # ── Base shares from PositionManager ───────────────
        base_shares = 0
        try:
            result = self.position_mgr.calculate_position_size(
                ticker=getattr(signal, "ticker", "UNKNOWN"),
                entry_price=price,
                stop_loss_price=stop_price,
                sector=getattr(signal, "sector", ""),
            )
            if result.get("can_trade") and result.get("shares", 0) > 0:
                base_shares = result["shares"]
        except Exception as e:
            logger.debug("PositionManager sizing fallback: %s", e)

        # Fallback: simple 1% risk using cached equity
        if base_shares <= 0:
            equity = (
                self._last_known_equity
                if self._last_known_equity > 0
                else 10000.0
            )
            risk_per_trade = equity * 0.01
            stop_distance = abs(price - stop_price)
            if stop_distance <= 0:
                return 1
            base_shares = int(risk_per_trade / stop_distance)
            max_shares = int((equity * 0.05) / price)
            base_shares = max(1, min(base_shares, max_shares))

        # ── 1. Confidence / ML grade multiplier ───────────
        _grade = getattr(signal, "ml_grade", "B")
        confidence_mult = {
            "A": 1.0, "B": 0.75, "C": 0.5,
        }.get(_grade, 0.75)

        # ── 2. Regime multiplier ──────────────────────────
        _regime = self._regime_state.get("risk_regime", "neutral")
        regime_mult = {
            "risk_on": 1.0, "neutral": 0.75, "risk_off": 0.5,
        }.get(_regime, 0.75)

        # Sprint 35: graduated regime size_scalar
        _size_scalar = self._regime_state.get(
            "size_scalar", 1.0,
        )
        if isinstance(_size_scalar, (int, float)):
            regime_mult *= _size_scalar

        # ── 3. Strategy health multiplier ─────────────────
        health_mult = self.leaderboard.get_health_multiplier(
            strategy_name or "unknown",
        )

        # ── 4. Volatility multiplier (VIX-based) ─────────
        _vix = self._context.get("market_state", {}).get("vix", 20)
        if _vix > 30:
            vol_mult = 0.5
        elif _vix > 25:
            vol_mult = 0.75
        else:
            vol_mult = 1.0

        # ── 5. Portfolio heat multiplier ──────────────────
        _open = len(self.position_mgr.positions)
        _max = self.position_mgr.params.max_open_positions
        heat_ratio = _open / _max if _max > 0 else 0
        if heat_ratio > 0.8:
            heat_mult = 0.5
        elif heat_ratio > 0.6:
            heat_mult = 0.75
        else:
            heat_mult = 1.0

        # ── 6. Half-Kelly multiplier ──────────────────────
        kelly_mult = 1.0
        if edge_pwin > 0 and edge_rr > 0:
            kelly_f = edge_pwin - (1.0 - edge_pwin) / edge_rr
            kelly_f = max(kelly_f, 0.0)
            kelly_mult = min(kelly_f * 0.5, 1.0)
            if kelly_mult > 0:
                kelly_mult = max(kelly_mult, 0.25)
            else:
                kelly_mult = 0.25

        # ── 7. Portfolio risk-budget multiplier (Sprint 35) ──
        budget_mult = 1.0
        try:
            _ticker = getattr(signal, "ticker", "UNKNOWN")
            _sector = getattr(signal, "sector", "")
            _equity = (
                self._last_known_equity
                if self._last_known_equity > 0
                else 10000.0
            )
            _pos_weight = (price * base_shares) / _equity if _equity > 0 else 0
            _exposure = self.risk_budget.build_exposure(
                list(self.position_mgr.positions.values()),
            )
            _risk_regime = self._regime_state.get("risk_regime", "neutral")
            _beta = getattr(signal, "beta", 1.0)
            if not isinstance(_beta, (int, float)):
                _beta = 1.0
            _dte = getattr(signal, "days_to_earnings", None)
            budget = self.risk_budget.check_budget(
                ticker=_ticker,
                sector=_sector,
                position_weight=_pos_weight,
                exposure=_exposure,
                regime_risk=_risk_regime,
                beta=_beta,
                days_to_earnings=_dte,
            )
            budget_mult = budget.get("size_scalar", 1.0)
            if not budget.get("allowed", True):
                logger.info(
                    "Risk budget blocked %s: %s",
                    _ticker, budget.get("violations", []),
                )
                return 1  # minimum 1 share
        except Exception as e:
            logger.debug("Risk budget check fallback: %s", e)

        # ── Combine all multipliers ───────────────────────
        combined = (
            confidence_mult
            * regime_mult
            * health_mult
            * vol_mult
            * heat_mult
            * kelly_mult
            * budget_mult
        )
        final = int(base_shares * combined)
        return max(1, final)
