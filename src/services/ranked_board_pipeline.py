"""Shared ranked-board enrichment: authority → cost rank → AI hints → opportunity quality."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

Row = Dict[str, Any]


def tradeability_from_funnel(
    should_trade: bool,
    execution_ready_count: int,
) -> str:
    """Honest tradeability label from funnel deploy count."""
    if not should_trade:
        return "NO_TRADE"
    if execution_ready_count >= 1:
        return "SELECTIVE"
    return "WAIT"


def scanner_degraded_from_scan(scanned: List[Any]) -> bool:
    return len(scanned) == 0


def enrich_ranked_board_rows(
    rows: List[Row],
    *,
    decision_authority: Optional[Dict[str, Any]] = None,
    index_regime: Optional[Dict[str, Any]] = None,
    tradeability: str = "WAIT",
    market_regime: Optional[Dict[str, Any]] = None,
    event_risks: Optional[List[str]] = None,
    authority_first: bool = True,
    include_opportunity_quality: bool = False,
    apply_authority: bool = True,
    apply_cost_rank: bool = True,
    apply_ai_hints: bool = True,
) -> List[Row]:
    """Single-pass row enrichment preserving today vs opportunities ordering."""
    if not rows:
        return rows

    from src.services.decision_truth_model import apply_authority_to_rows

    def _authority(data: List[Row]) -> List[Row]:
        if not apply_authority or not decision_authority:
            return data
        return apply_authority_to_rows(data, decision_authority)

    def _cost(data: List[Row]) -> List[Row]:
        if not apply_cost_rank or index_regime is None:
            return data
        from src.services.cost_adjusted_ranker import enrich_opportunity_rows

        return enrich_opportunity_rows(
            data,
            index_regime=index_regime,
            tradeability=tradeability,
        )

    def _ai(data: List[Row]) -> List[Row]:
        if not apply_ai_hints or market_regime is None:
            return data
        from src.services.ai_intelligence import attach_row_ai_hints

        return attach_row_ai_hints(
            data,
            market_regime=market_regime,
            index_regime=index_regime,
            event_risks=event_risks or [],
        )

    def _quality(data: List[Row]) -> List[Row]:
        if not include_opportunity_quality:
            return data
        from src.services.cc_opportunity_engine import enrich_opportunity_quality_rows

        return enrich_opportunity_quality_rows(
            data,
            tradeability=tradeability,
            event_risks=event_risks or [],
        )

    if authority_first:
        out = _authority(rows)
        out = _cost(out)
        out = _ai(out)
    else:
        out = _cost(rows)
        out = _ai(out)
        out = _authority(out)
    return _quality(out)


def enrich_ranked_board_row_groups(
    groups: Dict[str, List[Row]],
    *,
    quality_keys: Optional[Set[str]] = None,
    **kwargs: Any,
) -> Dict[str, List[Row]]:
    """Apply identical pipeline settings to multiple named row lists."""
    quality_keys = quality_keys or set()
    return {
        key: enrich_ranked_board_rows(
            rows,
            include_opportunity_quality=key in quality_keys,
            **kwargs,
        )
        for key, rows in groups.items()
    }


def enrich_playbook_ranked_board_groups(
    groups: Dict[str, List[Row]],
    **kwargs: Any,
) -> Dict[str, List[Row]]:
    """Playbook deploy board — authority-first ordering (Dashboard/Playbook surfaces)."""
    return enrich_ranked_board_row_groups(
        groups,
        authority_first=True,
        **kwargs,
    )
