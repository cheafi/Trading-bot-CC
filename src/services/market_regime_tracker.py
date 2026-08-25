"""
Market regime tracker — persistent regime timeline + pressure score.

Inspired by the reference 大盤 concept but adapted truthfully to CC. The
existing regime services (regime_service / index_regime / crisis_regime) compute
a point-in-time posture each request; this module gives that posture *memory*:

  - distribution-day count (down days on rising volume, O'Neil-style proxy)
  - follow-through / rally-attempt state machine
  - breadth-regime health over a window
  - regime-change timeline (when trend / tradeability transitions)
  - sector leadership / laggard persistence across sessions
  - a composite market_pressure_score (0-100, higher = more risk-off pressure)

Authority: research_only / monitor-only and downgrade-only (registered as
SIGNAL_REGIME_TIMELINE). It can sharpen "why WAIT/NO_TRADE/SELECTIVE" and inform
Dashboard/Discovery context. It can NEVER authorize deploy, and it may only push
posture toward caution (downgrade), never upgrade tradeability.

Persistence: append-only JSONL daily snapshots under
data/artifacts/regime_timeline.jsonl. Deterministic and network-free so it is
fully testable in CI from injected snapshots.
"""

from __future__ import annotations

import json
import os
import threading
from typing import Any, Dict, List, Optional

from src.services.signal_provenance import (
    SIGNAL_REGIME_TIMELINE,
    build_provenance_envelope,
)

DEFAULT_TIMELINE_PATH = os.path.join("data", "artifacts", "regime_timeline.jsonl")

# A distribution day clears when a fresh follow-through / rally is confirmed, or
# it simply ages out of the rolling window.
_DISTRIBUTION_WINDOW = 25
_DISTRIBUTION_DROP_PCT = 0.2  # index off >= 0.2% counts as a down day

FOLLOW_THROUGH_NONE = "none"
FOLLOW_THROUGH_ATTEMPT = "rally_attempt"
FOLLOW_THROUGH_CONFIRMED = "confirmed"
FOLLOW_THROUGH_FAILED = "failed"


def breadth_health(breadth: Optional[float]) -> str:
    if breadth is None:
        return "unknown"
    try:
        b = float(breadth)
    except (TypeError, ValueError):
        return "unknown"
    if b >= 65:
        return "broad"
    if b >= 50:
        return "constructive"
    if b >= 35:
        return "narrowing"
    return "thin"


class MarketRegimeTracker:
    """Append-only daily regime snapshot store with derived analytics."""

    def __init__(self, path: str = DEFAULT_TIMELINE_PATH) -> None:
        self.path = path
        self._lock = threading.Lock()

    # -- io -----------------------------------------------------------------
    def _append(self, snapshot: Dict[str, Any]) -> None:
        with self._lock:
            os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(snapshot, separators=(",", ":")) + "\n")

    def snapshots(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.path):
            return []
        rows: List[Dict[str, Any]] = []
        with self._lock:
            with open(self.path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        # Dedup by date keeping latest; sort chronologically.
        by_date: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            d = r.get("date")
            if d:
                by_date[d] = r
        return [by_date[d] for d in sorted(by_date)]

    # -- write --------------------------------------------------------------
    def record_snapshot(
        self,
        *,
        date: str,
        trend: str,
        tradeability: str,
        index_change_pct: Optional[float] = None,
        volume_vs_prior: Optional[float] = None,
        vix: Optional[float] = None,
        breadth: Optional[float] = None,
        leaders: Optional[List[str]] = None,
        laggards: Optional[List[str]] = None,
        live: bool = False,
    ) -> None:
        """Record one daily market snapshot.

        volume_vs_prior is today's volume / prior day's volume (>1 = rising).
        """
        self._append(
            {
                "date": date,
                "trend": str(trend).upper(),
                "tradeability": str(tradeability).upper(),
                "index_change_pct": index_change_pct,
                "volume_vs_prior": volume_vs_prior,
                "vix": vix,
                "breadth": breadth,
                "breadth_health": breadth_health(breadth),
                "leaders": list(leaders or []),
                "laggards": list(laggards or []),
                "live": bool(live),
            }
        )

    # -- analytics ----------------------------------------------------------
    def distribution_day_count(
        self, window: int = _DISTRIBUTION_WINDOW
    ) -> Dict[str, Any]:
        """Count distribution days in the trailing window.

        Distribution day = index closes down >= _DISTRIBUTION_DROP_PCT on volume
        higher than the prior session. Missing volume/price data is excluded
        (and surfaced), never guessed.
        """
        snaps = self.snapshots()[-window:]
        usable = [
            s
            for s in snaps
            if s.get("index_change_pct") is not None
            and s.get("volume_vs_prior") is not None
        ]
        count = sum(
            1
            for s in usable
            if s["index_change_pct"] <= -_DISTRIBUTION_DROP_PCT
            and s["volume_vs_prior"] > 1.0
        )
        if count >= 6:
            severity = "heavy"
        elif count >= 4:
            severity = "elevated"
        elif count >= 1:
            severity = "watch"
        else:
            severity = "clean"
        return {
            "count": count,
            "window": window,
            "sessions_evaluated": len(usable),
            "sessions_missing_data": len(snaps) - len(usable),
            "severity": severity,
        }

    def follow_through_state(self) -> Dict[str, Any]:
        """Lightweight rally-attempt / follow-through state machine.

        Confirmed = a >=1.2% up day on rising volume after at least one prior
        down/attempt session. Failed = an attempt undercut by a fresh >=1% down
        day. This is a proxy, explicitly labeled as such — not an O'Neil FTD.
        """
        snaps = self.snapshots()
        usable = [s for s in snaps if s.get("index_change_pct") is not None]
        if len(usable) < 2:
            return {"state": FOLLOW_THROUGH_NONE, "reason": "insufficient_history"}
        prior, latest = usable[-2], usable[-1]
        chg = latest["index_change_pct"]
        vol = latest.get("volume_vs_prior")
        rising_vol = vol is None or vol > 1.0
        if chg >= 1.2 and rising_vol and prior["index_change_pct"] <= 0:
            state = FOLLOW_THROUGH_CONFIRMED
        elif chg <= -1.0 and prior["index_change_pct"] > 0:
            state = FOLLOW_THROUGH_FAILED
        elif chg > 0:
            state = FOLLOW_THROUGH_ATTEMPT
        else:
            state = FOLLOW_THROUGH_NONE
        return {
            "state": state,
            "latest_change_pct": chg,
            "rising_volume": rising_vol,
            "proxy": True,
        }

    def regime_timeline(self) -> List[Dict[str, Any]]:
        """Transitions in trend or tradeability, chronologically."""
        snaps = self.snapshots()
        timeline: List[Dict[str, Any]] = []
        prev: Optional[Dict[str, Any]] = None
        for s in snaps:
            if (
                prev is None
                or s["trend"] != prev["trend"]
                or s["tradeability"] != prev["tradeability"]
            ):
                timeline.append(
                    {
                        "date": s["date"],
                        "trend": s["trend"],
                        "tradeability": s["tradeability"],
                        "from_trend": prev["trend"] if prev else None,
                        "from_tradeability": prev["tradeability"] if prev else None,
                    }
                )
            prev = s
        return timeline

    def sector_persistence(self, window: int = 10) -> Dict[str, Any]:
        """How often each sector appears as leader / laggard over the window."""
        snaps = self.snapshots()[-window:]
        leader_counts: Dict[str, int] = {}
        laggard_counts: Dict[str, int] = {}
        for s in snaps:
            for sec in s.get("leaders", []):
                leader_counts[sec] = leader_counts.get(sec, 0) + 1
            for sec in s.get("laggards", []):
                laggard_counts[sec] = laggard_counts.get(sec, 0) + 1
        return {
            "window": window,
            "sessions": len(snaps),
            "leader_cluster": sorted(
                leader_counts.items(), key=lambda kv: kv[1], reverse=True
            ),
            "laggard_cluster": sorted(
                laggard_counts.items(), key=lambda kv: kv[1], reverse=True
            ),
        }

    def market_pressure_score(self) -> Dict[str, Any]:
        """Composite 0-100 risk-off pressure. Higher = more caution warranted.

        Downgrade-only by construction: it is a *caution* score, never a
        green-light. Components and their contributions are returned so the
        operator sees exactly why pressure is high — no black box.
        """
        snaps = self.snapshots()
        if not snaps:
            return {
                "score": None,
                "posture": "unknown",
                "degraded": True,
                "components": {},
                "evidence_quality": {"sessions": 0, "sample_label": "empty"},
            }
        latest = snaps[-1]
        dist = self.distribution_day_count()
        ft = self.follow_through_state()

        components: Dict[str, float] = {}
        # VIX pressure (0-35)
        vix = latest.get("vix")
        if vix is not None:
            components["vix"] = round(min(35.0, max(0.0, (float(vix) - 12) * 1.5)), 2)
        # Distribution-day pressure (0-30)
        components["distribution_days"] = round(min(30.0, dist["count"] * 5.0), 2)
        # Breadth pressure (0-20) — thinner breadth = more pressure
        b = latest.get("breadth")
        if b is not None:
            components["breadth"] = round(min(20.0, max(0.0, (60 - float(b)) * 0.5)), 2)
        # Follow-through pressure (0-15)
        ft_press = {
            FOLLOW_THROUGH_FAILED: 15.0,
            FOLLOW_THROUGH_NONE: 8.0,
            FOLLOW_THROUGH_ATTEMPT: 4.0,
            FOLLOW_THROUGH_CONFIRMED: 0.0,
        }.get(ft["state"], 8.0)
        components["follow_through"] = ft_press

        score = round(min(100.0, sum(components.values())), 2)
        if score >= 65:
            posture = "defensive"
        elif score >= 40:
            posture = "neutral"
        else:
            posture = "constructive"
        live = bool(latest.get("live"))
        return {
            "score": score,
            "posture": posture,
            "passive_baseline_posture": posture,
            "components": components,
            "degraded": vix is None or b is None,
            "evidence_quality": {
                "sessions": len(snaps),
                "sample_label": "robust" if len(snaps) >= 20 else "thin",
                "live": live,
                "data_mode": "live" if live else "simulated",
            },
        }


_DEFAULT_REGIME_TRACKER: Optional[MarketRegimeTracker] = None


def get_regime_tracker() -> MarketRegimeTracker:
    global _DEFAULT_REGIME_TRACKER
    if _DEFAULT_REGIME_TRACKER is None:
        _DEFAULT_REGIME_TRACKER = MarketRegimeTracker()
    return _DEFAULT_REGIME_TRACKER


def build_regime_timeline_context(
    tracker: Optional[MarketRegimeTracker] = None,
    *,
    degraded: bool = False,
) -> Dict[str, Any]:
    """Research/monitor-only payload: timeline + pressure + persistence.

    Authority: research_only, downgrade-only (SIGNAL_REGIME_TIMELINE). It informs
    posture and sharpens WAIT/NO_TRADE rationale; it never authorizes deploy and
    can only push toward caution.
    """
    trk = tracker or get_regime_tracker()
    pressure = trk.market_pressure_score()
    snaps = trk.snapshots()
    return build_provenance_envelope(
        signal_type=SIGNAL_REGIME_TIMELINE,
        source="regime_timeline.jsonl",
        degraded=degraded or pressure.get("degraded", False) or not snaps,
        data_mode="research_only",
        extra={
            "market_pressure": pressure,
            "distribution_days": trk.distribution_day_count(),
            "follow_through": trk.follow_through_state(),
            "regime_timeline": trk.regime_timeline(),
            "sector_persistence": trk.sector_persistence(),
            "note": "Regime context only — informs WAIT rationale, never authorizes deploy.",
        },
    )
