# AlgoStrategyAdapter - bridges src.algo.IStrategy to src.strategies.BaseStrategy
# Converts DataFrame-centric analyse()/populate_*_trend() to generate_signals() API
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from uuid import uuid4
import numpy as np
import pandas as pd

from src.core.models import Direction, Horizon, Invalidation, Signal, StopType, Target
from src.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)

_HORIZON_LOOKUP = {
    "1m": Horizon.INTRADAY, "5m": Horizon.INTRADAY, "15m": Horizon.INTRADAY,
    "30m": Horizon.INTRADAY, "1h": Horizon.INTRADAY,
    "4h": Horizon.SWING_1_5D, "1d": Horizon.SWING_5_15D,
    "1w": Horizon.POSITION_15_60D,
}


class AlgoStrategyAdapter(BaseStrategy):
    """Wraps an IStrategy (src.algo) so it fulfills the BaseStrategy contract."""

    def __init__(self, algo_strategy, config=None):
        if isinstance(algo_strategy, type):
            self._algo = algo_strategy()
        else:
            self._algo = algo_strategy
        self.STRATEGY_ID = self._algo.STRATEGY_ID
        self.VERSION = getattr(self._algo, "VERSION", "1.0")
        tf_val = getattr(self._algo, "timeframe", None)
        tf_str = tf_val.value if hasattr(tf_val, "value") else str(tf_val or "1d")
        self.HORIZON = _HORIZON_LOOKUP.get(tf_str, Horizon.SWING_5_15D)
        super().__init__(config)

    def generate_signals(self, universe, features, market_data=None):
        result_signals = []
        for ticker in universe:
            try:
                ticker_df = self._get_ohlcv(ticker, features)
                if ticker_df is None:
                    continue
                min_bars = getattr(self._algo, "startup_candle_count", 50)
                if len(ticker_df) < min_bars:
                    continue
                analyzed = self._algo.analyze(
                    ticker_df.copy(), {"ticker": ticker, "timeframe": "1d"}
                )
                sigs = self._make_signals(ticker, analyzed)
                result_signals.extend(sigs)
            except Exception as exc:
                logger.debug(f"Adapter({self.STRATEGY_ID}) skip {ticker}: {exc}")
        return result_signals

    def _get_ohlcv(self, ticker, features):
        """Pull a single ticker OHLCV slice from the feature frame."""
        needed = {"open", "high", "low", "close", "volume"}
        if isinstance(features.index, pd.MultiIndex):
            vals = features.index.get_level_values(0)
            if ticker in vals:
                df = features.loc[ticker].copy()
                if needed.issubset(df.columns):
                    return df
        if "ticker" in features.columns:
            mask = features["ticker"] == ticker
            if mask.any():
                df = features.loc[mask].copy()
                if needed.issubset(df.columns):
                    return df
        if needed.issubset(features.columns):
            return features.copy()
        return None

    def _make_signals(self, ticker, analyzed):
        """Convert last enter_long/enter_short rows into Signal objects."""
        out = []
        if analyzed.empty:
            return out
        last = analyzed.iloc[-1]
        price = float(last.get("close", 0))
        if price <= 0:
            return out

        for col, dirn in [("enter_long", Direction.LONG), ("enter_short", Direction.SHORT)]:
            if last.get(col, 0) != 1:
                continue
            stop_pct = abs(getattr(self._algo, "stoploss", 0.05))
            roi_tbl = getattr(self._algo, "minimal_roi", {"0": 0.10})
            tgt_pct = max(roi_tbl.values()) if roi_tbl else 0.10

            if dirn == Direction.LONG:
                stop = round(price * (1 - stop_pct), 2)
                t1 = round(price * (1 + tgt_pct * 0.5), 2)
                t2 = round(price * (1 + tgt_pct), 2)
            else:
                stop = round(price * (1 + stop_pct), 2)
                t1 = round(price * (1 - tgt_pct * 0.5), 2)
                t2 = round(price * (1 - tgt_pct), 2)

            rr = tgt_pct / stop_pct if stop_pct else 1.0
            rsi = last.get("rsi", 50)
            adx = last.get("adx", 20)
            rv = last.get("relative_volume", last.get("volume_ratio", 1.0))
            conf = int(min(100, max(30,
                50 + (10 if adx > 25 else 0)
                + (5 if 1.2 < rv < 5 else 0)
                + (5 if dirn == Direction.LONG and 40 < rsi < 70 else 0)
                + (5 if dirn == Direction.SHORT and 30 < rsi < 60 else 0)
            )))

            try:
                sig = Signal(
                    id=uuid4(), ticker=ticker, direction=dirn,
                    horizon=self.HORIZON, entry_price=price,
                    invalidation=Invalidation(stop_price=stop, stop_type=StopType.HARD),
                    targets=[
                        Target(price=t1, pct_position=50),
                        Target(price=t2, pct_position=50),
                    ],
                    entry_logic=f"{self.STRATEGY_ID} entry signal",
                    catalyst="Technical setup",
                    key_risks=["Market regime shift", "False breakout"],
                    confidence=conf,
                    rationale=f"{self.STRATEGY_ID} {dirn.value} at ${price:.2f}",
                    risk_reward_ratio=round(rr, 2),
                    strategy_id=self.STRATEGY_ID,
                    strategy_version=self.VERSION,
                )
                out.append(sig)
            except Exception as exc:
                logger.warning(f"Signal build failed {ticker}/{self.STRATEGY_ID}: {exc}")
        return out
