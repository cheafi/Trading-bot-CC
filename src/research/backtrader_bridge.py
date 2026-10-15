"""
Backtrader bridge — optional Cerebro runs (mementum/backtrader patterns).

Falls back cleanly when backtrader is not installed. Uses the same OHLCV
frames as the live backtest router (yfinance / MarketDataService).
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    rename = {
        "Open": "open",
        "High": "high",
        "Low": "low",
        "Close": "close",
        "Volume": "volume",
    }
    for src, dst in rename.items():
        if src in out.columns and dst not in out.columns:
            out[dst] = out[src]
    if "close" not in out.columns:
        raise ValueError("missing close column")
    out = out.dropna(subset=["close"])
    out.index = pd.to_datetime(out.index)
    return out


def run_sma_cross_backtest(
    df: pd.DataFrame,
    *,
    fast: int = 10,
    slow: int = 30,
    cash: float = 100_000.0,
    commission: float = 0.001,
) -> dict[str, Any]:
    """Run a simple SMA cross strategy via backtrader Cerebro."""
    try:
        import backtrader as bt
    except ImportError:
        return {
            "ok": False,
            "engine": "backtrader",
            "available": False,
            "hint": "Install backtrader: pip install backtrader",
        }

    if slow <= fast:
        slow = fast + 10
    frame = _normalize_ohlcv(df)
    if len(frame) < slow + 5:
        return {
            "ok": False,
            "engine": "backtrader",
            "error": "insufficient_bars",
            "bars": len(frame),
        }

    class SmaCross(bt.Strategy):
        params = (("fast", fast), ("slow", slow))

        def __init__(self):
            self.fast_ma = bt.ind.SMA(period=self.p.fast)
            self.slow_ma = bt.ind.SMA(period=self.p.slow)
            self._trade_log: list[dict[str, Any]] = []

        def next(self):
            if not self.position and self.fast_ma[0] > self.slow_ma[0]:
                self.buy()
            elif self.position and self.fast_ma[0] < self.slow_ma[0]:
                self.close()

        def notify_trade(self, trade):
            if trade.isclosed:
                self._trade_log.append(
                    {
                        "pnl": round(trade.pnl, 2),
                        "pnl_comm": round(trade.pnlcomm, 2),
                        "bars": int(trade.barlen),
                    }
                )

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(cash)
    cerebro.broker.setcommission(commission=commission)
    data = bt.feeds.PandasData(dataname=frame)
    cerebro.adddata(data)
    strat = cerebro.addstrategy(SmaCross)
    start_val = cerebro.broker.getvalue()
    results = cerebro.run()
    end_val = cerebro.broker.getvalue()
    st = results[0]
    trades = getattr(st, "_trade_log", [])
    ret_pct = (end_val / start_val - 1.0) * 100 if start_val else 0.0
    wins = sum(1 for t in trades if t.get("pnl_comm", 0) > 0)
    return {
        "ok": True,
        "engine": "backtrader",
        "available": True,
        "strategy": f"sma_cross_{fast}_{slow}",
        "bars": len(frame),
        "start_value": round(start_val, 2),
        "end_value": round(end_val, 2),
        "return_pct": round(ret_pct, 2),
        "trades": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1) if trades else None,
        "trade_log": trades[-50:],
        "trust": {
            "mode": "backtest",
            "label": "Historical simulation — gross, commission approx only",
        },
    }
