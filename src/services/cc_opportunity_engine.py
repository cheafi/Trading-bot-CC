"""
Opportunity quality engine — ranking and monitor workflow support.

May demote sort order and enrich monitor copy; never overrides board gate.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.cost_adjusted_edge import compute_net_edge, infer_burdens_from_row

AUTHORITY_RESEARCH = "research_only"
AUTHORITY_CONFIRMATION = "confirmation_only"


def _setup_freshness(row: Dict[str, Any]) -> Dict[str, Any]:
    age = row.get("signal_age_days") or row.get("age_days")
    if age is None:
        decay = row.get("strategy_decay") or ""
        if "stale" in str(decay).lower():
            return {"tier": "stale", "label": "Setup stale — recheck before dossier drill"}
        return {"tier": "unknown", "label": "Freshness unknown — confirm-only"}
    days = int(age)
    if days <= 2:
        tier = "fresh"
        label = f"Fresh setup ({days}d) — ranking support"
    elif days <= 5:
        tier = "aging"
        label = f"Aging setup ({days}d) — monitor decay"
    else:
        tier = "stale"
        label = f"Stale setup ({days}d) — demote in sort"
    return {"tier": tier, "days": days, "label": label}


def _follow_through_quality(row: Dict[str, Any]) -> Dict[str, Any]:
    vol_ok = bool(row.get("volume_confirm") or row.get("volume_ok"))
    extended = bool(row.get("extended") or row.get("timing_extended"))
    if extended and not vol_ok:
        return {
            "quality": "weak",
            "label": "Weak follow-through — extended without volume",
            "downgrade_only": True,
        }
    if vol_ok:
        return {"quality": "ok", "label": "Follow-through OK — confirm-only"}
    return {"quality": "unknown", "label": "Follow-through unconfirmed"}


def _false_breakout_risk(row: Dict[str, Any]) -> Dict[str, Any]:
    extended = bool(row.get("extended") or row.get("timing_extended"))
    rr = float(row.get("risk_reward") or row.get("rr") or 0)
    if extended and rr < 2.0:
        return {
            "risk": "elevated",
            "label": "False-breakout risk — chase extended with thin RR",
            "downgrade_only": True,
        }
    if extended:
        return {"risk": "watch", "label": "Extended entry — monitor only"}
    return {"risk": "low", "label": "Breakout risk within band"}


def _event_blocker(
    ticker: str,
    event_risks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    risks = list(event_risks or [])
    sym = ticker.upper()
    hits = [r for r in risks if sym in r.upper()]
    if hits:
        return {
            "blocked": True,
            "label": f"Event blocker: {hits[0][:60]} — downgrade-only",
            "downgrade_only": True,
        }
    return {"blocked": False, "label": "No proximate event blocker"}


def _opportunity_decay_timer(row: Dict[str, Any]) -> Dict[str, Any]:
    fresh = _setup_freshness(row)
    days = fresh.get("days")
    if days is None:
        return {"hours_remaining": None, "label": "Decay timer unknown"}
    remaining = max(0, 7 - int(days))
    return {
        "hours_remaining": remaining * 24,
        "label": f"~{remaining}d monitor window before stale demotion",
    }


def evaluate_opportunity_quality(
    row: Dict[str, Any],
    *,
    tradeability: str = "",
    event_risks: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Per-row quality bundle for Playbook / Discovery / Dossier."""
    ticker = str(row.get("ticker") or "").upper()
    raw = row.get("raw_score") or row.get("score") or 0
    burdens = infer_burdens_from_row(row)
    edge = compute_net_edge(
        float(raw),
        turnover_burden=burdens["turnover_burden"],
        spread_burden=burdens["spread_burden"],
        action=row.get("action"),
        extended=bool(row.get("extended") or row.get("timing_extended")),
        partial_data=bool(row.get("partial")),
    )
    freshness = _setup_freshness(row)
    follow = _follow_through_quality(row)
    false_bo = _false_breakout_risk(row)
    event_blk = _event_blocker(ticker, event_risks)
    decay = _opportunity_decay_timer(row)

    quality_score = float(edge.get("net_deploy_score") or 0)
    if freshness.get("tier") == "stale":
        quality_score -= 1.0
    if false_bo.get("risk") == "elevated":
        quality_score -= 1.5
    if event_blk.get("blocked"):
        quality_score -= 2.0
    if follow.get("quality") == "weak":
        quality_score -= 1.0
    quality_score = round(max(0.0, min(10.0, quality_score)), 1)

    flags: List[str] = []
    if edge.get("weak_edge_after_cost"):
        flags.append("cost_drag")
    if false_bo.get("risk") == "elevated":
        flags.append("false_breakout")
    if event_blk.get("blocked"):
        flags.append("event_blocker")
    if freshness.get("tier") == "stale":
        flags.append("stale_setup")

    return {
        "ticker": ticker,
        "quality_score": quality_score,
        "edge_after_cost": edge,
        "spread_slippage_burden": {
            "turnover": burdens["turnover_burden"],
            "spread": burdens["spread_burden"],
            "label": f"Spread/turnover burden — net {edge.get('net_deploy_score')}",
        },
        "freshness": freshness,
        "decay_timer": decay,
        "follow_through": follow,
        "false_breakout": false_bo,
        "event_blocker": event_blk,
        "quality_flags": flags,
        "authority": AUTHORITY_CONFIRMATION if flags else AUTHORITY_RESEARCH,
        "may_authorize_deploy": False,
        "may_override_wait": False,
        "monitor_only": True,
    }


def enrich_opportunity_quality_rows(
    rows: List[Dict[str, Any]],
    *,
    tradeability: str = "",
    event_risks: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Attach quality bundle; re-sort hint by quality_score (display only)."""
    enriched = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        q = evaluate_opportunity_quality(
            row, tradeability=tradeability, event_risks=event_risks
        )
        enriched.append({**row, "opportunity_quality": q, "quality_score": q["quality_score"]})
    return enriched


def build_opportunity_pipeline_summary(
    *,
    discovery_count: int = 0,
    near_miss_count: int = 0,
    playbook_count: int = 0,
    deployable_count: int = 0,
) -> Dict[str, Any]:
    """Idea pipeline tracker — discovery → monitor → near-miss → playbook."""
    return {
        "stages": {
            "discovery": discovery_count,
            "near_miss": near_miss_count,
            "playbook": playbook_count,
            "deploy_ready": deployable_count,
        },
        "label": (
            f"Pipeline: {discovery_count} scan · {near_miss_count} near-miss · "
            f"{playbook_count} board · {deployable_count} gate-ready"
        ),
        "monitor_only": True,
        "may_authorize_deploy": False,
    }
