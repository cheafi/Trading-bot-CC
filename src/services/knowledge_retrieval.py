"""Knowledge retrieval — prior lessons from journal + belief history (research_only)."""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

from src.core.ai_provider import AUTHORITY_RESEARCH_ONLY, azure_search_configured

logger = logging.getLogger(__name__)

_JOURNAL_PATH = Path(__file__).resolve().parents[2] / "data" / "decision_journal.jsonl"
_BELIEF_PATH = Path(__file__).resolve().parents[2] / "data" / "belief_review.json"


def _load_journal_rows() -> List[Dict[str, Any]]:
    if not _JOURNAL_PATH.is_file():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        for line in _JOURNAL_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    except OSError as exc:
        logger.debug("knowledge journal read failed: %s", exc)
    return rows


def _load_belief_items() -> Dict[str, Any]:
    if not _BELIEF_PATH.is_file():
        return {}
    try:
        data = json.loads(_BELIEF_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.debug("knowledge belief read failed: %s", exc)
        return {}
    if not isinstance(data, dict):
        return {}
    return data.get("items") or {}


def _search_azure_index(ticker: str, *, limit: int = 3) -> List[Dict[str, Any]]:
    """Optional Azure AI Search hook — returns snippets when index env is configured."""
    if not azure_search_configured():
        return []
    endpoint = os.getenv("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
    index = os.getenv("AZURE_SEARCH_INDEX", "")
    key = os.getenv("AZURE_SEARCH_KEY", "")
    query = f"{ticker} trading thesis lesson"
    url = (
        f"{endpoint}/indexes/{urllib.parse.quote(index)}/docs"
        f"?api-version=2023-11-01&search={urllib.parse.quote(query)}"
        f"&$top={limit}&searchMode=any"
    )
    req = urllib.request.Request(
        url,
        headers={"api-key": key, "Content-Type": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        logger.debug("azure search hook skipped: %s", exc)
        return []
    hits: List[Dict[str, Any]] = []
    for row in payload.get("value") or []:
        if not isinstance(row, dict):
            continue
        text = str(
            row.get("content")
            or row.get("lesson")
            or row.get("text")
            or row.get("caption")
            or ""
        ).strip()
        if not text:
            continue
        hits.append(
            {
                "source": "azure_search",
                "lesson": text[:320],
                "score": row.get("@search.score"),
                "authority": AUTHORITY_RESEARCH_ONLY,
            }
        )
    return hits


def build_ticker_lessons(ticker: str, *, limit: int = 5) -> Dict[str, Any]:
    """Aggregate prior lessons for ticker from decision journal + belief review."""
    sym = str(ticker or "").strip().upper()
    if not sym:
        raise ValueError("ticker required")

    lessons: List[Dict[str, Any]] = []
    seen: set[str] = set()

    for row in reversed(_load_journal_rows()):
        row_ticker = str(row.get("ticker") or "").upper()
        if row_ticker != sym:
            continue
        key = str(row.get("entry_id") or row.get("decision_id") or "")
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        thesis = str(row.get("thesis") or "").strip()
        learning = str(row.get("learning") or "").strip()
        outcome = row.get("outcome")
        lesson_text = learning or thesis
        if not lesson_text:
            continue
        lessons.append(
            {
                "source": "decision_journal",
                "entry_id": row.get("entry_id"),
                "decision": row.get("decision"),
                "date": row.get("date") or row.get("recorded_at", "")[:10],
                "lesson": lesson_text[:320],
                "outcome": outcome,
                "stub": bool(row.get("stub")),
                "authority": "research_only",
            }
        )
        if len(lessons) >= limit:
            break

    if len(lessons) < limit:
        items = _load_belief_items()
        for item_id, item in items.items():
            if not isinstance(item, dict):
                continue
            if str(item.get("ticker") or "").upper() != sym:
                continue
            thesis = str(item.get("thesis") or "").strip()
            kill = str(item.get("kill_condition") or "").strip()
            if not thesis and not kill:
                continue
            dedupe = f"belief:{item_id}"
            if dedupe in seen:
                continue
            seen.add(dedupe)
            lessons.append(
                {
                    "source": "belief_review",
                    "item_id": item_id,
                    "date": None,
                    "lesson": (thesis or kill)[:320],
                    "kill_condition": kill or None,
                    "status": item.get("status"),
                    "authority": "research_only",
                }
            )
            if len(lessons) >= limit:
                break

    search_hits = _search_azure_index(sym, limit=max(0, limit - len(lessons)))
    for hit in search_hits:
        dedupe = f"search:{hit.get('lesson', '')[:48]}"
        if dedupe in seen:
            continue
        seen.add(dedupe)
        lessons.append(hit)
        if len(lessons) >= limit:
            break

    headline = (
        f"Prior lessons · {sym} — {len(lessons)} from journal/belief history"
        if lessons
        else f"No prior lessons · {sym} — first research pass"
    )
    return {
        "status": "ok" if lessons else "empty",
        "authority": "research_only",
        "ticker": sym,
        "headline": headline,
        "lesson_count": len(lessons),
        "lessons": lessons,
        "four_questions": {
            "know": f"Prior decisions and beliefs recorded for {sym}.",
            "believe": "Past thesis may still apply — verify before capital.",
            "doubt": "Sample size and regime drift may invalidate prior lessons.",
            "act": "Review lessons before deploy; research_only.",
        },
    }
