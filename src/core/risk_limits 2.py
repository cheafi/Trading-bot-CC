"""
Unified Risk Limits — Single Source of Truth
=============================================

All risk parameters for the platform live here. No other module should
hardcode risk thresholds. Import from here:

    from src.core.risk_limits import RISK, BACKTEST_DEFAULTS, SIGNAL_THRESHOLDS

Resolves the conflict between:
  - src/engines/portfolio_risk_budget.py  (5% single-name, 15 max positions)
  - src/algo/position_manager.py          (10% single-name, 5 max positions)
  - src/core/config.py                    (various defaults)
  - src/api/main.py                       (inline magic numbers)

Env-var overrides: set RISK_MAX_POSITION_PCT=0.03 to override 5% default.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(key: str, default: float) -> float:
    return float(os.environ.get(key, default))


def _env_int(key: str, default: int) -> int:
    return int(os.environ.get(key, default))


# ═══════════════════════════════════════════════════════════════
# Portfolio-Level Risk Limits
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class PortfolioRiskLimits:
    """Hard limits for portfolio risk management."""

    # ── Position limits ──
    max_position_pct: float = field(
        default_factory=lambda: _env_float("RISK_MAX_POSITION_PCT", 0.05)
    )  # 5% max single-name weight
    max_positions: int = field(
        default_factory=lambda: _env_int("RISK_MAX_POSITIONS", 10)
    )
    max_sector_pct: float = field(
        default_factory=lambda: _env_float("RISK_MAX_SECTOR_PCT", 0.30)
    )  # 30% max in any sector
    max_correlated_names: int = 3  # max names in a correlation bucket

    # ── Drawdown circuit breakers ──
    max_drawdown_pct: float = field(
        default_factory=lambda: _env_float("RISK_MAX_DRAWDOWN_PCT", 0.15)
    )  # 15% → kill switch, no new trades
    drawdown_warning_pct: float = 0.08  # 8% → reduce size by 50%
    daily_loss_limit_pct: float = field(
        default_factory=lambda: _env_float("RISK_DAILY_LOSS_LIMIT_PCT", 0.03)
    )  # 3% daily loss → halt trading

    # ── Exposure limits ──
    max_gross_exposure: float = 1.0  # 100% gross (no leverage)
    risk_off_max_exposure: float = 0.50  # 50% in risk-off regime
    max_portfolio_beta: float = 1.5

    # ── Earnings / event blackout ──
    earnings_blackout_days: int = 2  # no new positions within 2 days of earnings
    earnings_max_exposure_pct: float = 0.10  # max 10% total in earnings-adjacent names

    # ── Volatility scaling ──
    target_annual_vol: float = 0.15  # 15% target portfolio vol
    max_atr_pct_for_entry: float = 0.06  # don't enter if ATR% > 6%
    min_atr_pct_for_entry: float = 0.005  # dead stock filter

    # ── High-beta cluster ──
    max_high_beta_pct: float = 0.25  # 25% max in high-beta names


# ═══════════════════════════════════════════════════════════════
# Signal / Entry Thresholds
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class SignalThresholds:
    """Configurable entry/exit thresholds — replaces magic numbers."""

    # ── RSI ──
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    rsi_momentum_low: float = 50.0
    rsi_momentum_high: float = 75.0
    rsi_swing_entry: float = 45.0
    rsi_near_oversold: float = 35.0  # "approaching oversold" — display / why-buy
    rsi_near_overbought: float = 65.0  # symmetric complement

    # ── Volume ──
    volume_surge_threshold: float = 1.3  # breakout needs 1.3x avg volume
    volume_strong_surge: float = 1.5  # strong institutional interest
    volume_confirmation: float = 1.0  # momentum needs 1.0x avg

    # ── SMA proximity ──
    mean_rev_sma_distance: float = 0.03  # price < SMA20 * (1 - this)
    swing_sma_distance: float = 0.02  # price > SMA50 * (1 - this)

    # ── Stop loss multiples (of ATR) ──
    stop_atr_multiplier_momentum: float = 2.0
    stop_atr_multiplier_breakout: float = 1.5
    stop_atr_multiplier_mean_rev: float = 1.5
    stop_atr_multiplier_swing: float = 2.0

    # ── Target returns ──
    target_trending: float = 0.15
    target_normal: float = 0.08
    target_breakout_trending: float = 0.12
    target_breakout_normal: float = 0.07
    target_swing_trending: float = 0.10
    target_swing_normal: float = 0.06

    # ── Max hold days ──
    max_hold_momentum_trending: int = 60
    max_hold_momentum_normal: int = 25
    max_hold_breakout_trending: int = 45
    max_hold_breakout_normal: int = 20
    max_hold_mean_rev: int = 20
    max_hold_swing_trending: int = 40
    max_hold_swing_normal: int = 15

    # ── Confidence ──
    abstention_threshold: float = 35.0  # composite < this → NO TRADE
    strong_buy_threshold: float = 85.0
    buy_threshold: float = 70.0
    watch_threshold: float = 55.0
    high_confidence_threshold: float = 75.0  # display bucket: "high" vs "medium"

    # ── VIX ──
    vix_crisis: float = 35.0  # VIX > this → NO TRADE
    vix_elevated: float = 25.0  # VIX > this → reduce size


# ═══════════════════════════════════════════════════════════════
# Backtest Defaults
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class BacktestDefaults:
    """Default parameters for backtest engine."""

    account_size: float = field(
        default_factory=lambda: _env_float("BACKTEST_ACCOUNT_SIZE", 100_000)
    )
    commission_per_share: float = 0.005
    min_commission: float = 1.00
    slippage_base_bps: float = 5.0
    max_concurrent_positions: int = 3


# ═══════════════════════════════════════════════════════════════
# Universe Quality Gates
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class UniverseFilterGates:
    """
    Hard quality gates applied before any strategy runs.
    Canonical source for UniverseFilter.DEFAULT_GATES in signal_engine.py.
    Override via env vars or direct construction.
    """

    min_price: float = field(
        default_factory=lambda: _env_float("UNIVERSE_MIN_PRICE", 5.0)
    )  # No penny stocks
    min_dollar_vol_20d: float = field(
        default_factory=lambda: _env_float("UNIVERSE_MIN_DOLLAR_VOL", 5_000_000)
    )  # $5M daily dollar volume
    min_avg_volume_20d: int = field(
        default_factory=lambda: _env_int("UNIVERSE_MIN_AVG_VOL", 200_000)
    )  # 200K shares/day
    max_spread_pct: float = field(
        default_factory=lambda: _env_float("UNIVERSE_MAX_SPREAD_PCT", 1.0)
    )  # (high-low)/close proxy < 1%
    min_market_cap: float = field(
        default_factory=lambda: _env_float("UNIVERSE_MIN_MARKET_CAP", 500_000_000)
    )  # $500M market cap
    min_history_days: int = field(
        default_factory=lambda: _env_int("UNIVERSE_MIN_HISTORY_DAYS", 60)
    )
    earnings_blackout_days: int = field(
        default_factory=lambda: _env_int("UNIVERSE_EARNINGS_BLACKOUT_DAYS", 2)
    )

    def as_dict(self) -> dict:
        """Return as dict compatible with UniverseFilter(overrides=...)."""
        return {
            "min_price": self.min_price,
            "min_dollar_vol_20d": self.min_dollar_vol_20d,
            "min_avg_volume_20d": self.min_avg_volume_20d,
            "max_spread_pct": self.max_spread_pct,
            "min_market_cap": self.min_market_cap,
            "min_history_days": self.min_history_days,
            "earnings_blackout_days": self.earnings_blackout_days,
        }


# ═══════════════════════════════════════════════════════════════
# VIX Regime Thresholds
# ═══════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class VIXThresholds:
    """
    VIX-based regime thresholds — canonical source for regime_router.py constants.
    Override via env vars for paper-trading / stress-testing.
    """

    low: float = field(
        default_factory=lambda: _env_float("VIX_LOW", 14.0)
    )  # Below this → calm / RISK_ON
    mid: float = field(
        default_factory=lambda: _env_float("VIX_MID", 20.0)
    )  # Transition zone
    high: float = field(
        default_factory=lambda: _env_float("VIX_HIGH", 28.0)
    )  # Elevated → reduce size
    crisis: float = field(
        default_factory=lambda: _env_float("VIX_CRISIS", 35.0)
    )  # Crisis → NO TRADE (overrides all signals)


# ═══════════════════════════════════════════════════════════════
# Singleton instances
# ═══════════════════════════════════════════════════════════════

RISK = PortfolioRiskLimits()
SIGNAL_THRESHOLDS = SignalThresholds()
BACKTEST_DEFAULTS = BacktestDefaults()
UNIVERSE_GATES = UniverseFilterGates()
VIX = VIXThresholds()
