from __future__ import annotations

from typing import Any, Dict, Optional

from src.services.ai_service import get_ai_service


class FundAIService:
    @staticmethod
    def _fallback_memo(card: Dict[str, Any], regime: str, benchmark: str) -> str:
        alpha = float(card.get("excess_return_pct") or 0.0)
        regime_fit = int(card.get("regime_fit") or 0)
        gate = card.get("gate_status") or "UNKNOWN"
        holdings = (
            ", ".join(h.get("ticker", "—") for h in (card.get("holdings") or [])[:5])
            or "no current holdings"
        )
        alpha_phrase = "outperforming" if alpha >= 0 else "lagging"
        return (
            f"{card.get('display_name')} is {alpha_phrase} {benchmark} by {alpha:+.2f}% with a {gate} regime gate. "
            f"Current regime is {regime}, fit {regime_fit}%, and the sleeve is centered on {holdings}. "
            f"Base case: keep sizing aligned with {card.get('min_r_r', '—')}:1 minimum R:R and avoid adding if regime fit deteriorates."
        )

    @staticmethod
    def _fallback_expert_view(card: Dict[str, Any], regime: str) -> Dict[str, Any]:
        alpha = float(card.get("excess_return_pct") or 0.0)
        regime_fit = int(card.get("regime_fit") or 0)
        gate_status = card.get("gate_status") or "UNKNOWN"
        if regime_fit >= 80 and alpha >= 0:
            stance = "press"
            action = "Add only on leaders with clean continuation entries."
        elif regime_fit >= 50:
            stance = "hold"
            action = "Keep exposure selective and reduce laggards first."
        else:
            stance = "defend"
            action = "Pause adds and protect capital until regime fit improves."
        return {
            "stance": stance,
            "action": action,
            "gate_status": gate_status,
            "regime_gate": regime,
            "risk_flags": [
                f"Max drawdown {card.get('max_drawdown_pct', 0)}%",
                f"Sharpe {card.get('sharpe', 0)}",
            ],
            "focus": [
                f"Conviction tier: {card.get('risk_level', '—')} risk sleeve",
                f"Minimum R:R {card.get('min_r_r', '—')}:1",
                f"Regime fit {regime_fit}%",
            ],
        }

    async def build_pm_memo(
        self,
        card: Dict[str, Any],
        regime: str,
        benchmark: str,
    ) -> Dict[str, Any]:
        ai_service = get_ai_service()
        holdings = (
            "\n".join(
                f"- {h.get('ticker', '—')} weight {(float(h.get('weight', 0))*100):.1f}% score {h.get('score', 0)}"
                for h in (card.get("holdings") or [])[:8]
            )
            or "- No holdings"
        )
        prompt = (
            f"Fund: {card.get('display_name')}\n"
            f"Mandate: {card.get('mandate')}\n"
            f"Regime: {regime}\n"
            f"Gate: {card.get('gate_status')}\n"
            f"Benchmark: {benchmark}\n"
            f"Return: {card.get('fund_return_pct')}% | Alpha: {card.get('excess_return_pct')}% | Sharpe: {card.get('sharpe')} | MaxDD: {card.get('max_drawdown_pct')}%\n"
            f"Regime fit: {card.get('regime_fit')}%\n"
            f"Adds: {', '.join(card.get('adds') or []) or 'none'}\n"
            f"Reduces: {', '.join(card.get('reduces') or []) or 'none'}\n"
            f"Exits: {', '.join(card.get('exits') or []) or 'none'}\n"
            f"Top holdings:\n{holdings}\n"
            "Write a PM memo in <=120 words: 1) state posture, 2) what to do next, 3) key risk."
        )
        memo = await ai_service.generate_pm_memo(prompt)
        return {
            "fund_id": card.get("id"),
            "memo": memo or self._fallback_memo(card, regime, benchmark),
            "provider": ai_service.stats.get("last_provider"),
            "model": ai_service.stats.get("last_model"),
            "regime_gate": regime,
            "gate_status": card.get("gate_status"),
        }

    async def build_expert_view(
        self,
        card: Dict[str, Any],
        regime: str,
    ) -> Dict[str, Any]:
        ai_service = get_ai_service()
        prompt = (
            f"Fund card:\n{card}\n"
            f"Current regime: {regime}\n"
            "Return JSON only with keys: stance, action, gate_status, regime_gate, risk_flags, focus. "
            "Keep action to one sentence and each list to max 3 items."
        )
        response = await ai_service.generate_json(
            system="You are CC Fund Expert View generator. Return only compact JSON.",
            user_prompt=prompt,
            preferred_model=None,
            max_tokens=300,
        ) or self._fallback_expert_view(card, regime)
        response.setdefault("fund_id", card.get("id"))
        response.setdefault("gate_status", card.get("gate_status"))
        response.setdefault("regime_gate", regime)
        response["provider"] = ai_service.stats.get("last_provider")
        response["model"] = ai_service.stats.get("last_model")
        return response


_instance: Optional[FundAIService] = None


def get_fund_ai_service() -> FundAIService:
    global _instance
    if _instance is None:
        _instance = FundAIService()
    return _instance
