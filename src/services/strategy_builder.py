"""Strategy Builder — natural-language strategy drafts (research only)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from src.services.research_safety import sanitize_research_payload
from src.services.strategy_export import (
    export_pine_draft,
    export_strategy_contract_json,
)

_TICKER_RE = re.compile(r"\b([A-Z]{1,5})\b")
_MA_RE = re.compile(r"(\d+)\s*/\s*(\d+)\s*ma", re.I)
_VIX_RE = re.compile(r"vix", re.I)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _default_expiry(days: int = 30) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() + "Z"


def parse_strategy_prompt(raw_prompt: str) -> Dict[str, Any]:
    """Turn plain-language strategy into structured draft — not live orders."""
    text = str(raw_prompt or "").strip()
    lower = text.lower()
    universe = ["SPY"]
    for m in _TICKER_RE.finditer(text.upper()):
        t = m.group(1)
        if t not in {"MA", "RS", "VIX", "AND", "THE", "TO"} and t not in universe:
            universe.append(t)
    universe = universe[:8]

    timeframe = "daily"
    if "intraday" in lower or "1h" in lower or "分鐘" in text:
        timeframe = "intraday"
    elif "weekly" in lower or "週" in text:
        timeframe = "weekly"

    entry_rules: List[str] = []
    exit_rules: List[str] = []
    risk_rules: List[str] = ["Max risk per trade ≤ 1R; no add without rule"]
    regime_filters: List[str] = []

    ma_match = _MA_RE.search(text)
    if ma_match:
        fast, slow = ma_match.group(1), ma_match.group(2)
        entry_rules.append(f"Fast MA ({fast}) crosses above slow MA ({slow})")
        exit_rules.append(f"Fast MA ({fast}) crosses below slow MA ({slow})")
    elif "trend" in lower or "趨勢" in text:
        entry_rules.append("Price above rising 50MA with RS improving vs benchmark")
        exit_rules.append("Close below 50MA or RS deterioration")
    else:
        entry_rules.append(
            "Setup qualifies in Playbook watch bucket with volume confirmation"
        )
        exit_rules.append("Invalidation level hit or regime WAIT")

    if _VIX_RE.search(text) or "vix" in lower:
        regime_filters.append("VIX below elevated threshold (e.g. < 25) or declining")
    if "uptrend" in lower or "上升" in text or "regime" in lower:
        regime_filters.append(
            "Market regime uptrend / TRADE board only for deploy review"
        )
    if "唔想追高" in text or "no chase" in lower:
        risk_rules.append("No chase: entry only on pullback to monitor zone")

    invalidation = "Regime flips WAIT/NO_TRADE or structure breaks on volume"
    data_req = ["OHLCV", "benchmark", "regime", "playbook_rank"]
    if _VIX_RE.search(text):
        data_req.append("VIX")

    draft = sanitize_research_payload(
        {
            "id": str(uuid.uuid4())[:12],
            "rawPrompt": text,
            "hypothesis": text[:300] if text else "Strategy hypothesis pending detail",
            "universe": universe,
            "timeframe": timeframe,
            "entryRules": entry_rules,
            "exitRules": exit_rules,
            "riskRules": risk_rules,
            "regimeFilters": regime_filters,
            "invalidation": invalidation,
            "dataRequirements": data_req,
            "backtestConfig": {
                "benchmark": "SPY",
                "period": "2y",
                "walkForward": True,
                "monteCarlo": True,
            },
            "generatedCode": export_pine_draft(
                name="CC_Strategy_Draft",
                entry_rules=entry_rules,
                exit_rules=exit_rules,
                regime_filters=regime_filters,
            ),
            "status": "draft",
            "expiry": _default_expiry(),
            "confirmationPath": "Strategy Lab → Backtest → Playbook → Dossier",
            "authority_notice": [
                "Research draft only — not live execution",
                "Run validation before watch-rule eligibility",
            ],
        }
    )
    return draft


def strategy_draft_to_watch_intent(draft: Dict[str, Any]) -> str:
    """Bridge draft → Vibe Agent intent text."""
    assets = ", ".join((draft.get("universe") or ["WATCHLIST"])[:3])
    entry = "; ".join((draft.get("entryRules") or [])[:2])
    return f"Monitor strategy draft on {assets}: {entry}. No chase; open Playbook when validated."


def build_strategy_draft_record(raw_prompt: str) -> Dict[str, Any]:
    draft = parse_strategy_prompt(raw_prompt)
    draft["contractJson"] = export_strategy_contract_json(draft)
    return draft
