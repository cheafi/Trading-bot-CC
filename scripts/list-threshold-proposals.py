#!/usr/bin/env python3
"""
List threshold governance proposals.

Usage:
  python scripts/list-threshold-proposals.py [--status open|shadow|all] [--json]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.services.threshold_governance_store import get_threshold_governance_store
from src.services.threshold_registry import list_thresholds, registry_summary


def main() -> int:
    parser = argparse.ArgumentParser(description="List threshold governance proposals")
    parser.add_argument("--status", default="all", choices=["open", "shadow", "all"])
    parser.add_argument("--json", action="store_true", help="Emit JSON to stdout")
    args = parser.parse_args()

    store = get_threshold_governance_store()
    if args.status == "open":
        proposals = store.open_proposals()
    elif args.status == "shadow":
        proposals = store.shadow_proposals()
    else:
        proposals = store.load_proposals()

    payload = {
        "registry": registry_summary(),
        "thresholds": list_thresholds(),
        "proposals": proposals,
        "summary": store.summary(),
        "authority_effect": "none",
        "may_authorize_deploy": False,
        "can_auto_loosen": False,
    }

    if args.json:
        print(json.dumps(payload, indent=2, default=str))
    else:
        print(f"Threshold registry — {payload['registry'].get('total_thresholds', 0)} definitions")
        print(f"Proposals ({args.status}): {len(proposals)}")
        for p in proposals[:10]:
            print(
                f"  {p.get('proposal_id')} · {p.get('threshold_key')} · "
                f"{p.get('proposal_type')} · {p.get('status')}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
