"""Operator-facing warmup checklist and playbook rank buckets (CC X contract)."""

from __future__ import annotations

from typing import Any, Dict, List


def build_warmup_module_checklist(
    *,
    shell_ok: bool,
    cached_board_ok: bool,
    market_data_ok: bool,
    dossier_core_ok: bool,
    enrichments_ok: bool,
    broker_ok: bool,
) -> List[Dict[str, Any]]:
    """Checklist rows for /health while the FastAPI backend warms up."""
    return [
        {"key": "shell", "label": "Shell", "ready": shell_ok},
        {"key": "cached_board", "label": "Cached board", "ready": cached_board_ok},
        {"key": "market_data", "label": "Market data", "ready": market_data_ok},
        {"key": "dossier_core", "label": "Dossier core", "ready": dossier_core_ok},
        {"key": "enrichments", "label": "Enrichments", "ready": enrichments_ok},
        {"key": "broker", "label": "Broker", "ready": broker_ok},
    ]


def _playbook_bucket_key(row: Dict[str, Any]) -> str:
    act = str(row.get("action") or row.get("effective_action") or "WATCH").upper()
    if act in ("DEPLOY", "BUY", "ENTER", "TRADE", "EXECUTE"):
        return "deploy"
    if act in ("PILOT", "PROBE", "SCALE_IN"):
        return "pilot"
    if act in ("WATCH", "MONITOR"):
        return "watch"
    return "other"


def build_playbook_rank_buckets(
    opportunities: List[Dict[str, Any]],
    near_miss: List[Dict[str, Any]],
) -> Dict[str, Any]:
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "deploy": [],
        "pilot": [],
        "watch": [],
        "near_miss": list(near_miss or []),
        "other": [],
    }
    for row in opportunities or []:
        key = _playbook_bucket_key(row)
        buckets[key].append(row)
    return {
        **buckets,
        "counts": {name: len(rows) for name, rows in buckets.items()},
    }
