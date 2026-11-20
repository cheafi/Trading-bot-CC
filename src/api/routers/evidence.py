"""Evidence Router — read-only walk-forward evidence artifacts.

Endpoints:
  GET /api/evidence/walk-forward              — registered rules + artifact status
  GET /api/evidence/walk-forward/{strategy_id} — latest fresh artifact

Artifacts are produced offline by ``scripts/compute_walk_forward.py``; nothing
here fetches data, runs a backtest, or touches a broker.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from src.api.deps import sanitize_for_json, verify_api_key
from src.engines.walk_forward import RULES
from src.services import walk_forward_service

router = APIRouter(prefix="/api/evidence", tags=["evidence"])


@router.get("/walk-forward")
async def list_walk_forward(_=Depends(verify_api_key)):
    out = []
    for sid, rule in RULES.items():
        art = walk_forward_service.load(sid)
        out.append(
            {
                "strategy_id": sid,
                "rule": rule.description,
                "available": art is not None,
                "grade": (art or {}).get("evidence", {}).get("grade", "NO_BACKTEST"),
                "as_of": (art or {}).get("as_of"),
            }
        )
    return {"strategies": out}


@router.get("/walk-forward/{strategy_id}")
async def get_walk_forward(strategy_id: str, _=Depends(verify_api_key)):
    if strategy_id not in RULES:
        raise HTTPException(404, "unknown strategy_id")
    art = walk_forward_service.load(strategy_id)
    if art is None:
        return {
            "strategy_id": strategy_id,
            "available": False,
            "evidence": {"grade": "NO_BACKTEST", "reason_codes": ["NO_FRESH_ARTIFACT"]},
        }
    return sanitize_for_json({**art, "available": True})
