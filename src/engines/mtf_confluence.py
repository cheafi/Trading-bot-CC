"""
MTFConfluenceGate — Sprint 99
==============================
Multi-timeframe signal alignment gate.

Checks that daily and weekly trend/momentum signals agree before
a trade is approved. Misaligned timeframes reduce conviction and
can block trades below the confluence threshold.

Score components (each 0–1, equally weighted by default):
  1. Weekly trend alignment — price > 10-week SMA (bull) or < (bear)
  2. Daily vs weekly momentum  — both daily and weekly RSI in same zone
  3. Weekly MACD direction     — weekly MACD histogram sign matches daily
  4. Weekly regime match       — current weekly regime agrees with daily

Usage::

    gate = MTFConfluenceGate()
    result = await gate.check("AAPL", daily_data=df, market_data_service=mds)
    # result.confluence_score ∈ [0, 1]
    # result.approved  →  score >= threshold (default 0.60)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ── Thresholds ────────────────────────────────────────────────────────────────

CONFLUENCE_THRESHOLD = 0.60  # minimum score to pass gate
RSI_BULL_MIN = 40  # RSI > 40 → bullish zone
RSI_BEAR_MAX = 60  # RSI < 60 → bearish zone
WEEKLY_SMA_PERIOD = 10  # 10-week SMA (≈ 50-day)
DAILY_SMA_PERIOD = 20  # 20-day SMA for trend direction


# ── Result dataclass ──────────────────────────────────────────────────────────


@dataclass
class ConfluenceResult:
    ticker: str
    confluence_score: float  # 0.0 – 1.0
    approved: bool
    weekly_trend_aligned: bool
    momentum_aligned: bool
    macd_aligned: bool
    regime_aligned: bool
    weekly_rsi: Optional[float]
    daily_rsi: Optional[float]
    weekly_close: Optional[float]
    weekly_sma10: Optional[float]
    notes: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "confluence_score": round(self.confluence_score, 3),
            "approved": self.approved,
            "components": {
                "weekly_trend_aligned": self.weekly_trend_aligned,
                "momentum_aligned": self.momentum_aligned,
                "macd_aligned": self.macd_aligned,
                "regime_aligned": self.regime_aligned,
            },
            "weekly_rsi": self.weekly_rsi,
            "daily_rsi": self.daily_rsi,
            "weekly_close": self.weekly_close,
            "weekly_sma10": self.weekly_sma10,
            "notes": self.notes,
        }


# ── Engine ────────────────────────────────────────────────────────────────────


class MTFConfluenceGate:
    """
    Multi-timeframe alignment gate.

    Given daily bars (provided) and weekly bars (fetched via yfinance or
    passed in), scores timeframe confluence and returns a gating decision.
    """

    async def check(
        self,
        ticker: str,
        daily_data: Optional[pd.DataFrame] = None,
        market_data_service: Any = None,
        direction: str = "LONG",  # LONG | SHORT
    ) -> ConfluenceResult:
        """
        Compute multi-timeframe confluence score.

        Args:
            ticker: Symbol
            daily_data: DataFrame with OHLCV, indexed by date (daily bars).
                        If None, fetched from market_data_service.
            market_data_service: Service for fetching market data.
            direction: Trade direction (affects which regime/trend checks pass).
        """
        notes: list = []

        # ── Fetch data ──────────────────────────────────────────────────────
        daily_df = daily_data
        if daily_df is None or len(daily_df) < 20:
            daily_df = await self._fetch_daily(ticker, market_data_service)

        weekly_df = await self._fetch_weekly(ticker, market_data_service)

        if daily_df is None or len(daily_df) < 20:
            notes.append("insufficient daily data — gate bypassed")
            return self._bypass(ticker, notes)

        if weekly_df is None or len(weekly_df) < WEEKLY_SMA_PERIOD:
            notes.append("insufficient weekly data — gate bypassed")
            return self._bypass(ticker, notes)

        # ── Indicators ────────────────────────────────────────────────────
        daily_close = (
            daily_df["Close"] if "Close" in daily_df.columns else daily_df.iloc[:, 3]
        )
        weekly_close = (
            weekly_df["Close"] if "Close" in weekly_df.columns else weekly_df.iloc[:, 3]
        )

        daily_rsi = _rsi(daily_close, 14)
        weekly_rsi = _rsi(weekly_close, 14)

        daily_sma20 = daily_close.rolling(DAILY_SMA_PERIOD).mean()
        weekly_sma10 = weekly_close.rolling(WEEKLY_SMA_PERIOD).mean()

        # Daily MACD
        daily_macd_hist = _macd_hist(daily_close)
        weekly_macd_hist = _macd_hist(weekly_close)

        d_rsi = float(daily_rsi.iloc[-1]) if not daily_rsi.empty else 50.0
        w_rsi = float(weekly_rsi.iloc[-1]) if not weekly_rsi.empty else 50.0
        w_close = float(weekly_close.iloc[-1])
        w_sma10 = float(weekly_sma10.iloc[-1]) if not weekly_sma10.empty else w_close
        d_sma20 = (
            float(daily_sma20.iloc[-1])
            if not daily_sma20.empty
            else float(daily_close.iloc[-1])
        )
        d_macd_sign = (
            float(daily_macd_hist.iloc[-1]) if not daily_macd_hist.empty else 0.0
        )
        w_macd_sign = (
            float(weekly_macd_hist.iloc[-1]) if not weekly_macd_hist.empty else 0.0
        )

        direction_up = direction.upper() in ("LONG", "BUY")

        # ── Component checks ──────────────────────────────────────────────

        # 1. Weekly trend alignment: weekly close vs 10-week SMA
        if direction_up:
            weekly_trend = w_close > w_sma10
        else:
            weekly_trend = w_close < w_sma10
        if not weekly_trend:
            notes.append(
                f"weekly trend misaligned: close={w_close:.2f} sma10={w_sma10:.2f}"
            )

        # 2. Momentum alignment: both RSIs in same zone
        if direction_up:
            momentum_ok = d_rsi > RSI_BULL_MIN and w_rsi > RSI_BULL_MIN
        else:
            momentum_ok = d_rsi < RSI_BEAR_MAX and w_rsi < RSI_BEAR_MAX
        if not momentum_ok:
            notes.append(f"RSI misaligned: daily={d_rsi:.1f} weekly={w_rsi:.1f}")

        # 3. MACD histogram sign agreement
        if direction_up:
            macd_ok = d_macd_sign > 0 and w_macd_sign > 0
        else:
            macd_ok = d_macd_sign < 0 and w_macd_sign < 0
        if not macd_ok:
            notes.append(
                f"MACD misaligned: daily_hist={d_macd_sign:.3f} weekly_hist={w_macd_sign:.3f}"
            )

        # 4. Regime alignment: daily SMA direction matches weekly SMA direction
        daily_prev_sma = (
            float(daily_sma20.iloc[-5]) if len(daily_sma20.dropna()) > 5 else d_sma20
        )
        weekly_prev_sma = (
            float(weekly_sma10.iloc[-2]) if len(weekly_sma10.dropna()) > 2 else w_sma10
        )
        daily_sma_rising = d_sma20 > daily_prev_sma
        weekly_sma_rising = w_sma10 > weekly_prev_sma
        regime_ok = daily_sma_rising == weekly_sma_rising
        if not regime_ok:
            notes.append(
                f"Regime misaligned: daily_sma_rising={daily_sma_rising} weekly={weekly_sma_rising}"
            )

        # ── Score ─────────────────────────────────────────────────────────
        components = [weekly_trend, momentum_ok, macd_ok, regime_ok]
        score = sum(components) / len(components)
        approved = score >= CONFLUENCE_THRESHOLD

        return ConfluenceResult(
            ticker=ticker,
            confluence_score=score,
            approved=approved,
            weekly_trend_aligned=weekly_trend,
            momentum_aligned=momentum_ok,
            macd_aligned=macd_ok,
            regime_aligned=regime_ok,
            weekly_rsi=round(w_rsi, 1),
            daily_rsi=round(d_rsi, 1),
            weekly_close=round(w_close, 2),
            weekly_sma10=round(w_sma10, 2),
            notes=notes,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _fetch_daily(
        self,
        ticker: str,
        mds: Any,
    ) -> Optional[pd.DataFrame]:
        try:
            if mds is not None:
                return await asyncio.to_thread(
                    mds.get_ohlcv, ticker, period="6mo", interval="1d"
                )
            import yfinance as yf

            return await asyncio.to_thread(
                lambda: yf.download(ticker, period="6mo", interval="1d", progress=False)
            )
        except Exception as e:
            logger.debug("MTF daily fetch failed for %s: %s", ticker, e)
            return None

    async def _fetch_weekly(
        self,
        ticker: str,
        mds: Any,
    ) -> Optional[pd.DataFrame]:
        try:
            import yfinance as yf

            df = await asyncio.to_thread(
                lambda: yf.download(ticker, period="2y", interval="1wk", progress=False)
            )
            return df if df is not None and len(df) >= WEEKLY_SMA_PERIOD else None
        except Exception as e:
            logger.debug("MTF weekly fetch failed for %s: %s", ticker, e)
            return None

    def _bypass(self, ticker: str, notes: list) -> ConfluenceResult:
        """Return a pass-through result when data is unavailable."""
        return ConfluenceResult(
            ticker=ticker,
            confluence_score=0.5,
            approved=True,  # fail-open when data unavailable
            weekly_trend_aligned=True,
            momentum_aligned=True,
            macd_aligned=True,
            regime_aligned=True,
            weekly_rsi=None,
            daily_rsi=None,
            weekly_close=None,
            weekly_sma10=None,
            notes=notes + ["gate bypassed (fail-open)"],
        )


# ── Indicator helpers ─────────────────────────────────────────────────────────


def _rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, float("nan"))
    return 100 - 100 / (1 + rs)


def _macd_hist(
    series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.Series:
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return macd_line - signal_line


# ── Module singleton ──────────────────────────────────────────────────────────

_gate_instance: Optional[MTFConfluenceGate] = None


def get_mtf_gate() -> MTFConfluenceGate:
    global _gate_instance
    if _gate_instance is None:
        _gate_instance = MTFConfluenceGate()
    return _gate_instance
