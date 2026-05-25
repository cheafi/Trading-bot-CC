from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.ai_service import get_ai_service
from src.services.trade_memory_service import get_trade_memory_service


class TradeReviewAIService:
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
    def _fallback_review(
        trade: Dict[str, Any], similar_cases: list[Dict[str, Any]]
    ) -> Dict[str, Any]:
        r_multiple = float(trade.get("r_multiple") or 0.0)
        regime = trade.get("regime_at_entry") or "unknown"
        conviction = TradeReviewAIService._conviction(trade)
        verdict = "GOOD_PROCESS" if r_multiple > 0 else "PROCESS_REVIEW"

        # Structured grading (A/B/C/F)
        thesis_quality = "A" if r_multiple > 0 else "C"
        timing_quality = "B" if float(trade.get("hold_days") or 0) > 0 else "F"
        exit_quality = "A" if r_multiple > -1 else "F"
        regime_alignment = "A" if "BULL" in regime.upper() and r_multiple > 0 else "C"

        what_worked = [f"Thesis Quality: {thesis_quality}", f"Regime Alignment: {regime_alignment}"]
        what_failed = [f"Timing Quality: {timing_quality}", f"Exit Quality: {exit_quality}"]
        repeat_rule = "Repeat only when regime matches and R:R is at least 2:1." if r_multiple > 0 else "Do not repeat unless entry timing avoids noise."

        lesson = f"In {regime}, {conviction} setups " + ("have an edge if held patiently." if r_multiple > 0 else "fail when discipline is broken.")

        return {
            "verdict": verdict,
            "what_worked": what_worked,
            "what_failed": what_failed,
            "repeat_rule": repeat_rule,
            "confidence_recalibration": "Keep unchanged." if r_multiple > 0 else "Downshift conviction until evidence improves.",
            "similar_case_note": similar_cases[0]["lesson"] if similar_cases else "No real similar cases to compare against yet.",
            "structured_lesson": lesson
        }

    async def review_trade(
        self,
        trade: Dict[str, Any],
        similar_limit: int = 3,
    ) -> Dict[str, Any]:
        ai_service = get_ai_service()
        memory_service = get_trade_memory_service()
        similar_cases = await memory_service.find_similar_cases(
            trade, limit=similar_limit
        )
        prompt = (
            f"Closed trade: {trade}\n"
            f"Similar cases: {similar_cases}\n"
            "Return JSON only with keys: verdict, what_worked, what_failed, repeat_rule, confidence_recalibration, similar_case_note. "
            "Each list max 3 bullets; use strings, not nested objects."
        )
        review = await ai_service.review_trade(prompt) or self._fallback_review(
            trade, similar_cases
        )
        review["trade"] = {
            "ticker": trade.get("ticker"),
            "entry_time": trade.get("entry_time"),
            "exit_time": trade.get("exit_time"),
            "strategy_id": trade.get("strategy_id"),
            "regime_at_entry": trade.get("regime_at_entry"),
            "conviction": self._conviction(trade),
            "r_multiple": trade.get("r_multiple"),
            "pnl_pct": trade.get("pnl_pct"),
        }
        review["similar_cases"] = similar_cases
        review["provider"] = ai_service.stats.get("last_provider")
        review["model"] = ai_service.stats.get("last_model")
        return review


_instance: Optional[TradeReviewAIService] = None


def get_trade_review_ai_service() -> TradeReviewAIService:
    global _instance
    if _instance is None:
        _instance = TradeReviewAIService()
    return _instance
