"""
Options availability — research-only liquidity / IV signals for watch candidates.

Never implies deploy authority or "buy now" when deploy is blocked.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def _grade_from_liquidity(liquidity_score: float) -> str:
    if liquidity_score >= 0.65:
        return "liquid"
    if liquidity_score >= 0.35:
        return "thin"
    return "illiquid"


def _strategy_hint(
    *,
    iv_rank: Optional[float],
    action: str,
    deploy_blocked: bool,
) -> str:
    act = str(action or "").upper()
    iv = float(iv_rank) if iv_rank is not None else None
    if iv is not None and iv >= 55:
        hint = "covered_call"
    elif iv is not None and iv <= 25 and act in ("WATCH", "PILOT"):
        hint = "protective_put"
    elif iv is not None and iv >= 70:
        hint = "avoid"
    else:
        hint = "research_only"
    if deploy_blocked:
        return hint
    return hint


def assess_options_availability(
    ticker: str,
    row: Optional[Dict[str, Any]] = None,
    *,
    deploy_blocked: bool = True,
) -> Dict[str, Any]:
    """
    Research signal for a single ticker — options chain liquidity + IV context.

    Uses row metadata when present; otherwise returns honest unavailable stub.
    """
    sym = str(ticker or "").upper().strip()
    r = row or {}
    meta = r.get("options_meta") or r.get("options") or {}
    liq = meta.get("liquidity_score")
    if liq is None:
        liq = r.get("options_liquidity_score")
    if liq is None:
        oi = int(meta.get("open_interest") or r.get("options_oi") or 0)
        vol = int(meta.get("volume") or r.get("options_volume") or 0)
        liq = min(1.0, (oi / 5000.0) * 0.5 + (vol / 2000.0) * 0.5) if (oi or vol) else None
    iv_rank = meta.get("iv_rank")
    if iv_rank is None:
        iv_rank = r.get("iv_rank")
    if iv_rank is None and meta.get("iv") is not None:
        iv_rank = min(100.0, max(0.0, float(meta.get("iv") or 0) * 100.0))

    if liq is None:
        return {
            "ticker": sym,
            "options_liquid": "unknown",
            "iv_rank": iv_rank,
            "strategy_hint": "research_only",
            "display": "Options: data unavailable",
            "display_zh": "期權：資料不可用",
            "research_only": True,
            "deploy_blocked": deploy_blocked,
            "options_lab_url": f"/options-lab?ticker={sym}" if sym else "/options-lab",
        }

    liquid = _grade_from_liquidity(float(liq))
    hint = _strategy_hint(iv_rank=iv_rank, action=str(r.get("action") or ""), deploy_blocked=deploy_blocked)
    iv_pct = f"{int(round(float(iv_rank)))}%" if iv_rank is not None else "—"
    liquid_zh = {"liquid": "流動", "thin": "偏薄", "illiquid": "不流動"}.get(liquid, liquid)
    copy_en = f"Options: {liquid} · IV {iv_pct}"
    copy_zh = f"期權：{liquid_zh} · IV {iv_pct}"
    if deploy_blocked:
        copy_en += " · research only"
        copy_zh += " · 僅研究"

    return {
        "ticker": sym,
        "options_liquid": liquid if liquid != "illiquid" else "no",
        "iv_rank": round(float(iv_rank), 1) if iv_rank is not None else None,
        "strategy_hint": hint,
        "display": copy_en,
        "display_zh": copy_zh,
        "research_only": deploy_blocked,
        "deploy_blocked": deploy_blocked,
        "options_lab_url": f"/options-lab?ticker={sym}" if sym else "/options-lab",
    }


def batch_options_availability(
    candidates: List[Dict[str, Any]],
    *,
    deploy_blocked: bool = True,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Attach options research signals to top watch candidates."""
    out: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in candidates or []:
        sym = str(row.get("ticker") or "").upper().strip()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        out.append(assess_options_availability(sym, row, deploy_blocked=deploy_blocked))
        if len(out) >= limit:
            break
    return out
