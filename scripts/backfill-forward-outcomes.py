#!/usr/bin/env python3
"""
Backfill forward outcomes from decision journal + market data.

Usage:
  python scripts/backfill-forward-outcomes.py [--dry-run] [--limit N]
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.decision_journal_store import get_decision_journal_store
from src.services.forward_outcome_backfill import (
    backfill_missing_outcomes,
    get_forward_outcome_store,
)
from src.services.no_edge_tracker import get_no_edge_tracker
from src.services.signal_attribution_store import get_signal_attribution_store


def _history_provider_from_market_data():
    """Build sync history provider wrapping async market data service."""
    try:
        from src.services.market_data import get_market_data_service
    except ImportError:
        return None

    svc = get_market_data_service()

    def provider(ticker: str):
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        try:
            df = loop.run_until_complete(svc.get_history(ticker, period="3mo", interval="1d"))
        except Exception:
            return []
        if df is None or df.empty:
            return []
        rows = []
        for idx, row in df.iterrows():
            d = str(idx)[:10]
            close = row.get("Close") or row.get("close")
            if close is not None:
                rows.append({"date": d, "close": float(close)})
        return rows

    return provider


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill forward outcomes from journal")
    parser.add_argument("--dry-run", action="store_true", help="Compute without writing")
    parser.add_argument("--limit", type=int, default=200, help="Max events to process")
    args = parser.parse_args()

    journal_store = get_decision_journal_store()
    outcome_store = get_forward_outcome_store()
    attribution_store = get_signal_attribution_store()
    no_edge_tracker = get_no_edge_tracker()

    events = journal_store.load_all()[-args.limit :]
    history_provider = None if args.dry_run else _history_provider_from_market_data()

    result = backfill_missing_outcomes(
        events,
        history_provider=history_provider,
        store=outcome_store,
        dry_run=args.dry_run,
    )

    attribution_updated = 0
    if not args.dry_run and result.get("written", 0) > 0:
        all_outcomes = outcome_store.load_all()
        events_by_id = {str(e.get("event_id")): e for e in events if e.get("event_id")}
        attribution_updated = attribution_store.update_from_forward_outcomes(
            all_outcomes[-result["written"] :],
            events_by_id,
        )
        for event in events:
            if event.get("event_type") == "NO_EDGE_TODAY":
                no_edge_tracker.record(
                    session_id=str(event.get("session_id") or ""),
                    truth={
                        "reason_codes": event.get("reason_codes"),
                        "primary_blocker": (event.get("authority_state") or {}).get(
                            "primary_blocker"
                        ),
                        "deploy_qualified_count": 0,
                    },
                )

    summary = {
        "dry_run": args.dry_run,
        "events_loaded": len(events),
        "backfill": result,
        "attribution_updated": attribution_updated,
        "outcome_summary": outcome_store.summarize(),
        "no_edge_summary": no_edge_tracker.summarize(),
        "attribution_summary": attribution_store.summarize(),
        "journal_total": journal_store.count(),
    }
    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
