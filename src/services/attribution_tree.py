"""Alpha Attribution Tree — PnL → Market Data traceability (Sprint 120)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def resolve_attribution_chain(
    *,
    position_id: str,
    ticker: str,
    decision_id: Optional[str] = None,
    alpha_id: Optional[str] = None,
    artifact_id: Optional[str] = None,
    market_data_ref: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Resolve 7-level chain: PnL → Position → Decision → Research → Knowledge → Evidence → Market Data.
    MVP stub returns structured refs for audit export.
    """
    decision_id = decision_id or f"dec-{ticker.upper()}-unknown"
    alpha_id = alpha_id or f"alpha-{ticker.upper()}-unknown"
    artifact_id = artifact_id or f"artifact-{ticker.upper()}"
    market_data_ref = market_data_ref or f"md-{ticker.upper()}"

    chain: List[Dict[str, Any]] = [
        {"level": "pnl", "ref": f"pnl-{position_id}", "label": "Realized PnL"},
        {"level": "position", "ref": position_id, "label": ticker.upper()},
        {"level": "decision", "ref": decision_id, "label": "Decision journal"},
        {"level": "research", "ref": artifact_id, "label": "Alpha Factory artifact"},
        {"level": "knowledge", "ref": alpha_id, "label": "AlphaObject"},
        {
            "level": "evidence",
            "ref": f"evidence-{alpha_id}",
            "label": "Provenance envelope",
        },
        {"level": "market_data", "ref": market_data_ref, "label": "Market data source"},
    ]
    return {
        "position_id": position_id,
        "ticker": ticker.upper(),
        "attribution_root_ref": f"attr-root-{decision_id}",
        "chain": chain,
        "chain_depth": len(chain),
        "complete": all(c.get("ref") for c in chain),
        "authority": "research_only",
        "disclaimer": "Attribution chain for audit — does not grant deploy authority.",
    }


def enrich_board_row_attribution(row: Dict[str, Any]) -> Dict[str, Any]:
    """Attach attribution_root_ref + decision_id to a board row."""
    out = dict(row)
    ticker = str(out.get("ticker") or "").upper()
    if not out.get("decision_id"):
        from src.services.investment_object_factory import make_decision_id

        out["decision_id"] = make_decision_id(ticker, row=out)
    if not out.get("attribution_root_ref"):
        from src.services.investment_object_factory import make_attribution_root_ref

        out["attribution_root_ref"] = make_attribution_root_ref(out["decision_id"])
    return out
