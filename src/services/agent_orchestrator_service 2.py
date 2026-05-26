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
import math
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from src.core.risk_limits import VIX
from src.engines.decision_persistence import get_journal
from src.engines.expert_council import ExpertCouncil
from src.research_lab.slippage import estimate_slippage
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

    @staticmethod
    def _clamp(v: float, lo: float, hi: float) -> float:
        return max(lo, min(hi, v))

    @staticmethod
    def _numeric_stance(action: str) -> float:
        a = str(action or "").upper()
        if a in ("TRADE", "WATCH", "HOLD"):
            return 1.0
        if a in ("NO_TRADE", "REJECT", "EXIT", "REDUCE"):
            return -1.0
        return 0.0

    def _estimate_execution_quality(
        self,
        signal: Dict[str, Any],
        regime: Dict[str, Any],
        rr: float,
    ) -> Dict[str, Any]:
        """Estimate execution friction for critic feedback loop."""
        price = float(signal.get("entry_price") or signal.get("entry") or 100.0)
        stop = float(signal.get("stop_loss") or signal.get("stop") or 0.0)
        avg_volume = float(
            signal.get("avg_volume")
            or signal.get("average_volume")
            or signal.get("volume")
            or 1_000_000
        )
        vix_now = float(regime.get("vix", 18.0) or 18.0)

        # Spread proxy (bps) from price/liquidity/volatility regime
        if price < 5:
            spread_bps = 70.0
        elif price < 20:
            spread_bps = 35.0
        else:
            spread_bps = 15.0

        if avg_volume < 500_000:
            spread_bps += 25.0
        elif avg_volume < 2_000_000:
            spread_bps += 10.0

        if vix_now >= 28:
            spread_bps += 15.0
        elif vix_now >= 20:
            spread_bps += 8.0

        risk_per_share = abs(price - stop) if stop > 0 else price * 0.02
        risk_per_share = max(risk_per_share, 0.01)
        # 1% risk on a 100k reference book => 1,000 USD risk budget
        size_shares = max(1, int(1000.0 / risk_per_share))

        # estimate_slippage expects avg_spread_pct in percentage points.
        avg_spread_pct = max(0.01, (spread_bps * 2.0) / 100.0)
        slip = estimate_slippage(
            price=max(price, 0.01),
            size_shares=size_shares,
            avg_daily_volume=max(1, int(avg_volume)),
            avg_spread_pct=avg_spread_pct,
        )

        one_way_bps = float(slip.total_cost_bps)
        round_trip_bps = float(slip.round_trip_bps)

        # Fill quality score: lower costs + acceptable R:R => higher score.
        fill_score = 100.0 - one_way_bps * 1.15
        if rr < 2.0:
            fill_score -= 12.0
        fill_score = self._clamp(fill_score, 0.0, 100.0)

        if fill_score >= 70:
            fill_quality = "HIGH"
        elif fill_score >= 50:
            fill_quality = "MEDIUM"
        else:
            fill_quality = "LOW"

        return {
            "expected_slippage_bps": round(one_way_bps, 2),
            "round_trip_cost_bps": round(round_trip_bps, 2),
            "spread_proxy_bps": round(spread_bps, 1),
            "fill_quality": fill_quality,
            "fill_score": round(fill_score, 1),
            "estimated_shares": size_shares,
        }

    @staticmethod
    def _realized_outcome_signal(entry: Dict[str, Any]) -> Optional[float]:
        outcome = str(entry.get("outcome") or "").lower()
        ret = entry.get("actual_return_pct")
        if ret is not None:
            try:
                rv = float(ret)
                if rv > 0:
                    return 1.0
                if rv < 0:
                    return -1.0
                return 0.0
            except Exception:
                pass
        if outcome in ("win", "target_hit"):
            return 1.0
        if outcome in ("loss", "stopped_out"):
            return -1.0
        if outcome in ("scratch", "flat"):
            return 0.0
        return None

    def _agent_prediction_signal(self, entry: Dict[str, Any], agent: str) -> float:
        agents_obj = entry.get("agents")
        agents: Dict[str, Any] = agents_obj if isinstance(agents_obj, dict) else {}
        node_obj = agents.get(agent)
        node: Dict[str, Any] = node_obj if isinstance(node_obj, dict) else {}

        if "stance" in node:
            try:
                return self._clamp(float(node.get("stance") or 0.0), -1.0, 1.0)
            except Exception:
                pass

        # Backward-compatible fallback for old rows without per-agent stance.
        action = str(entry.get("final_action") or entry.get("decision_tier") or "")
        regime_gate = str(entry.get("regime_gate") or "").upper()
        rr = float(entry.get("rr_multiple") or 0.0)

        if agent == "macro":
            return 1.0 if regime_gate == "PASS" else -1.0
        if agent == "risk":
            return 1.0 if action in ("TRADE", "WATCH") else -1.0
        if agent == "execution":
            return 1.0 if rr >= 2.0 else -1.0
        if agent == "critic":
            council_obj = entry.get("council")
            council = council_obj if isinstance(council_obj, dict) else {}
            agreement = float(council.get("agreement_ratio") or 0.0)
            return 1.0 if agreement >= 0.6 else -1.0
        return self._numeric_stance(action)

    def _series_metrics(self, values: List[float]) -> Dict[str, Any]:
        n = len(values)
        if n == 0:
            return {
                "samples": 0,
                "ic": None,
                "ir": None,
                "hit_rate": None,
            }
        mean_v = sum(values) / n
        var = sum((x - mean_v) ** 2 for x in values) / n
        std = math.sqrt(var)
        ir = (mean_v / std) if std > 1e-9 else None
        hit_rate = len([x for x in values if x > 0]) / n
        return {
            "samples": n,
            "ic": round(mean_v, 4),
            "ir": round(ir, 4) if ir is not None else None,
            "hit_rate": round(hit_rate, 4),
        }

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
        action_stance = self._numeric_stance(action)

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

        execution_quality = self._estimate_execution_quality(signal, regime, rr)
        if execution_quality["fill_quality"] == "LOW":
            notes.append(
                f"Execution quality low ({execution_quality['expected_slippage_bps']:.1f} bps one-way)"
            )
            if action == "TRADE":
                action = "WATCH"
                conviction_tier = "LEADER"
                notes.append("Downgraded TRADE to WATCH due to execution friction")

        explanation = (
            enriched.get("explanation", {})
            if isinstance(enriched.get("explanation"), dict)
            else {}
        )

        agents = {
            "research": {
                "thesis": explanation.get("why_now", "No clear thesis."),
                "counterpoint": explanation.get("why_not_stronger", ""),
                "stance": action_stance,
                "confidence": round(self._clamp(rr / 3.0, 0.2, 0.95), 3),
            },
            "macro": {
                "regime": regime.get("regime", "UNKNOWN"),
                "vix": vix_now,
                "regime_gate": regime_gate,
                "stance": 1.0 if regime_gate == "PASS" else -1.0,
                "confidence": round(self._clamp(1.0 - (vix_now / 45.0), 0.1, 0.95), 3),
            },
            "risk": {
                "dominant_risk": council_result.verdict.dominant_risk,
                "risk_level": enriched.get("risk_level", "MEDIUM"),
                "invalidation": explanation.get("invalidation", ""),
                "stance": 1.0 if action in ("TRADE", "WATCH", "HOLD") else -1.0,
                "confidence": round(
                    self._clamp(council_result.verdict.agreement_ratio, 0.2, 0.95), 3
                ),
            },
            "execution": {
                "entry": signal.get("entry") or signal.get("entry_price") or "—",
                "stop": signal.get("stop") or signal.get("stop_loss") or "—",
                "target": signal.get("target") or signal.get("take_profit") or "—",
                "rr_multiple": rr,
                "expected_slippage_bps": execution_quality["expected_slippage_bps"],
                "fill_quality": execution_quality["fill_quality"],
                "fill_score": execution_quality["fill_score"],
                "stance": 1.0 if execution_quality["fill_score"] >= 50 else -1.0,
                "confidence": round(execution_quality["fill_score"] / 100.0, 3),
            },
            "critic": {
                "agreement_ratio": council_result.verdict.agreement_ratio,
                "dissent_count": len(council_result.verdict.dissenting_views),
                "notes": notes,
                "execution_quality": execution_quality,
                "stance": 1.0 if len(notes) == 0 else -1.0,
                "confidence": round(
                    self._clamp(council_result.verdict.agreement_ratio, 0.2, 0.95), 3
                ),
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
                        "execution_quality": execution_quality,
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

    def reliability_report(
        self,
        lookback: int = 600,
        min_samples: int = 5,
    ) -> Dict[str, Any]:
        """
        Per-agent reliability by regime using IC/IR style statistics.

        IC here is mean directional edge (+1 correct, -1 wrong).
        IR is mean edge divided by edge volatility.
        """
        rows = get_journal().get_recent(limit=max(50, lookback))
        rows = [
            r
            for r in rows
            if str(r.get("agent_mode") or "") == "deterministic-multi-agent"
        ]

        resolved = []
        for r in rows:
            realized = self._realized_outcome_signal(r)
            if realized is None:
                continue
            resolved.append((r, realized))

        agent_names = ["research", "macro", "risk", "execution", "critic"]
        agent_report: Dict[str, Any] = {}

        for agent in agent_names:
            edge_all: List[float] = []
            by_regime: Dict[str, List[float]] = {}

            for row, realized in resolved:
                pred = self._agent_prediction_signal(row, agent)
                if pred == 0.0:
                    continue
                edge = pred * realized
                edge_all.append(edge)
                regime = str(row.get("regime") or "unknown").upper()
                by_regime.setdefault(regime, []).append(edge)

            regime_metrics: Dict[str, Any] = {}
            for regime, values in sorted(by_regime.items()):
                if len(values) < min_samples:
                    continue
                regime_metrics[regime] = self._series_metrics(values)

            summary = self._series_metrics(edge_all)
            summary["regimes"] = regime_metrics
            summary["coverage"] = (
                round((summary["samples"] / len(resolved)), 4) if resolved else 0.0
            )
            agent_report[agent] = summary

        ranked = [
            {"agent": a, **m}
            for a, m in agent_report.items()
            if m.get("samples", 0) > 0 and m.get("ic") is not None
        ]
        ranked.sort(
            key=lambda x: (x.get("ic", -999), x.get("samples", 0)), reverse=True
        )

        return {
            "mode": "deterministic-multi-agent",
            "lookback": lookback,
            "resolved_samples": len(resolved),
            "agents": agent_report,
            "top_agents": ranked[:3],
        }


_agent_orchestrator: Optional[AgentOrchestratorService] = None


def get_agent_orchestrator_service() -> AgentOrchestratorService:
    global _agent_orchestrator
    if _agent_orchestrator is None:
        _agent_orchestrator = AgentOrchestratorService()
    return _agent_orchestrator
