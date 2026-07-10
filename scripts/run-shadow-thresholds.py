#!/usr/bin/env python3
"""
Run shadow threshold simulations and forward shadow tracking.

Usage:
  python scripts/run-shadow-thresholds.py [--json] [--write]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.forward_outcome_backfill import get_forward_outcome_store
from src.services.forward_shadow_thresholds import batch_forward_shadow
from src.services.shadow_threshold_simulator import batch_simulate_proposals
from src.services.threshold_governance_store import get_threshold_governance_store


def main() -> int:
    parser = argparse.ArgumentParser(description="Run shadow threshold simulations")
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    parser.add_argument("--write", action="store_true", help="Persist shadow runs")
    args = parser.parse_args()

    store = get_threshold_governance_store()
    proposals = store.shadow_proposals() or store.open_proposals()
    outcome_store = get_forward_outcome_store()
    forward_rows = outcome_store.load_all()[-200:]
    historical_rows = forward_rows

    sim = batch_simulate_proposals(
        proposals,
        historical_rows=historical_rows,
        forward_outcomes=forward_rows,
    )
    shadow = batch_forward_shadow(
        proposals,
        forward_rows=forward_rows,
        persist=args.write,
    )

    result = {
        "historical_simulation": sim,
        "forward_shadow": shadow,
        "proposal_count": len(proposals),
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "no_live_changes": True,
    }

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"Shadow thresholds — proposals={len(proposals)}")
        print(f"  Historical sims: {sim.get('count', 0)} (approve={sim.get('approve_shadow_count', 0)})")
        print(f"  Forward shadow runs: {shadow.get('count', 0)}")
        if args.write:
            print("  (shadow runs persisted)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
