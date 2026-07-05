"""Ranked board pipeline — shared enrichment contract."""

from __future__ import annotations

from src.services.ranked_board_pipeline import (
    enrich_ranked_board_row_groups,
    enrich_ranked_board_rows,
    scanner_degraded_from_scan,
    tradeability_from_funnel,
)


def test_tradeability_from_funnel():
    assert tradeability_from_funnel(False, 3) == "NO_TRADE"
    assert tradeability_from_funnel(True, 0) == "WAIT"
    assert tradeability_from_funnel(True, 2) == "SELECTIVE"


def test_scanner_degraded_from_scan():
    assert scanner_degraded_from_scan([]) is True
    assert scanner_degraded_from_scan([{"ticker": "AAPL"}]) is False


def test_enrich_ranked_board_rows_empty_passthrough():
    assert enrich_ranked_board_rows([]) == []


def test_enrich_ranked_board_row_groups_preserves_keys():
    rows = [{"ticker": "X", "score": 7.0}]
    out = enrich_ranked_board_row_groups(
        {"a": rows, "b": []},
        apply_authority=False,
        apply_cost_rank=False,
        apply_ai_hints=False,
    )
    assert set(out) == {"a", "b"}
    assert out["a"][0]["ticker"] == "X"
    assert out["b"] == []


def test_authority_first_flag_exists():
    """Pipeline exposes ordering knob for today vs opportunities paths."""
    import inspect
    from src.services import ranked_board_pipeline as mod

    sig = inspect.signature(mod.enrich_ranked_board_rows)
    assert "authority_first" in sig.parameters


def test_playbook_enrich_helper_authority_first():
    from src.services.ranked_board_pipeline import enrich_playbook_ranked_board_groups

    rows = [{"ticker": "AAPL", "score": 7.0}]
    out = enrich_playbook_ranked_board_groups(
        {"opportunities": rows},
        apply_authority=False,
        apply_cost_rank=False,
        apply_ai_hints=False,
    )
    assert out["opportunities"][0]["ticker"] == "AAPL"


def test_playbook_router_uses_shared_ranked_pipeline():
    from pathlib import Path

    src = (Path(__file__).resolve().parents[1] / "src/api/routers/playbook.py").read_text(
        encoding="utf-8"
    )
    assert "ranked_board_pipeline" in src
    assert "PLAYBOOK_RANKED_AUTHORITY_FIRST" in src
    assert "authority_first=PLAYBOOK_RANKED_AUTHORITY_FIRST" in src
    assert "enrich_opportunity_rows(" not in src
