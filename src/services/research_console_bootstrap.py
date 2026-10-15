"""One-shot bootstrap for Strategy Lab / Research Console."""

from __future__ import annotations

import copy
import time
from typing import Any, Dict, Optional

from src.services.alpha_zoo_cache import cached_zoo_fresh, load_cached_zoo
from src.services.correlation_regime_timeline import build_correlation_regime_timeline
from src.services.research_store import list_memory
from src.services.research_task_catalog import catalog_payload
from src.services.research_safety import sanitize_research_payload

_CACHE: Optional[Dict[str, Any]] = None
_CACHE_TS: float = 0.0
_CACHE_TTL = 300.0  # 5 min — fast Strategy Lab tab switches


async def bootstrap_research_console(request, *, force_refresh: bool = False) -> Dict[str, Any]:
    global _CACHE, _CACHE_TS
    now = time.time()
    if not force_refresh and _CACHE and (now - _CACHE_TS) < _CACHE_TTL:
        out = copy.deepcopy(_CACHE)
        out["cached"] = True
        out["cache_age_sec"] = round(now - _CACHE_TS, 1)
        return out
    mds = request.app.state.market_data
    regime: Dict[str, Any] = {}
    try:
        from src.services.regime_service import RegimeService

        regime = RegimeService.get() or {}
    except Exception:
        pass

    corr = await build_correlation_regime_timeline(
        mds,
        ["SPY", "QQQ", "TLT", "IWM", "GLD"],
        period="3mo",
        window=30,
        step=10,
    )
    current_corr = (corr.get("current") or {}) if corr.get("ok") else {}

    ss: Dict[str, Any] = {}
    try:
        from src.services.cc_state import attach_system_state

        payload: Dict[str, Any] = {}
        attach_system_state(payload)
        ss = payload.get("system_state") or {}
    except Exception:
        pass

    memory = list_memory(limit=8, item_type="vibe_session")
    zoo_row = load_cached_zoo()
    alpha_zoo_cache: Dict[str, Any] = {
        "available": bool(zoo_row and zoo_row.get("ok")),
        "fresh": cached_zoo_fresh() if zoo_row else False,
        "computed_count": (zoo_row or {}).get("computed_count"),
        "zoo_total": (zoo_row or {}).get("zoo_total"),
        "cached_at": (zoo_row or {}).get("cached_at"),
        "summary": (zoo_row or {}).get("summary"),
        "top_alive": (zoo_row or {}).get("top_alive") or [],
        "canonical_pack": (zoo_row or {}).get("canonical_pack"),
    }
    payload = sanitize_research_payload(
        {
            "ok": True,
            "cached": False,
            "authority": "research_only",
            "execution_permission": False,
            "workflow": [
                {"step": 1, "id": "question", "label": "Frame question", "act": "Know"},
                {"step": 2, "id": "evidence", "label": "Data + documents", "act": "Believe"},
                {"step": 3, "id": "teams", "label": "Analyst teams", "act": "Doubt"},
                {"step": 4, "id": "backtest", "label": "Run card + benchmark", "act": "Believe"},
                {"step": 5, "id": "export", "label": "Artifacts", "act": "Know"},
                {"step": 6, "id": "playbook", "label": "Playbook gate", "act": "Act"},
            ],
            "gates": {
                "tradeability": ss.get("tradeability") or regime.get("tradeability") or "UNKNOWN",
                "deploy_open": bool(ss.get("deploy_open")),
                "data_freshness": ss.get("data_freshness") or "UNKNOWN",
            },
            "regime": {
                "label": regime.get("label") or regime.get("regime_label") or "UNKNOWN",
                "should_trade": regime.get("should_trade"),
                "stale": regime.get("stale"),
            },
            "correlation_surface": {
                "regime": current_corr.get("regime"),
                "edge_density": current_corr.get("edge_density"),
                "as_of": current_corr.get("as_of"),
                "descriptive_only": True,
            },
            "recent_sessions": [
                {
                    "id": m.get("id"),
                    "prompt": (m.get("prompt") or "")[:120],
                    "consensus": m.get("consensus"),
                }
                for m in memory
            ],
            "task_catalog": catalog_payload().get("tasks") or [],
            "alpha_zoo_cache": alpha_zoo_cache,
        }
    )
    _CACHE = copy.deepcopy(payload)
    _CACHE_TS = now
    return payload
