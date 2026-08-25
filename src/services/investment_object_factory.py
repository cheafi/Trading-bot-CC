"""Build InvestmentObject instances from Today / Playbook rows (CC X Sprint 118+)."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.investment_object import (
    InvestmentObject,
    InvestmentStage,
    PortfolioImpactBlock,
    ProvenanceBlock,
)


def _parse_as_of(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _provenance_from_row(row: Dict[str, Any]) -> ProvenanceBlock:
    trust = row.get("trust") if isinstance(row.get("trust"), dict) else {}
    prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    mode = str(
        prov.get("mode")
        or trust.get("freshness")
        or row.get("data_mode")
        or "LIVE"
    ).upper()
    if mode in ("DEGRADED", "STALE"):
        mode = "DEGRADED"
    return ProvenanceBlock(
        source=str(prov.get("source") or row.get("source") or "playbook_row"),
        as_of=_parse_as_of(prov.get("as_of") or row.get("as_of") or trust.get("as_of")),
        mode=mode,
        lag_days=int(prov.get("lag_days") or row.get("lag_days") or 0),
        data_freshness_minutes=int(
            prov.get("data_freshness_minutes")
            or row.get("data_freshness_minutes")
            or -1
        ),
    )


def make_decision_id(ticker: str, *, row: Optional[Dict[str, Any]] = None) -> str:
    """Stable decision id for attribution chain."""
    base = f"{ticker.upper()}:{row.get('rank') if row else ''}:{row.get('as_of') if row else ''}"
    digest = hashlib.sha256(base.encode("utf-8")).hexdigest()[:12]
    return f"dec-{ticker.upper()}-{digest}"


def make_attribution_root_ref(decision_id: str) -> str:
    return f"attr-root-{decision_id}"


def investment_object_from_row(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
    regime_label: str = "",
    portfolio_fit: Optional[Dict[str, Any]] = None,
) -> InvestmentObject:
    """Map a playbook/today opportunity row to InvestmentObject (research-first)."""
    ticker = str(row.get("ticker") or "").upper()
    decision_id = str(row.get("decision_id") or make_decision_id(ticker, row=row))
    fit = portfolio_fit or {}
    stage = InvestmentStage.GATED if row.get("execution_ready") else InvestmentStage.IDEA
    if row.get("deploy_eligible"):
        stage = InvestmentStage.GATED

    portfolio_impact = PortfolioImpactBlock(
        fit_score=int(fit.get("fit_score") or row.get("portfolio_fit_score") or 50),
        sector_overlap_pct=float(
            fit.get("sector_overlap_pct") or row.get("sector_overlap_pct") or 0.0
        ),
        correlation_note=str(fit.get("correlation_note") or row.get("correlation_note") or ""),
        replacement_delta=fit.get("replacement_delta") or row.get("replacement_delta"),
        what_becomes_worse=list(
            fit.get("what_becomes_worse") or row.get("what_becomes_worse") or []
        ),
        concentration_label=str(
            fit.get("concentration_label") or row.get("concentration_label") or "neutral"
        ),
    )

    return InvestmentObject(
        ticker=ticker,
        artifact_id=row.get("artifact_id"),
        authority="research_only",
        may_authorize_deploy=False,
        deploy_eligible=bool(row.get("deploy_eligible")),
        gate_reasons=list(row.get("gate_reasons") or []),
        provenance=_provenance_from_row(row),
        alpha_source=str(row.get("alpha_source") or row.get("source") or "scanner"),
        edge_hypothesis=str(row.get("why_now") or row.get("thesis") or ""),
        setup_type=str(row.get("setup_type") or row.get("ladder_bucket") or ""),
        strategy_style=str(row.get("strategy_style") or row.get("engine") or ""),
        expected_alpha_bps=row.get("expected_alpha_bps") or row.get("net_edge_bps"),
        ev_score=row.get("ev_score"),
        ev_components=dict(row.get("ev_components") or {}),
        confidence=int(row.get("confidence") or row.get("score") or 50),
        theme_tags=list(row.get("theme_tags") or ([row["theme"]] if row.get("theme") else [])),
        sector=str(row.get("sector") or ""),
        theme_cluster_id=row.get("theme_cluster_id"),
        portfolio_impact=portfolio_impact,
        entry_zone=str(row.get("entry_zone") or row.get("entry") or ""),
        stop=row.get("stop") or row.get("stop_loss"),
        target=row.get("target") or row.get("activation"),
        rr_ratio=row.get("risk_reward") or row.get("rr_ratio"),
        stage=stage,
        decision_id=decision_id,
        regime_at_signal=regime_label or str(row.get("regime_at_signal") or ""),
        journal_ref=row.get("journal_ref"),
    )


def attach_investment_objects(
    rows: List[Dict[str, Any]],
    *,
    tradeability: str = "",
    regime_label: str = "",
) -> List[Dict[str, Any]]:
    """Attach investment_object dict + attribution refs to ranked rows."""
    out: List[Dict[str, Any]] = []
    for row in rows:
        r = dict(row)
        io = investment_object_from_row(
            r, tradeability=tradeability, regime_label=regime_label
        )
        r["decision_id"] = io.decision_id
        r["attribution_root_ref"] = make_attribution_root_ref(io.decision_id or "")
        r["investment_object"] = io.model_dump(mode="json")
        out.append(r)
    return out
