#!/usr/bin/env python3
"""Performance smoke timings for CC release-critical paths."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

ROOT = Path(__file__).resolve().parents[1]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

THRESHOLDS_MS = {
    "today_build": 8000,
    "oi_eval": 3000,
    "alpha_qa": 3000,
    "alpha_review": 3000,
    "threshold_dry_run": 2000,
    "export_html": 500,
}


@dataclass
class SmokeResult:
    component: str
    duration_ms: int
    status: str
    threshold_ms: int
    detail: str = ""


def _timed(name: str, fn: Callable[[], Any], *, threshold_ms: int, blocks_release: bool) -> SmokeResult:
    t0 = time.perf_counter()
    detail = ""
    try:
        fn()
        status = "ok"
    except Exception as exc:
        detail = str(exc)[:200]
        status = "error"
    elapsed = int((time.perf_counter() - t0) * 1000)
    if status == "ok" and elapsed > threshold_ms:
        status = "slow"
    if status == "error" and blocks_release:
        status = "fail"
    elif status == "slow" and not blocks_release:
        status = "slow_optional"
    return SmokeResult(name, elapsed, status, threshold_ms, detail)


def run_smoke() -> List[SmokeResult]:
    results: List[SmokeResult] = []

    def today_build():
        from src.services.system_truth import resolve_system_truth
        from src.services.opportunity_quality_engine import build_decision_quality_dashboard

        truth = resolve_system_truth(
            {"market_regime": {"tradeability": "WAIT"}, "trust": {"stale": False}},
            cc_header={"data_tier": "FRESH"},
            ops_console={"engine_running": True},
        )
        build_decision_quality_dashboard(truth=truth, candidates=[{"ticker": "SPY", "score": 6.0}])

    results.append(_timed("today_build", today_build, threshold_ms=THRESHOLDS_MS["today_build"], blocks_release=True))

    def oi_eval():
        from src.services.opportunity_quality_engine import evaluate_opportunity_quality

        evaluate_opportunity_quality({"ticker": "AAPL", "score": 7.0, "sample_size": 2}, surface="discovery")

    results.append(_timed("oi_eval", oi_eval, threshold_ms=THRESHOLDS_MS["oi_eval"], blocks_release=False))

    def alpha_qa():
        from src.services.alpha_quality_evaluator import evaluate_alpha_quality

        evaluate_alpha_quality(
            forward_outcomes=[],
            playbook_rows=[],
        )

    results.append(_timed("alpha_qa", alpha_qa, threshold_ms=THRESHOLDS_MS["alpha_qa"], blocks_release=False))

    def alpha_review():
        from src.services.alpha_review_service import build_alpha_review

        build_alpha_review(
            alpha_quality_report={"status": "learning", "sample_size": 0, "overfit_risk": "medium"},
            persist=False,
        )

    results.append(_timed("alpha_review", alpha_review, threshold_ms=THRESHOLDS_MS["alpha_review"], blocks_release=False))

    def threshold_dry():
        from src.services.threshold_proposal_service import threshold_governance_summary_for_dashboard

        threshold_governance_summary_for_dashboard()

    results.append(
        _timed("threshold_dry_run", threshold_dry, threshold_ms=THRESHOLDS_MS["threshold_dry_run"], blocks_release=False)
    )

    def export_html():
        helpers = (ROOT / "src/api/static/cc-helpers.js").read_text(encoding="utf-8")
        assert "buildExportReviewHtml" in helpers
        assert "buildExportAllSurfacesPage" in helpers

    results.append(_timed("export_html", export_html, threshold_ms=THRESHOLDS_MS["export_html"], blocks_release=False))

    return results


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="CC performance smoke check")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    results = run_smoke()
    fails = [r for r in results if r.status in ("fail", "error") and r.component == "today_build"]
    slow_block = [r for r in results if r.component == "today_build" and r.duration_ms > r.threshold_ms]

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print("Performance smoke")
        for r in results:
            print(f"  {r.component:20} {r.duration_ms:5}ms  {r.status:14}  (threshold {r.threshold_ms}ms)")
            if r.detail:
                print(f"    {r.detail}")

    if fails or slow_block:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
