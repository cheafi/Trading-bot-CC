#!/usr/bin/env python3
"""
Generate Alpha Review report from persisted Alpha QA snapshots.

Usage:
  python scripts/generate-alpha-review.py [--window 20d|60d|120d] [--dry-run] [--json] [--min-sample N] [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.alpha_quality_store import get_alpha_quality_store
from src.services.alpha_review_service import build_alpha_review
from src.services.alpha_review_store import get_alpha_review_store
from src.services.decision_journal_store import get_decision_journal_store
from src.services.forward_outcome_backfill import get_forward_outcome_store
from src.services.no_edge_tracker import get_no_edge_tracker
from src.services.opportunity_intelligence_store import get_opportunity_intelligence_store
from src.services.rule_learning_loop import build_rules_from_agent_state, summarize_rules
from src.services.signal_attribution_store import get_signal_attribution_store


def _parse_window(raw: str) -> int:
    s = str(raw).lower().strip().rstrip("d")
    try:
        return int(s)
    except ValueError:
        return 20


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Alpha Review report")
    parser.add_argument("--window", default="20d", help="Lookback window: 20d, 60d, or 120d")
    parser.add_argument("--dry-run", action="store_true", help="Compute without persisting report")
    parser.add_argument("--write", action="store_true", help="Persist report (default when not dry-run)")
    parser.add_argument("--json", action="store_true", help="Emit JSON report to stdout")
    parser.add_argument("--min-sample", type=int, default=12, help="Minimum sample for evidence")
    args = parser.parse_args()

    window_days = _parse_window(args.window)
    persist = args.write or not args.dry_run

    aq_store = get_alpha_quality_store()
    snapshots = aq_store.load_snapshots(limit=window_days * 2)
    latest = snapshots[-1] if snapshots else {}

    outcome_store = get_forward_outcome_store()
    oi_store = get_opportunity_intelligence_store()
    attribution_store = get_signal_attribution_store()
    no_edge_tracker = get_no_edge_tracker()
    journal_store = get_decision_journal_store()

    forward_summary = outcome_store.summarize(window=window_days)
    oi_transitions = oi_store.load_transitions(limit=window_days * 4)
    no_edge_rows = (
        no_edge_tracker.load_all()[-window_days:]
        if hasattr(no_edge_tracker, "load_all")
        else []
    )
    rule_summary = summarize_rules(build_rules_from_agent_state({}))

    report = build_alpha_review(
        alpha_snapshots=snapshots,
        alpha_quality_report=latest,
        baselines=latest.get("baseline_comparison"),
        overfit={
            "overfit_risk": latest.get("overfit_risk", "medium"),
            "reason_codes": latest.get("overfit_reason_codes", []),
            "allow_green_ui": latest.get("allow_green_ui", False),
            "allow_validated_label": latest.get("allow_green_ui", False),
        },
        missed_opportunity=latest.get("missed_opportunity_summary") or latest.get("missed_opportunity_review"),
        no_edge_tracking={"quality_label": "", "samples": len(no_edge_rows)},
        attribution=attribution_store.summarize(),
        stage_transitions=oi_transitions,
        rule_summary=rule_summary,
        governor_qa=latest.get("governor_qa"),
        window_days=window_days,
        min_sample=args.min_sample,
        persist=persist,
        supersede_prior=persist,
        store=get_alpha_review_store(),
    )

    _ = journal_store.summary()
    _ = forward_summary

    if args.json:
        print(json.dumps(report, indent=2, default=str))
    else:
        print(
            f"Alpha Review — status={report.get('status')} "
            f"evidence={report.get('evidence_level')} "
            f"n={report.get('sample_size')}"
        )
        print(f"  Human review items: {report.get('human_review_count', 0)}")
        for action in (report.get("next_actions") or [])[:3]:
            print(f"  → {action}")
        if persist:
            print(f"  Report: {report.get('report_id')}")
        else:
            print("  (dry-run — not persisted)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
