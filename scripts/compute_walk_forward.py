"""Compute walk-forward evidence for a registered rule and save the artifact.

Usage: python scripts/compute_walk_forward.py [strategy_id]

Downloads 5y daily bars for the brief universe plus SPY. Read-only: no orders.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.engines.walk_forward import RULES  # noqa: E402
from src.services import walk_forward_service  # noqa: E402


def main() -> int:
    sid = sys.argv[1] if len(sys.argv) > 1 else "brief_rs_leader_v1"
    if sid not in RULES:
        print(f"unknown strategy_id; choose one of: {', '.join(sorted(RULES))}")
        return 2
    from data.generate_brief import UNIVERSE

    report = asyncio.run(walk_forward_service.compute(sid, UNIVERSE))
    path = walk_forward_service.save(report)
    summary = {
        k: report.get(k)
        for k in (
            "strategy_id",
            "as_of",
            "trades",
            "in_sample_vs_oos",
            "fold_consistency",
            "cost_sensitivity",
            "missing_tickers",
        )
    }
    summary["evidence"] = {
        k: report["evidence"].get(k) for k in ("grade", "reason_codes", "sample_size")
    }
    summary["windows"] = report.get("windows")
    print(json.dumps(summary, indent=2, default=str))
    print(f"saved {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
