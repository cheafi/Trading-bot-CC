"""Belief review — thesis + kill conditions (research_only, no deploy authority)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

_DATA_PATH = Path(__file__).resolve().parents[2] / "data" / "belief_review.json"
_EDITABLE_FIELDS = frozenset({"thesis", "kill_condition", "conviction", "status"})


def _load_store() -> Dict[str, Any]:
    if not _DATA_PATH.is_file():
        return {"items": {}}
    try:
        data = json.loads(_DATA_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("belief review store read failed: %s", exc)
        return {"items": {}}
    if not isinstance(data, dict):
        return {"items": {}}
    data.setdefault("items", {})
    return data


def _save_store(store: Dict[str, Any]) -> None:
    try:
        _DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        _DATA_PATH.write_text(json.dumps(store, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("belief review store write failed: %s", exc)
        raise


def build_belief_items(forward_outcomes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Merge forward-outcome tickers with persisted thesis/kill edits."""
    store = _load_store()
    saved: Dict[str, Any] = store.get("items") or {}
    seen: set[str] = set()
    items: List[Dict[str, Any]] = []
    for fo in forward_outcomes:
        ticker = str(fo.get("ticker") or "").upper()
        decision_id = str(fo.get("decision_id") or "").strip()
        if not ticker:
            continue
        item_id = decision_id or f"ticker:{ticker}"
        if item_id in seen:
            continue
        seen.add(item_id)
        persisted = saved.get(item_id) if isinstance(saved.get(item_id), dict) else {}
        items.append(
            {
                "id": item_id,
                "ticker": ticker,
                "decision_id": decision_id or None,
                "thesis": str(persisted.get("thesis") or ""),
                "kill_condition": str(persisted.get("kill_condition") or ""),
                "conviction": persisted.get("conviction"),
                "status": str(persisted.get("status") or "due_review"),
                "forward_horizon": fo.get("horizon"),
                "authority": "research_only",
            }
        )
    return items[:20]


def build_deploy_belief_flags(
    holdings: List[Dict[str, Any]],
    *,
    deploy_open: bool = False,
) -> Dict[str, Any]:
    """
    Flag held tickers with incomplete thesis/kill when deploy is open.

    Display-only amber strip — never blocks human deploy authority.
    """
    if not deploy_open:
        return {
            "active": False,
            "authority": "research_only",
            "incomplete_count": 0,
            "incomplete_tickers": [],
            "headline": "",
        }
    held = {
        str(h.get("ticker") or "").upper()
        for h in (holdings or [])
        if str(h.get("ticker") or "").strip()
    }
    if not held:
        return {
            "active": False,
            "authority": "research_only",
            "incomplete_count": 0,
            "incomplete_tickers": [],
            "headline": "",
        }

    store = _load_store()
    saved: Dict[str, Any] = store.get("items") or {}
    incomplete: List[Dict[str, Any]] = []
    for item_id, item in saved.items():
        if not isinstance(item, dict):
            continue
        ticker = str(item.get("ticker") or "").upper()
        if ticker not in held:
            for fo_ticker in held:
                if item_id == f"ticker:{fo_ticker}" or ticker == fo_ticker:
                    ticker = fo_ticker
                    break
            else:
                continue
        thesis = str(item.get("thesis") or "").strip()
        kill = str(item.get("kill_condition") or "").strip()
        if thesis and kill:
            continue
        incomplete.append(
            {
                "ticker": ticker,
                "item_id": item_id,
                "missing_thesis": not thesis,
                "missing_kill": not kill,
            }
        )

    for ticker in held:
        if any(x["ticker"] == ticker for x in incomplete):
            continue
        has_record = any(
            isinstance(v, dict)
            and (
                str(v.get("ticker") or "").upper() == ticker
                or item_id == f"ticker:{ticker}"
            )
            for item_id, v in saved.items()
        )
        if not has_record:
            incomplete.append(
                {
                    "ticker": ticker,
                    "item_id": f"ticker:{ticker}",
                    "missing_thesis": True,
                    "missing_kill": True,
                }
            )

    tickers = sorted({x["ticker"] for x in incomplete})
    headline = (
        "Belief incomplete — do not size without thesis · 信念不完整 — 未有論點勿加倉"
        if tickers
        else ""
    )
    return {
        "active": bool(tickers),
        "authority": "research_only",
        "may_authorize_deploy": False,
        "incomplete_count": len(tickers),
        "incomplete_tickers": tickers,
        "items": incomplete[:10],
        "headline": headline,
    }


def update_belief_item(item_id: str, patch: Dict[str, Any]) -> Dict[str, Any]:
    """Persist research-only belief edits — never affects deploy authority."""
    clean = {
        k: v
        for k, v in (patch or {}).items()
        if k in _EDITABLE_FIELDS and v is not None
    }
    key = str(item_id or "").strip()
    if not key or not clean:
        raise ValueError("item_id and at least one editable field required")
    store = _load_store()
    items: Dict[str, Any] = store.setdefault("items", {})
    current = dict(items.get(key) or {})
    current.update(clean)
    current["id"] = key
    current["authority"] = "research_only"
    items[key] = current
    _save_store(store)
    return current
