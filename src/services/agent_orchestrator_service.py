"""
Agent Orchestrator Service — Sprint 77
======================================
Multi-agent style deliberation inspired by research projects like TradingAgents,
but implemented with deterministic, in-house engines:

Research -> Macro -> Risk -> Execution -> Critic -> Final action

No direct LLM dependency here; this service composes existing engines and
risk limits so output remains auditable and reproducible.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.core.risk_limits import VIX
from src.engines.decision_persistence import get_journal
from src.engines.expert_council import ExpertCouncil
from src.services.brief_data_service import all_brief_tickers, find_signal, load_brief
from src.services.regime_service import RegimeService

logger = logging.getLogger(__name__)


@dataclass
class AgentRunResult:
    ticker: str
    final_action: str
    conviction_tier: str
    rr_multiple: float
    regime_gate: str
    summary: str
    agents: Dict[str, Any]
    council: Dict[str, Any]
    journal: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "final_action": self.final_action,
            "conviction_tier": self.conviction_tier,
            "rr_multiple": round(self.rr_multiple, 2),
            "regime_gate": self.regime_gate,
            "summary": self.summary,
            "agents": self.agents,
            "council": self.council,
            "journal": self.journal,
        }


class AgentOrchestratorService:
    """Deterministic agent orchestrator over existing council + risk stack."""

    def __init__(self, council: Optional[ExpertCouncil] = None) -> None:
        self._council = council or ExpertCouncil()

    def _load_signal(self, ticker: str) -> Dict[str, Any]:
        brief = load_brief()
        sig, section = find_signal(ticker, brief)
        if not sig:
            sig = {"ticker": ticker, "strategy": "unknown", "score": 0.0}
            section = "not_in_brief"
        out = dict(sig)
        out["ticker"] = ticker
        out["brief_section"] = section
        return out

    @staticmethod
    def _conviction_tier(action: str) -> str:
        if action == "TRADE":
            return "TRADE"
        if action in ("WATCH", "HOLD"):
            return "LEADER"
        return "WATCH"

    @staticmethod
    def _min_rr_for_tier(tier: str) -> float:
        return 3.0 if tier == "TRADE" else 2.0

    def run_ticker(
        self,
        ticker: str,
        regime: Optional[Dict[str, Any]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        ticker = ticker.strip().upper()
        regime = regime or RegimeService.get()
        signal = self._load_signal(ticker)

        council_result = self._council.evaluate(signal, regime)
        enriched = council_result.pipeline.to_dict()

        action = str(enriched.get("action", "WATCH"))
        rr = float(signal.get("risk_reward") or 0.0)
        conviction_tier = self._conviction_tier(action)

        # Regime gate (hard): should_trade + VIX crisis guard
        vix_now = float(regime.get("vix", 0.0) or 0.0)
        regime_ok = bool(regime.get("should_trade", True)) and vix_now < float(
            VIX.crisis
        )
        regime_gate = "PASS" if regime_ok else "BLOCK"

        # Risk policy learned from multi-agent workflows:
        # - TRADE requires >=3R, WATCH/LEADER requires >=2R
        # - If regime is blocked, force NO_TRADE
        notes: List[str] = []
        if action == "TRADE":
            min_rr = self._min_rr_for_tier(conviction_tier)
            if rr > 0 and rr < min_rr:
                action = "WATCH"
                conviction_tier = "LEADER"
                notes.append(f"R:R {rr:.2f}R below {min_rr:.1f}R minimum for TRADE")

        if not regime_ok and action == "TRADE":
            action = "NO_TRADE"
            conviction_tier = "WATCH"
            notes.append("Regime gate blocked (risk-off or crisis VIX)")

        explanation = (
            enriched.get("explanation", {})
            if isinstance(enriched.get("explanation"), dict)
            else {}
        )

        agents = {
            "research": {
                "thesis": explanation.get("why_now", "No clear thesis."),
                "counterpoint": explanation.get("why_not_stronger", ""),
            },
            "macro": {
                "regime": regime.get("regime", "UNKNOWN"),
                "vix": vix_now,
                "regime_gate": regime_gate,
            },
            "risk": {
                "dominant_risk": council_result.verdict.dominant_risk,
                "risk_level": enriched.get("risk_level", "MEDIUM"),
                "invalidation": explanation.get("invalidation", ""),
            },
            "execution": {
                "entry": signal.get("entry") or signal.get("entry_price") or "—",
                "stop": signal.get("stop") or signal.get("stop_loss") or "—",
                "target": signal.get("target") or signal.get("take_profit") or "—",
                "rr_multiple": rr,
            },
            "critic": {
                "agreement_ratio": council_result.verdict.agreement_ratio,
                "dissent_count": len(council_result.verdict.dissenting_views),
                "notes": notes,
            },
        }

        summary = (
            f"{ticker}: action={action}, tier={conviction_tier}, "
            f"R:R={rr:.2f}R, regime_gate={regime_gate}"
        )

        journal_info: Dict[str, Any] = {
            "persisted": False,
            "path": "data/artifacts/decision_journal.jsonl",
        }
        if persist:
            try:
                score = float(enriched.get("final_confidence", 0.0) or 0.0)
                entry = get_journal().record(
                    ticker=ticker,
                    decision_tier=conviction_tier,
                    composite_score=score,
                    should_trade=(action == "TRADE"),
                    regime=str(regime.get("regime", "unknown")),
                    sector=str(
                        signal.get("sector") or enriched.get("sector") or "unknown"
                    ),
                    entry_price=float(signal.get("entry_price") or 0.0),
                    stop_price=float(signal.get("stop_loss") or 0.0),
                    target_price=float(signal.get("take_profit") or 0.0),
                    expert_consensus=str(council_result.verdict.direction),
                    extra={
                        "agent_mode": "deterministic-multi-agent",
                        "final_action": action,
                        "regime_gate": regime_gate,
                        "rr_multiple": rr,
                        "agents": agents,
                        "council": {
                            "agreement_ratio": council_result.verdict.agreement_ratio,
                            "dominant_risk": council_result.verdict.dominant_risk,
                            "verdict_summary": council_result.verdict.verdict_summary,
                        },
                    },
                )
                journal_info = {
                    "persisted": True,
                    "timestamp": entry.get("timestamp"),
                    "path": "data/artifacts/decision_journal.jsonl",
                }
            except Exception as exc:
                logger.warning(
                    "[AgentOrchestrator] journal persistence failed for %s: %s",
                    ticker,
                    exc,
                )
                journal_info["error"] = str(exc)

        return AgentRunResult(
            ticker=ticker,
            final_action=action,
            conviction_tier=conviction_tier,
            rr_multiple=rr,
            regime_gate=regime_gate,
            summary=summary,
            agents=agents,
            council={
                "direction": council_result.verdict.direction,
                "composite_conviction": council_result.verdict.composite_conviction,
                "agreement_ratio": council_result.verdict.agreement_ratio,
                "dominant_risk": council_result.verdict.dominant_risk,
                "verdict_summary": council_result.verdict.verdict_summary,
            },
            journal=journal_info,
        ).to_dict()

    def run_batch(
        self, tickers: List[str], limit: int = 10, persist: bool = False
    ) -> Dict[str, Any]:
        out = []
        for t in tickers[: max(1, limit)]:
            try:
                out.append(self.run_ticker(t, persist=persist))
            except Exception as exc:
                logger.warning("[AgentOrchestrator] %s failed: %s", t, exc)
                out.append({"ticker": t, "error": str(exc)})
        return {"count": len(out), "results": out}

    def run_today(self, limit: int = 10, persist: bool = False) -> Dict[str, Any]:
        tickers = all_brief_tickers()[: max(1, limit)]
        if not tickers:
            return {"count": 0, "results": [], "message": "No brief tickers available"}
        return self.run_batch(tickers, limit=limit, persist=persist)


_agent_orchestrator: Optional[AgentOrchestratorService] = None


def get_agent_orchestrator_service() -> AgentOrchestratorService:
    global _agent_orchestrator
    if _agent_orchestrator is None:
        _agent_orchestrator = AgentOrchestratorService()
    return _agent_orchestrator
