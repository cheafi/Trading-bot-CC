#!/usr/bin/env python3
"""
Evaluate Alpha Quality Control Tower — OI vs baselines with persisted learning.

Usage:
  python scripts/evaluate-alpha-quality.py [--dry-run] [--window 20d|60d|120d] [--min-sample N] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.alpha_quality_evaluator import evaluate_alpha_quality
from src.services.alpha_quality_store import get_alpha_quality_store
from src.services.decision_journal_store import get_decision_journal_store
from src.services.forward_outcome_backfill import get_forward_outcome_store
from src.services.no_edge_tracker import get_no_edge_tracker
from src.services.opportunity_intelligence_store import get_opportunity_intelligence_store
from src.services.signal_attribution_store import get_signal_attribution_store


def _parse_window(raw: str) -> int:
    s = str(raw).lower().strip().rstrip("d")
    try:
        return int(s)
    except ValueError:
        return 20


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Alpha Quality Control Tower")
    parser.add_argument("--dry-run", action="store_true", help="Compute without persisting snapshot")
    parser.add_argument("--window", default="20d", help="Lookback window: 20d, 60d, or 120d")
    parser.add_argument("--min-sample", type=int, default=12, help="Minimum sample for lift reporting")
    parser.add_argument("--json", action="store_true", help="Emit JSON report to stdout")
    args = parser.parse_args()

    window_days = _parse_window(args.window)
    journal_store = get_decision_journal_store()
    outcome_store = get_forward_outcome_store()
    oi_store = get_opportunity_intelligence_store()
    attribution_store = get_signal_attribution_store()
    no_edge_tracker = get_no_edge_tracker()

    forward_summary = outcome_store.summarize(window=window_days)
    oi_snapshots = oi_store.load_snapshots(limit=window_days * 4)
    oi_transitions = oi_store.load_transitions(limit=window_days * 4)
    forward_outcomes = outcome_store.load_all()[-window_days * 4 :]
    no_edge_rows = no_edge_tracker.load_all()[-window_days:] if hasattr(no_edge_tracker, "load_all") else []

    report = evaluate_alpha_quality(
        opportunities=oi_snapshots,
        score_snapshots=oi_snapshots,
        stage_transitions=oi_transitions,
        forward_outcomes=forward_outcomes,
        forward_summary=forward_summary,
        attribution=attribution_store.summarize(),
        no_edge_tracking={"session_id": "", "samples": len(no_edge_rows)},
        window_days=window_days,
        persist=not args.dry_run,
        store=get_alpha_quality_store(),
    )

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(f"Alpha Quality — status={report.get('status')} n={report.get('sample_size')}")
        print(f"  OI lift: {report.get('oi_lift_display')}")
        print(f"  Cost-adj expectancy: {report.get('cost_adj_expectancy_display')}")
        print(f"  Overfit risk: {report.get('overfit_risk')}")
        print(f"  Conversion: {report.get('conversion_quality')}")
        if report.get("snapshot_id"):
            print(f"  Snapshot: {report['snapshot_id']}")
        elif args.dry_run:
            print("  (dry-run — not persisted)")

    _ = journal_store.summary()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
