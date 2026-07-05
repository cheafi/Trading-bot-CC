from __future__ import annotations

import json
import logging
import math
import os
from typing import Any, Dict, List, Optional

from src.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)

_TRADES_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "closed_trades.jsonl"
)


class TradeMemoryService:
    def __init__(self) -> None:
        self._memories: Optional[List[Dict[str, Any]]] = None
        self._vector_ready = False

    @staticmethod
    def _load_trades(path: str = _TRADES_PATH) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        if not os.path.exists(path):
            return rows
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except Exception:
                    continue
        return rows

    @staticmethod
    def _conviction(trade: Dict[str, Any]) -> str:
        return (
            trade.get("conviction")
            or trade.get("conviction_tier")
            or trade.get("tier")
            or trade.get("signal_tier")
            or "WATCH"
        )

    @staticmethod
    def _trade_text(trade: Dict[str, Any]) -> str:
        fields = [
            trade.get("ticker", ""),
            trade.get("strategy_id", ""),
            trade.get("regime_at_entry", ""),
            TradeMemoryService._conviction(trade),
            str(trade.get("setup_grade", "")),
            f"r_multiple={trade.get('r_multiple', 0)}",
            f"hold_days={trade.get('hold_days', 0)}",
            f"pnl_pct={trade.get('pnl_pct', 0)}",
        ]
        return " | ".join(str(value) for value in fields if value not in (None, ""))

    @staticmethod
    def _token_score(left: str, right: str) -> float:
        left_tokens = {
            token for token in left.lower().replace("|", " ").split() if token
        }
        right_tokens = {
            token for token in right.lower().replace("|", " ").split() if token
        }
        if not left_tokens or not right_tokens:
            return 0.0
        return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)

    @staticmethod
    def _cosine_similarity(left: List[float], right: List[float]) -> float:
        if not left or not right or len(left) != len(right):
            return 0.0
        dot = sum(a * b for a, b in zip(left, right))
        left_mag = math.sqrt(sum(a * a for a in left))
        right_mag = math.sqrt(sum(b * b for b in right))
        if left_mag == 0 or right_mag == 0:
            return 0.0
        return dot / (left_mag * right_mag)

    async def _ensure_memories(self) -> List[Dict[str, Any]]:
        if self._memories is None:
            self._memories = []
            for trade in self._load_trades():
                self._memories.append(
                    {
                        "trade": trade,
                        "memory_text": self._trade_text(trade),
                        "embedding": None,
                    }
                )
        if self._vector_ready or not self._memories:
            return self._memories

        ai_service = get_ai_service()
        texts = [row["memory_text"] for row in self._memories]
        vectors = await ai_service.embed_texts(texts)
        if vectors and len(vectors) == len(self._memories):
            for row, vector in zip(self._memories, vectors):
                row["embedding"] = vector
            self._vector_ready = True
        return self._memories

    async def find_trade(
        self,
        ticker: Optional[str] = None,
        entry_time: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        rows = await self._ensure_memories()
        candidates = rows
        if ticker:
            ticker_upper = ticker.upper()
            candidates = [
                row
                for row in candidates
                if (row["trade"].get("ticker") or "").upper() == ticker_upper
            ]
        if entry_time:
            exact = [
                row
                for row in candidates
                if (row["trade"].get("entry_time") or "") == entry_time
            ]
            if exact:
                return exact[0]["trade"]
        if candidates:
            return sorted(
                candidates,
                key=lambda row: row["trade"].get("exit_time")
                or row["trade"].get("entry_time")
                or "",
                reverse=True,
            )[0]["trade"]
        return None

    async def find_similar_cases(
        self,
        trade: Dict[str, Any],
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        rows = await self._ensure_memories()
        if not rows:
            return []

        target_text = self._trade_text(trade)
        target_vector: Optional[List[float]] = None
        ai_service = get_ai_service()
        vectors = await ai_service.embed_texts([target_text])
        if vectors:
            target_vector = vectors[0]

        scored: List[Dict[str, Any]] = []
        for row in rows:
            current = row["trade"]
            if current is trade:
                continue
            if current.get("ticker") == trade.get("ticker") and current.get(
                "entry_time"
            ) == trade.get("entry_time"):
                continue
            score = self._token_score(target_text, row["memory_text"])
            if target_vector and row.get("embedding"):
                score = max(
                    score, self._cosine_similarity(target_vector, row["embedding"])
                )
            if (current.get("strategy_id") or "") == (trade.get("strategy_id") or ""):
                score += 0.08
            if (current.get("regime_at_entry") or "") == (
                trade.get("regime_at_entry") or ""
            ):
                score += 0.08
            if self._conviction(current) == self._conviction(trade):
                score += 0.05
            scored.append(
                {
                    "similarity": round(score, 3),
                    "ticker": current.get("ticker", "—"),
                    "strategy_id": current.get("strategy_id"),
                    "regime_at_entry": current.get("regime_at_entry"),
                    "conviction": self._conviction(current),
                    "r_multiple": current.get("r_multiple"),
                    "pnl_pct": current.get("pnl_pct"),
                    "hold_days": current.get("hold_days"),
                    "entry_time": current.get("entry_time"),
                    "exit_time": current.get("exit_time"),
                    "setup_grade": current.get("setup_grade"),
                    "lesson": self._build_lesson(current),
                }
            )

        scored.sort(key=lambda row: row["similarity"], reverse=True)
        return scored[:limit]

    @staticmethod
    def _build_lesson(trade: Dict[str, Any]) -> str:
        r_multiple = float(trade.get("r_multiple") or 0.0)
        regime = trade.get("regime_at_entry") or "unknown regime"
        conviction = TradeMemoryService._conviction(trade)
        if r_multiple > 1:
            return f"Winner: {conviction} signal worked in {regime}; let strength run toward 2R-3R."
        if r_multiple > 0:
            return f"Small win: {conviction} signal survived in {regime}; exits likely capped upside early."
        if r_multiple < -1:
            return f"Hard loser: avoid repeating the same {conviction} setup in {regime} without tighter stop discipline."
        return f"Soft miss: thesis weakened in {regime}; demand cleaner trigger before re-entry."


_instance: Optional[TradeMemoryService] = None


def get_trade_memory_service() -> TradeMemoryService:
    global _instance
    if _instance is None:
        _instance = TradeMemoryService()
    return _instance
