"""Today payload builder — side context + row enrichment helpers."""

from __future__ import annotations

import sys
from types import ModuleType

if "fastapi" not in sys.modules:
    _fastapi = ModuleType("fastapi")

    class _Request:  # noqa: D106
        pass

    _fastapi.Request = _Request
    sys.modules["fastapi"] = _fastapi

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.services.today_payload_builder import (
    TodaySideContext,
    apply_today_opportunity_quality,
    enrich_today_rows_post_regime,
    gather_today_side_context,
    load_portfolio_holdings_snapshot,
)


def test_load_portfolio_holdings_snapshot_returns_tuple():
    holdings, count, local_only = load_portfolio_holdings_snapshot()
    assert isinstance(holdings, list)
    assert count == len(holdings)
    assert isinstance(local_only, bool)


def test_enrich_today_rows_post_regime_passthrough_without_regime():
    top5 = [{"ticker": "A", "score": 8.0}]
    near = [{"ticker": "B", "score": 6.5}]
    all_opps = [{"ticker": "A", "score": 8.0}]
    with patch(
        "src.services.ranked_board_pipeline.enrich_ranked_board_row_groups",
        return_value={"top5": top5, "near_miss": near, "all_opps": all_opps},
    ):
        t5, nm, opps = enrich_today_rows_post_regime(
            top5=top5,
            near_miss=near,
            all_opps_for_action=all_opps,
            index_regime_summary={"posture": "neutral", "degraded": False},
            tradeability="WAIT",
            trend_label="SIDEWAYS",
            breadth_pct=50.0,
            event_risks=[],
        )
    assert t5[0]["ticker"] == "A"
    assert nm[0]["ticker"] == "B"
    assert opps[0]["ticker"] == "A"


def test_apply_today_opportunity_quality_delegates():
    rows = [{"ticker": "Z", "score": 7.5, "action": "WATCH"}]
    enriched = {"top5": [{"ticker": "Z", "quality_score": 0.5}], "near_miss": rows}
    with patch(
        "src.services.ranked_board_pipeline.enrich_ranked_board_row_groups",
        return_value=enriched,
    ):
        top5, near = apply_today_opportunity_quality(
            top5=rows,
            near_miss=[dict(rows[0])],
            tradeability="WAIT",
            event_risks=["VIX elevated"],
        )
    assert top5[0]["quality_score"] == 0.5
    assert near[0]["ticker"] == "Z"


def test_gather_today_side_context_parallel():
    async def _run():
        request = SimpleNamespace()
        with patch(
            "src.services.today_insights.load_equity_dd_pct_for_hints",
            new=AsyncMock(return_value=1.5),
        ), patch(
            "src.services.today_payload_builder.load_portfolio_holdings_snapshot",
            return_value=([{"ticker": "SPY"}], 1, True),
        ):
            ctx = await gather_today_side_context(
                request,
                used_brief_fallback=False,
                scanner_degraded=False,
            )
            assert isinstance(ctx, TodaySideContext)
            assert ctx.equity_dd_pct == 1.5
            assert ctx.pf_count == 1

    asyncio.run(_run())


def test_build_today_payload_exported():
    from pathlib import Path

    src = (
        Path(__file__).resolve().parents[1]
        / "src/services/today_payload_builder.py"
    ).read_text(encoding="utf-8")
    assert "async def build_today_payload" in src
    assert "return payload, not scanner_degraded" in src
