"""
Forward Outcome Backfill — resolve forward outcomes from journal + market data.

Horizons: 1d/3d/5d/10d/20d. Labels study vs trade; never backtest-as-live-proof.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Set

from src.services.forward_outcome_tracker import (
    HORIZONS_DAYS,
    STUDY_LABEL,
    build_forward_outcome_study,
    compute_forward_outcome,
    summarize_forward_outcomes,
)

logger = logging.getLogger(__name__)

_DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "decision_journal"
)
_OUTCOMES_PATH = os.environ.get("FORWARD_OUTCOMES_PATH") or os.path.join(
    _DATA_DIR, "forward_outcomes.jsonl"
)

PriceFetcher = Callable[[str, int], Optional[float]]


def _ensure_dir(path: str) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)


def _parse_ts(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            return datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return datetime.fromisoformat(ts)
    except ValueError:
        try:
            return datetime.strptime(ts[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def _horizon_elapsed(event_ts: str, horizon: int) -> bool:
    """True when enough calendar days have passed to attempt resolution."""
    dt = _parse_ts(event_ts)
    if dt is None:
        return False
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    elapsed = (now - dt).days
    return elapsed >= horizon


def build_price_series_from_history(
    history_rows: List[Dict[str, Any]],
    *,
    event_ts: str,
    entry_ref: Optional[float] = None,
) -> Dict[int, float]:
    """
    Map horizon days → close price from ordered history rows after event date.
    history_rows: [{date, close}, ...] sorted ascending.
    """
    if not history_rows:
        return {}
    evt_dt = _parse_ts(event_ts)
    if evt_dt is None:
        return {}
    if evt_dt.tzinfo is None:
        evt_dt = evt_dt.replace(tzinfo=timezone.utc)
    evt_date = evt_dt.date()
    future_rows = []
    for row in history_rows:
        d_str = str(row.get("date") or row.get("Date") or "")[:10]
        try:
            d = datetime.strptime(d_str, "%Y-%m-%d").date()
        except ValueError:
            continue
        if d > evt_date:
            future_rows.append((d, float(row.get("close") or row.get("Close") or 0)))
    if not future_rows:
        return {}
    base_price = float(entry_ref) if entry_ref else future_rows[0][1]
    series: Dict[int, float] = {}
    for h in HORIZONS_DAYS:
        idx = h - 1
        if 0 <= idx < len(future_rows):
            series[h] = future_rows[idx][1]
    if base_price and not series.get(1) and future_rows:
        series[1] = future_rows[0][1]
    return series


def enrich_outcome_record(
    outcome: Dict[str, Any],
    *,
    event: Dict[str, Any],
    data_quality: str,
    outcome_source: str,
) -> Dict[str, Any]:
    """Add metadata required by learning layer contract."""
    auth = event.get("authority_state") or {}
    enriched = dict(outcome)
    enriched.update(
        {
            "data_quality": data_quality,
            "outcome_source": outcome_source,
            "authority_state": auth.get("deploy_authority_tier") or "unknown",
            "authority_effect": "none",
            "event_type": event.get("event_type"),
            "event_timestamp": event.get("timestamp"),
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "learning_mode_label": STUDY_LABEL,
            "is_trade_result": bool(
                event.get("event_type") == "TRADE_EXECUTED"
                or outcome.get("is_trade_result")
            ),
            "study_not_trade": not bool(
                event.get("event_type") == "TRADE_EXECUTED"
            ),
            "may_authorize_deploy": False,
            "evidence_only": True,
        }
    )
    if event.get("event_type") in ("WATCH_CANDIDATE", "NEAR_MISS"):
        enriched["outcome_label"] = "study"
    elif event.get("event_type") == "TRADE_EXECUTED":
        enriched["outcome_label"] = "trade"
    else:
        enriched["outcome_label"] = "study"
    return enriched


class ForwardOutcomeStore:
    """Append-only forward outcome persistence."""

    def __init__(self, path: Optional[str] = None) -> None:
        self.path = path or _OUTCOMES_PATH
        _ensure_dir(self.path)

    def persist(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record)
        payload["record_type"] = "forward_outcome"
        line = json.dumps(payload, separators=(",", ":"), default=str) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
        return payload

    def persist_study(
        self, studies: List[Dict[str, Any]], *, event_id: str
    ) -> int:
        written = 0
        for s in studies:
            s = dict(s)
            s["event_id"] = event_id
            self.persist(s)
            written += 1
        return written

    def load_all(self) -> List[Dict[str, Any]]:
        if not os.path.isfile(self.path):
            return []
        rows: List[Dict[str, Any]] = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rows.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return rows

    def resolved_keys(self) -> Set[str]:
        keys: Set[str] = set()
        for r in self.load_all():
            eid = str(r.get("event_id") or "")
            h = r.get("horizon")
            if eid and h is not None:
                keys.add(f"{eid}:{h}")
        return keys

    def count_distinct_events(self) -> int:
        return len({r.get("event_id") for r in self.load_all() if r.get("event_id")})

    def count_with_forward_r(self) -> int:
        return sum(1 for r in self.load_all() if r.get("forward_r") is not None)

    def load_for_event(self, event_id: str) -> List[Dict[str, Any]]:
        return [r for r in self.load_all() if r.get("event_id") == event_id]

    def summarize(self, *, window: int = 20) -> Dict[str, Any]:
        all_rows = self.load_all()
        by_event: Dict[str, List[Dict[str, Any]]] = {}
        for r in all_rows:
            eid = str(r.get("event_id") or "")
            by_event.setdefault(eid, []).append(r)
        studies = list(by_event.values())[-window:]
        summary = summarize_forward_outcomes(studies)
        deploy_outcomes = [
            r
            for r in all_rows
            if r.get("event_type") == "DEPLOY_CANDIDATE" and r.get("forward_r") is not None
        ]
        false_deploy = 0
        if deploy_outcomes:
            false_deploy = sum(
                1 for r in deploy_outcomes if float(r.get("forward_r") or 0) < 0
            )
            summary["false_deploy_rate"] = round(
                false_deploy / len(deploy_outcomes), 3
            )
        else:
            summary["false_deploy_rate"] = None
        summary["total_outcomes"] = len(all_rows)
        summary["distinct_events"] = len(by_event)
        summary["outcome_source"] = "forward_outcome_backfill"
        summary["store_path"] = self.path
        return summary


def backfill_event_outcomes(
    event: Dict[str, Any],
    *,
    price_fetcher: Optional[PriceFetcher] = None,
    price_series: Optional[Dict[int, float]] = None,
    history_rows: Optional[List[Dict[str, Any]]] = None,
    store: Optional[ForwardOutcomeStore] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """Backfill forward outcomes for one journal event."""
    ticker = str(event.get("ticker") or "").upper().strip()
    if not ticker:
        return []
    event_ts = str(event.get("timestamp") or "")
    event_id = str(event.get("event_id") or "")
    had_trade = event.get("event_type") == "TRADE_EXECUTED"

    series = dict(price_series or {})
    if not series and history_rows:
        series = build_price_series_from_history(
            history_rows,
            event_ts=event_ts,
            entry_ref=event.get("entry_ref"),
        )
    if not series and price_fetcher and ticker:
        for h in HORIZONS_DAYS:
            if _horizon_elapsed(event_ts, h):
                px = price_fetcher(ticker, h)
                if px is not None:
                    series[h] = px

    if not series:
        return []

    raw_study = build_forward_outcome_study(
        event, price_series=series, had_real_trade=had_trade
    )
    missing_prices = sum(1 for h in HORIZONS_DAYS if h not in series)
    if missing_prices == len(HORIZONS_DAYS):
        data_quality = "missing"
        outcome_source = "none"
    elif missing_prices > 0:
        data_quality = "partial"
        outcome_source = "market_data" if price_fetcher or history_rows else "manual"
    else:
        data_quality = "complete"
        outcome_source = "market_data" if price_fetcher or history_rows else "manual"

    enriched = [
        enrich_outcome_record(
            s,
            event=event,
            data_quality=data_quality,
            outcome_source=outcome_source,
        )
        for s in raw_study
    ]

    if not dry_run and store:
        st = store or ForwardOutcomeStore()
        st.persist_study(enriched, event_id=event_id)

    return enriched


def backfill_missing_outcomes(
    events: List[Dict[str, Any]],
    *,
    price_fetcher: Optional[PriceFetcher] = None,
    history_provider: Optional[Callable[[str], List[Dict[str, Any]]]] = None,
    store: Optional[ForwardOutcomeStore] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Backfill outcomes for events missing resolution."""
    st = store or ForwardOutcomeStore()
    resolved = st.resolved_keys()
    written = 0
    skipped = 0
    no_ticker = 0
    results: List[Dict[str, Any]] = []

    for event in events:
        eid = str(event.get("event_id") or "")
        ticker = str(event.get("ticker") or "").upper().strip()
        if not ticker:
            no_ticker += 1
            continue
        needs = any(f"{eid}:{h}" not in resolved for h in HORIZONS_DAYS)
        if not needs:
            skipped += 1
            continue
        history = history_provider(ticker) if history_provider else None
        study = backfill_event_outcomes(
            event,
            price_fetcher=price_fetcher,
            history_rows=history,
            store=st,
            dry_run=dry_run,
        )
        if study:
            written += len(study)
            results.append({"event_id": eid, "ticker": ticker, "horizons": len(study)})
        else:
            skipped += 1

    return {
        "written": written,
        "skipped": skipped,
        "no_ticker": no_ticker,
        "dry_run": dry_run,
        "events_processed": len(events),
        "results": results,
        "summary": st.summarize() if not dry_run else {},
    }


def get_forward_outcome_store(path: Optional[str] = None) -> ForwardOutcomeStore:
    return ForwardOutcomeStore(path=path)
