"""
Leader / Holdings Tracking API — institutional research layer.

All responses distinguish verified vs inferred sources.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.services.leader_tracking_service import (
    ensure_seeded,
    get_alerts,
    get_consensus_list,
    get_consensus_ticker,
    get_dashboard_cards,
    get_flow_ticker,
    get_flow_tracked,
    get_leader_detail,
    list_baskets_enriched,
    list_leaders_enriched,
)
from src.services import leader_persistence as store

logger = logging.getLogger(__name__)

router = APIRouter(tags=["leaders"])


@router.get("/api/leaders")
async def api_list_leaders(
    category: Optional[str] = Query(None, description="verified_filer|public_figure|fund_manager|influencer|etf"),
    source_quality: Optional[str] = Query(None, description="verified|delayed|derived|inferred|speculative"),
    search: Optional[str] = Query(None),
):
    """Leader hub — list tracked entities with metrics."""
    return {
        "leaders": list_leaders_enriched(
            category=category,
            source_quality=source_quality,
            search=search,
        ),
        "categories": [
            {"id": "verified_filer", "label": "Verified Filers"},
            {"id": "public_figure", "label": "Public Figures / Political"},
            {"id": "fund_manager", "label": "Fund Managers / 13F"},
            {"id": "influencer", "label": "Influencers / Idea Leaders"},
            {"id": "etf", "label": "ETF / Public Portfolios"},
        ],
    }


@router.get("/api/leaders/dashboard")
async def api_leaders_dashboard():
    """Home cards: top moves, verified updates, consensus, flow-confirmed."""
    return get_dashboard_cards()


@router.get("/api/leaders/{leader_id}")
async def api_leader_detail(leader_id: str):
    """Leader profile + holdings + timeline + decision box."""
    detail = get_leader_detail(leader_id)
    if not detail:
        raise HTTPException(404, f"Leader not found: {leader_id}")
    return detail


@router.get("/api/leaders/{leader_id}/holdings")
async def api_leader_holdings(
    leader_id: str,
    action: Optional[str] = Query(None, description="new_buy|add|reduce|exit|unchanged"),
):
    detail = get_leader_detail(leader_id)
    if not detail:
        raise HTTPException(404, f"Leader not found: {leader_id}")
    holdings = detail["holdings"]
    if action:
        holdings = [h for h in holdings if h["action_type"] == action]
    return {"leader_id": leader_id, "holdings": holdings}


@router.get("/api/leaders/{leader_id}/timeline")
async def api_leader_timeline(leader_id: str):
    detail = get_leader_detail(leader_id)
    if not detail:
        raise HTTPException(404, f"Leader not found: {leader_id}")
    return {"leader_id": leader_id, "timeline": detail["timeline"]}


@router.get("/api/consensus")
async def api_consensus(
    verified_only: bool = Query(False),
    min_overlap: int = Query(2, ge=1),
    sector: Optional[str] = Query(None),
    theme: Optional[str] = Query(None),
):
    """Cross-leader overlap and accumulation scores."""
    data = get_consensus_list(verified_only=verified_only, min_overlap=min_overlap)
    if sector or theme:
        filtered = []
        for item in data["items"]:
            conn = store._get_db()
            try:
                rows = conn.execute(
                    """
                    SELECT sector, theme FROM leader_holdings
                    WHERE ticker = ? LIMIT 1
                    """,
                    (item["ticker"],),
                ).fetchone()
            finally:
                conn.close()
            if rows:
                if sector and rows["sector"] != sector:
                    continue
                if theme and theme not in (rows["theme"] or ""):
                    continue
            filtered.append(item)
        data["items"] = filtered
    return data


@router.get("/api/consensus/ticker/{ticker}")
async def api_consensus_ticker(ticker: str):
    return get_consensus_ticker(ticker)


@router.get("/api/flow/tracked")
async def api_flow_tracked():
    return get_flow_tracked()


@router.get("/api/flow/{ticker}")
async def api_flow_ticker(ticker: str):
    return get_flow_ticker(ticker)


@router.get("/api/baskets")
async def api_baskets():
    return {"baskets": list_baskets_enriched()}


@router.get("/api/baskets/{basket_id}")
async def api_basket_detail(basket_id: str):
    b = store.get_basket(basket_id)
    if not b:
        raise HTTPException(404, f"Basket not found: {basket_id}")
    b["performance"] = {
        "note": "Connect shadow basket backtest for live performance",
    }
    return b


@router.get("/api/alerts/leaders")
async def api_leader_alerts(
    unseen_only: bool = Query(True),
):
    alerts = get_alerts()
    if unseen_only:
        alerts = [a for a in alerts if not a.get("seen")]
    return {"alerts": alerts}


@router.post("/api/leaders/admin/reseed")
async def api_reseed_demo(force: bool = Query(True)):
    """Re-seed demo data (dev/admin)."""
    ensure_seeded(force=force)
    return {"ok": True, "message": "Leader tracking demo data reseeded"}
