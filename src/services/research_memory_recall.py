"""Recall prior vibe sessions for reusable research context."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.services.research_store import list_memory

_TOKEN = re.compile(r"[a-z0-9]{3,}", re.I)


def recall_similar_sessions(prompt: str, *, limit: int = 5) -> List[Dict[str, Any]]:
    tokens = set(_TOKEN.findall(str(prompt or "").lower()))
    if not tokens:
        return []
    rows = list_memory(limit=80, item_type="vibe_session")
    scored: List[tuple[int, Dict[str, Any]]] = []
    for row in rows:
        text = " ".join(
            [
                str(row.get("prompt") or ""),
                " ".join(row.get("lessons") or []),
                str(row.get("consensus") or ""),
            ]
        ).lower()
        row_tokens = set(_TOKEN.findall(text))
        overlap = len(tokens & row_tokens)
        if overlap > 0:
            scored.append((overlap, row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:limit]]


def attach_session_recall(payload: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    prior = recall_similar_sessions(prompt)
    if prior:
        payload["session_recall"] = {
            "matches": [
                {
                    "id": p.get("id"),
                    "prompt": (p.get("prompt") or "")[:200],
                    "consensus": p.get("consensus"),
                    "symbols": p.get("symbols"),
                }
                for p in prior
            ],
            "reusable": True,
        }
    return payload
