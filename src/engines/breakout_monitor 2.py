"""
Breakout Monitor — Post-Signal Tracking.

After a breakout signal fires, this engine monitors:
1. Did the breakout hold? (close above pivot)
2. Is there follow-through? (continuation volume)
3. Has the breakout failed? (close back inside range)
4. High volume rejection detection
5. Weak follow-through warning

This closes the gap between "signal fired" and
"did the trade actually work?"
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "artifacts")


class BreakoutStatus(str, Enum):
    PENDING = "pending"  # Just broke out
    CONFIRMED = "confirmed"  # Held + follow-through
    WEAK = "weak"  # Held but no volume
    FAILED = "failed"  # Fell back inside range
    REJECTED = "rejected"  # High vol rejection


@dataclass
class BreakoutRecord:
    """Track a single breakout signal."""

    ticker: str
    breakout_date: str
    breakout_price: float
    pivot_price: float
    status: BreakoutStatus = BreakoutStatus.PENDING
    days_since: int = 0
    max_gain_pct: float = 0.0
    current_pct: float = 0.0
    follow_through_volume: bool = False
    close_above_pivot: bool = True
    failure_reasons: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "breakout_date": self.breakout_date,
            "breakout_price": round(self.breakout_price, 2),
            "pivot_price": round(self.pivot_price, 2),
            "status": self.status.value,
            "days_since": self.days_since,
            "max_gain_pct": round(self.max_gain_pct, 2),
            "current_pct": round(self.current_pct, 2),
            "follow_through_volume": self.follow_through_volume,
            "close_above_pivot": self.close_above_pivot,
            "failure_reasons": self.failure_reasons,
        }


class BreakoutMonitor:
    """
    Monitors breakout signals post-entry.

    Detects:
    - Breakout failure (price returns inside range)
    - High volume rejection
    - Weak follow-through (no volume continuation)
    - Confirmed breakout (held + volume)
    """

    def __init__(
        self,
        failure_threshold_pct: float = -2.0,
        confirm_days: int = 3,
        volume_confirm_mult: float = 1.2,
    ):
        self.failure_threshold = failure_threshold_pct
        self.confirm_days = confirm_days
        self.vol_confirm = volume_confirm_mult
        self._active: Dict[str, BreakoutRecord] = {}
        self._history: List[BreakoutRecord] = []

    def register_breakout(
        self,
        ticker: str,
        breakout_price: float,
        pivot_price: float,
        date: Optional[str] = None,
    ) -> BreakoutRecord:
        """Register a new breakout to monitor."""
        rec = BreakoutRecord(
            ticker=ticker,
            breakout_date=date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            breakout_price=breakout_price,
            pivot_price=pivot_price,
        )
        self._active[ticker] = rec
        return rec

    def update(
        self,
        ticker: str,
        current_close: float,
        current_volume: float,
        avg_volume: float,
    ) -> Optional[BreakoutRecord]:
        """
        Update a tracked breakout with new data.

        Returns updated record or None if not tracked.
        """
        rec = self._active.get(ticker)
        if rec is None:
            return None

        rec.days_since += 1
        pct = (current_close - rec.breakout_price) / rec.breakout_price * 100
        rec.current_pct = pct
        rec.max_gain_pct = max(rec.max_gain_pct, pct)

        # Check pivot hold
        rec.close_above_pivot = current_close >= rec.pivot_price * 0.99

        # Volume check
        if avg_volume > 0 and current_volume > avg_volume * self.vol_confirm:
            rec.follow_through_volume = True

        # Status determination
        if not rec.close_above_pivot:
            rec.status = BreakoutStatus.FAILED
            rec.failure_reasons.append(f"Closed below pivot ${rec.pivot_price:.2f}")
        elif rec.max_gain_pct > 3.0 and pct < rec.max_gain_pct * 0.3:
            rec.status = BreakoutStatus.REJECTED
            rec.failure_reasons.append(
                f"Gave back {rec.max_gain_pct - pct:.1f}%" " of gains — rejection"
            )
        elif (
            rec.days_since >= self.confirm_days
            and rec.follow_through_volume
            and rec.close_above_pivot
        ):
            rec.status = BreakoutStatus.CONFIRMED
        elif rec.days_since >= self.confirm_days and not rec.follow_through_volume:
            rec.status = BreakoutStatus.WEAK
            rec.failure_reasons.append(
                "No volume follow-through after" f" {self.confirm_days} days"
            )

        # Archive completed signals
        if rec.status in (
            BreakoutStatus.FAILED,
            BreakoutStatus.REJECTED,
        ):
            self._history.append(rec)
            del self._active[ticker]

        return rec

    def get_active(self) -> List[BreakoutRecord]:
        """Get all actively monitored breakouts."""
        return list(self._active.values())

    def get_failures(
        self,
        limit: int = 20,
    ) -> List[BreakoutRecord]:
        """Get recent breakout failures."""
        return self._history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Summary statistics."""
        total = len(self._history) + len(self._active)
        if total == 0:
            return {
                "total_tracked": 0,
                "active": 0,
                "confirmed": 0,
                "failed": 0,
                "failure_rate": 0,
            }
        confirmed = sum(
            1 for r in self._history if r.status == BreakoutStatus.CONFIRMED
        )
        failed = sum(
            1
            for r in self._history
            if r.status
            in (
                BreakoutStatus.FAILED,
                BreakoutStatus.REJECTED,
            )
        )
        return {
            "total_tracked": total,
            "active": len(self._active),
            "confirmed": confirmed,
            "failed": failed,
            "failure_rate": round(
                failed / max(confirmed + failed, 1) * 100,
                1,
            ),
        }

    def save(self, path: Optional[str] = None):
        """Persist state to JSON."""
        fpath = path or os.path.join(_DATA_DIR, "breakout_monitor.json")
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        data = {
            "active": {k: v.to_dict() for k, v in self._active.items()},
            "history": [r.to_dict() for r in self._history[-100:]],
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: Optional[str] = None):
        """Load state from JSON."""
        fpath = path or os.path.join(_DATA_DIR, "breakout_monitor.json")
        if not os.path.exists(fpath):
            return
        try:
            with open(fpath) as f:
                data = json.load(f)
            for _k, v in data.get("active", {}).items():
                self._active[v["ticker"]] = BreakoutRecord(
                    ticker=v["ticker"],
                    breakout_date=v["breakout_date"],
                    breakout_price=v["breakout_price"],
                    pivot_price=v["pivot_price"],
                    status=BreakoutStatus(v["status"]),
                    days_since=v.get("days_since", 0),
                    max_gain_pct=v.get("max_gain_pct", 0),
                    current_pct=v.get("current_pct", 0),
                )
            logger.info(
                "Loaded %d active breakouts",
                len(self._active),
            )
        except Exception as e:
            logger.warning("Failed to load breakout state: %s", e)
