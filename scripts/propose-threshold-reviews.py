#!/usr/bin/env python3
"""
Propose threshold reviews from Alpha Review / QA signals.

Usage:
  python scripts/propose-threshold-reviews.py [--window 60d] [--dry-run] [--write] [--json]
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
from src.services.threshold_proposal_service import build_threshold_proposals


def _parse_window(raw: str) -> int:
    s = str(raw).lower().strip().rstrip("d")
    try:
        return int(s)
    except ValueError:
        return 60


def main() -> int:
    parser = argparse.ArgumentParser(description="Propose threshold reviews from Alpha Review")
    parser.add_argument("--window", default="60d", help="Lookback window: 20d, 60d, or 120d")
    parser.add_argument("--dry-run", action="store_true", help="Compute without persisting proposals")
    parser.add_argument("--write", action="store_true", help="Persist proposals")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    args = parser.parse_args()

    window_days = _parse_window(args.window)
    persist = args.write or not args.dry_run

    aq_store = get_alpha_quality_store()
    snapshots = aq_store.load_snapshots(limit=window_days * 2)
    latest = snapshots[-1] if snapshots else {}

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
        missed_opportunity=latest.get("missed_opportunity_review"),
        no_edge_tracking={"quality_label": "", "samples": 0},
        attribution={},
        stage_transitions=[],
        rule_summary={},
        governor_qa=latest.get("governor_qa"),
        window_days=window_days,
        persist=False,
        store=get_alpha_review_store(),
    )

    batch = build_threshold_proposals(
        alpha_review=report,
        alpha_quality=latest,
        governor_qa=latest.get("governor_qa"),
        persist=persist,
    )

    if args.json:
        print(json.dumps(batch, indent=2, default=str))
    else:
        print(f"Threshold proposals — count={batch.get('count', 0)}")
        for p in (batch.get("proposals") or [])[:5]:
            print(f"  → {p.get('threshold_key')} · {p.get('proposal_type')}: {p.get('rationale', '')[:60]}")
        if persist:
            print("  (persisted)")
        else:
            print("  (dry-run — not persisted)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
