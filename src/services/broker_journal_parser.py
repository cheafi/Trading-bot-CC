"""Broker journal parsing for Shadow Account workflows."""

from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.services.research_safety import sanitize_research_payload

_TICKER = re.compile(r"^[A-Z0-9.\-^]{1,12}$")
_DATA = Path("data") / "closed_trades.jsonl"


def parse_journal_text(raw: str, *, fmt: Optional[str] = None) -> List[Dict[str, Any]]:
    text = str(raw or "").strip()
    if not text:
        return []
    kind = (fmt or "").lower()
    if kind == "json" or text.startswith("["):
        return _parse_json_trades(text)
    if kind == "csv" or ("," in text and "\n" in text):
        return _parse_csv_trades(text)
    return _parse_json_trades(text) or _parse_csv_trades(text)


def load_closed_trades_local(*, limit: int = 100) -> List[Dict[str, Any]]:
    if not _DATA.exists():
        return []
    rows: List[Dict[str, Any]] = []
    try:
        with open(_DATA, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError:
        return []
    return rows[-limit:]


def normalize_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for t in trades:
        if not isinstance(t, dict):
            continue
        ticker = str(t.get("ticker") or t.get("symbol") or "").upper().strip()
        if ticker and not _TICKER.match(ticker):
            continue
        pnl = t.get("pnl")
        if pnl is None:
            pnl = t.get("pnl_pct") or t.get("realized_pnl")
        out.append(
            {
                "ticker": ticker or None,
                "pnl": pnl,
                "pnl_pct": t.get("pnl_pct"),
                "exit_reason": t.get("exit_reason") or t.get("notes") or t.get("reason"),
                "early_exit": bool(t.get("early_exit")),
                "chase": bool(t.get("chase")),
                "average_down": bool(t.get("average_down")),
                "revenge": bool(t.get("revenge")),
                "setup_valid": t.get("setup_valid"),
            }
        )
    return out[:200]


def parse_broker_journal(
    *,
    text: Optional[str] = None,
    fmt: Optional[str] = None,
    source: str = "upload",
    use_local_closed: bool = False,
    limit: int = 100,
) -> Dict[str, Any]:
    trades: List[Dict[str, Any]] = []
    if use_local_closed:
        trades = load_closed_trades_local(limit=limit)
        source = "closed_trades_jsonl"
    elif text:
        trades = parse_journal_text(text, fmt=fmt)
    normalized = normalize_trades(trades)
    rules = extract_rules_from_trades(normalized)
    return sanitize_research_payload(
        {
            "source": source,
            "trade_count": len(normalized),
            "trades": normalized,
            "extracted_rules": rules,
            "authority": "research_only",
        }
    )


def extract_rules_from_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Light rule extraction from journal tags — not ML."""
    rules: List[Dict[str, Any]] = []
    if any(t.get("early_exit") for t in trades):
        rules.append(
            {
                "id": "no_discretionary_early_exit",
                "text": "Hold until dossier invalidation unless stop hit.",
            }
        )
    if any(t.get("chase") for t in trades):
        rules.append(
            {"id": "no_chase", "text": "No entries outside Playbook monitor zone."}
        )
    if any(t.get("revenge") for t in trades):
        rules.append(
            {"id": "cooldown_after_loss", "text": "WAIT gate binding after drawdown."}
        )
    if not rules:
        rules.append(
            {"id": "journal_baseline", "text": "Log entry thesis + invalidation before open."}
        )
    return rules


def _parse_json_trades(text: str) -> List[Dict[str, Any]]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict) and isinstance(data.get("trades"), list):
        return [x for x in data["trades"] if isinstance(x, dict)]
    return []


def _parse_csv_trades(text: str) -> List[Dict[str, Any]]:
    reader = csv.DictReader(io.StringIO(text))
    rows: List[Dict[str, Any]] = []
    for row in reader:
        if not row:
            continue
        norm = {k.strip().lower(): v for k, v in row.items() if k}
        rows.append(
            {
                "ticker": norm.get("ticker") or norm.get("symbol"),
                "pnl": norm.get("pnl") or norm.get("realized_pnl"),
                "pnl_pct": norm.get("pnl_pct") or norm.get("return_pct"),
                "exit_reason": norm.get("exit_reason") or norm.get("notes"),
            }
        )
    return rows
