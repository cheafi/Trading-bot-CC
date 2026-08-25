"""Knowledge Graph MVP — theme clusters for Discovery / IO (Sprint 121/123)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_GRAPH_PATH = _DATA_DIR / "artifacts" / "knowledge_graph" / "graph.json"


def _load_graph() -> Dict[str, Any]:
    if _GRAPH_PATH.is_file():
        try:
            data = json.loads(_GRAPH_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.debug("knowledge graph load failed: %s", exc)
    return {"nodes": [], "edges": [], "theme_clusters": {}}


def _save_graph(data: Dict[str, Any]) -> None:
    _GRAPH_PATH.parent.mkdir(parents=True, exist_ok=True)
    _GRAPH_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def theme_cluster_id_for(ticker: str) -> str:
    """Map ticker → theme cluster via static theme tags."""
    try:
        from src.core.stock_universe import etf_theme_for

        theme = etf_theme_for(ticker.upper()) or "general"
    except Exception:
        theme = "general"
    slug = theme.lower().replace(" ", "_").replace("/", "_")
    return f"theme-{slug}"


def neighbors_for(ticker: str, *, limit: int = 8) -> Dict[str, Any]:
    """Return graph neighbors for a ticker — research_only."""
    sym = ticker.upper()
    cluster = theme_cluster_id_for(sym)
    graph = _load_graph()
    cluster_members = list((graph.get("theme_clusters") or {}).get(cluster) or [])
    if sym not in cluster_members:
        cluster_members = [sym] + [m for m in cluster_members if m != sym]
    return {
        "ticker": sym,
        "theme_cluster_id": cluster,
        "neighbors": cluster_members[:limit],
        "authority": "research_only",
        "confidence": "low" if len(cluster_members) < 5 else "medium",
    }


def register_tickers(tickers: List[str]) -> None:
    """Incrementally register tickers into theme clusters."""
    graph = _load_graph()
    clusters: Dict[str, List[str]] = dict(graph.get("theme_clusters") or {})
    for raw in tickers:
        sym = str(raw or "").upper()
        if not sym:
            continue
        cid = theme_cluster_id_for(sym)
        members = list(clusters.get(cid) or [])
        if sym not in members:
            members.append(sym)
        clusters[cid] = members[:200]
    graph["theme_clusters"] = clusters
    _save_graph(graph)
