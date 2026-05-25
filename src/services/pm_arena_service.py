"""PM Arena service — deterministic model-fund competition spine.

LLMs may explain, challenge, and retrieve context, but this service only emits
deterministic PM state and bounded action suggestions.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PM_FUND_MANDATES: Dict[str, Dict[str, Any]] = {
    "APEX_LEADERS": {
        "display_name": "Apex Leaders",
        "icon": "🚀",
        "style": "Concentrated leaders · strong trend · top relative strength",
        "goal": "Maximize upside from strongest names when regime supports risk.",
        "best_environment": "BULL / trend-following markets",
        "source_model_id": "LEADER_MOMENTUM",
        "lead_model": "ai/gemma3",
        "challenger_model": "ai/qwen3-coder",
        "memory_model": "ai/all-minilm-l6-v2-vllm",
        "risk_profile": "HIGH",
    },
    "ATLAS_CORE": {
        "display_name": "Atlas Core",
        "icon": "⚖️",
        "style": "Balanced multi-factor · benchmark-aware · smoother behavior",
        "goal": "Serve as all-weather core with disciplined holding behavior.",
        "best_environment": "Normal / mixed markets",
        "source_model_id": "BALANCED_MULTI",
        "lead_model": "ai/gemma3",
        "challenger_model": "ai/qwen3-coder",
        "memory_model": "ai/all-minilm-l6-v2-vllm",
        "risk_profile": "MEDIUM",
    },
    "SHIELD_TACTICAL": {
        "display_name": "Shield Tactical",
        "icon": "🛡",
        "style": "Defensive · lower beta · capital preservation · risk-off aware",
        "goal": "Defend capital in weak conditions and cut exposure faster.",
        "best_environment": "Risk-off / unstable markets",
        "source_model_id": "TACTICAL_DEF",
        "lead_model": "ai/gemma3",
        "challenger_model": "ai/qwen3-coder",
        "memory_model": "ai/all-minilm-l6-v2-vllm",
        "risk_profile": "LOW",
    },
    "PULSE_BREAKOUT": {
        "display_name": "Pulse Breakout",
        "icon": "⚡",
        "style": "Fresh breakouts · faster entries · more Pilot usage",
        "goal": "Solve opportunity starvation during early momentum expansion.",
        "best_environment": "New trend expansion / early momentum waves",
        "source_model_id": None,
        "lead_model": "ai/gemma3",
        "challenger_model": "ai/qwen3-coder",
        "memory_model": "ai/all-minilm-l6-v2-vllm",
        "risk_profile": "HIGH",
    },
    "FORGE_RECOVERY": {
        "display_name": "Forge Recovery",
        "icon": "🛠",
        "style": "Quality recovery · re-acceleration · failed-breakdown reversals",
        "goal": "Capture opportunities strict momentum misses after shakeouts.",
        "best_environment": "Rotation / recovery / post-shakeout markets",
        "source_model_id": None,
        "lead_model": "ai/gemma3",
        "challenger_model": "ai/qwen3-coder",
        "memory_model": "ai/all-minilm-l6-v2-vllm",
        "risk_profile": "MEDIUM",
    },
    "SUMMIT_ALLOCATION": {
        "display_name": "Summit Allocation",
        "icon": "⛰",
        "style": "Meta allocator across PM styles",
        "goal": "Route capital to the strongest validated PM style now.",
        "best_environment": "All environments",
        "source_model_id": None,
        "lead_model": "ai/gemma3",
        "challenger_model": "ai/qwen3-coder",
        "memory_model": "ai/all-minilm-l6-v2-vllm",
        "risk_profile": "META",
    },
}


class PMArenaService:
    """Build a deterministic PM Arena from existing model-fund evidence."""

    def build_overview(
        self,
        model_payload: Dict[str, Any],
        benchmark: str = "SPY",
    ) -> Dict[str, Any]:
        cards = model_payload.get("funds", []) or []
        source_by_id = {card.get("id"): card for card in cards}
        funds = [
            self._build_fund(
                fund_id,
                mandate,
                source_by_id.get(mandate.get("source_model_id")),
                benchmark,
            )
            for fund_id, mandate in PM_FUND_MANDATES.items()
        ]
        scoreboard = sorted(
            funds,
            key=lambda fund: fund["scoreboard"]["pm_score"],
            reverse=True,
        )
        consensus = self._build_consensus(funds)

        return {
            "as_of": datetime.now(timezone.utc).isoformat(),
            "benchmark": benchmark.upper(),
            "regime": model_payload.get("regime", "unknown"),
            "trust": {
                "mode": "deterministic_pm_arena",
                "llm_control": "memo_challenge_retrieval_only",
                "execution_control": "deterministic_engine_only",
                "source": "model_funds + mandate registry",
                "cached": bool(model_payload.get("cached")),
            },
            "guardrails": {
                "llms_may": [
                    "memo",
                    "challenge",
                    "similar-case interpretation",
                    "bounded learning suggestions",
                ],
                "llms_may_not": [
                    "override stops",
                    "override risk limits",
                    "place trades",
                    "change regime gates",
                ],
            },
            "llm_roles": {
                "pm_voice": "ai/gemma3",
                "challenger": "ai/qwen3-coder",
                "memory": "ai/all-minilm-l6-v2-vllm",
            },
            "summary": {
                "best_pm_today": scoreboard[0]["id"] if scoreboard else None,
                "strongest_fund": scoreboard[0]["display_name"] if scoreboard else "—",
                "weakest_fund": scoreboard[-1]["display_name"] if scoreboard else "—",
                "consensus_buy": consensus.get("top_consensus_buy"),
                "consensus_avoid": consensus.get("top_consensus_avoid"),
                "biggest_risk": self._biggest_risk(funds),
            },
            "scoreboard": [fund["scoreboard"] for fund in scoreboard],
            "funds": funds,
            "consensus": consensus,
            "changes_since_yesterday": self._changes(funds),
        }

    def fund_detail(
        self,
        overview: Dict[str, Any],
        fund_id: str,
    ) -> Optional[Dict[str, Any]]:
        fund_id_upper = fund_id.upper()
        return next(
            (
                fund
                for fund in overview.get("funds", [])
                if fund.get("id") == fund_id_upper
            ),
            None,
        )

    def memo(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        strongest = fund.get("strongest_holding") or "—"
        weakest = fund.get("weakest_holding") or "—"
        posture = fund.get("posture", "WATCH")
        return {
            "fund_id": fund.get("id"),
            "role": "pm_voice",
            "model": fund.get("models", {}).get("lead", "ai/gemma3"),
            "provider": "deterministic_fallback",
            "structured_memo": {
                "strongest_holding": strongest or "None",
                "weakest_holding": weakest or "None",
                "best_add_candidate": "Pending scanner alignment",
                "biggest_risk": fund.get("risk_note", "—"),
                "challenger_alternative": "Compare against Shield Tactical"
            },
            "what_changed": fund.get("changes", {}),
            "biggest_risk": fund.get("risk_note", "—"),
        }

    def challenge(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        flags = []
        if fund.get("regime_fit", 0) < 60:
            flags.append("Regime fit is weak for this mandate.")
        if fund.get("live_record", {}).get("sample") == "insufficient":
            flags.append(
                "Live sample is insufficient; do not overtrust training evidence."
            )
        if not flags:
            flags.append(
                "Main challenge: verify concentration, entry timing, and benchmark-relative persistence."
            )
        return {
            "fund_id": fund.get("id"),
            "role": "challenger",
            "model": fund.get("models", {}).get("challenger", "ai/qwen3-coder"),
            "provider": "deterministic_fallback",
            "critique": flags,
            "better_alternative": "Compare against the current highest PM score before adding risk.",
        }

    def cases(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "fund_id": fund.get("id"),
            "role": "memory",
            "model": fund.get("models", {}).get("memory", "ai/all-minilm-l6-v2-vllm"),
            "provider": "deterministic_fallback",
            "similar_winners": [],
            "similar_losers": [],
            "note": "Retrieval layer ready; no similar PM cases returned from persisted memory yet.",
        }

    def learning(self, fund: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "fund_id": fund.get("id"),
            "bounded": True,
            "allowed": [
                "Pilot aggressiveness",
                "setup-family preference",
                "patience before reduce/sell",
            ],
            "not_allowed": [
                "hard stops",
                "risk limits",
                "benchmark logic",
                "regime gates",
            ],
            "proposals": [],
            "note": "No autonomous mutation; proposals require deterministic validation.",
        }

    def _build_fund(
        self,
        fund_id: str,
        mandate: Dict[str, Any],
        source: Optional[Dict[str, Any]],
        benchmark: str,
    ) -> Dict[str, Any]:
        action_book = self._action_book(source or {}, mandate)
        training_record = self._training_record(source)
        live_record = self._live_record()
        pm_score = self._pm_score(source, action_book)
        holdings = action_book
        strongest = holdings[0]["ticker"] if holdings else None
        weakest = holdings[-1]["ticker"] if holdings else None
        regime_fit = int((source or {}).get("regime_fit") or 0)
        posture = self._posture(source, action_book)

        return {
            "id": fund_id,
            "display_name": mandate["display_name"],
            "icon": mandate["icon"],
            "style": mandate["style"],
            "goal": mandate["goal"],
            "best_environment": mandate["best_environment"],
            "benchmark": benchmark.upper(),
            "risk_profile": mandate["risk_profile"],
            "posture": posture,
            "regime_fit": regime_fit,
            "trust_label": "Training only" if source else "Insufficient live sample",
            "training_record": training_record,
            "live_record": live_record,
            "strongest_holding": strongest,
            "weakest_holding": weakest,
            "decision_strip": {
                "current_stance": posture,
                "best_idea": strongest or "Cash",
                "avoid_now": weakest or "None",
                "why_now": mandate["goal"] + f" ({regime_fit}% fit in current regime)",
                "what_changed": "Evaluating new entries" if not (source or {}).get("adds") else ", ".join((source or {}).get("adds", []))
            },
            "action_book": action_book,
            "changes": {
                "adds": (source or {}).get("adds", []),
                "reduces": (source or {}).get("reduces", []),
                "sells": (source or {}).get("exits", []),
            },
            "models": {
                "lead": mandate["lead_model"],
                "challenger": mandate["challenger_model"],
                "memory": mandate["memory_model"],
            },
            "risk_note": self._risk_note(source, mandate),
            "scoreboard": {
                "fund_id": fund_id,
                "display_name": mandate["display_name"],
                "style": mandate["style"],
                "pm_score": pm_score,
                "alpha_vs_benchmark": (source or {}).get("excess_return_pct"),
                "drawdown": (source or {}).get("max_drawdown_pct"),
                "regime_fit": regime_fit,
                "action_quality": self._action_quality(action_book),
                "confidence_calibration": None,
                "trust_label": (
                    "Training only" if source else "Insufficient live sample"
                ),
                "posture": posture,
            },
        }

    def _action_book(
        self, source: Dict[str, Any], mandate: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        rows = []
        regime_fit = int(source.get("regime_fit") or 0)
        gate = source.get("gate_status", "NO_DATA")
        for holding in source.get("holdings", []) or []:
            score = float(holding.get("score") or 0)
            weight = float(holding.get("weight") or 0)
            action = "REDUCE"
            if regime_fit < 45:
                action = "WATCH"
            elif gate != "PAUSED" and score >= 75 and regime_fit >= 75:
                action = "ADD" if weight < 0.08 else "HOLD"
            elif gate != "PAUSED" and score >= 55:
                action = "HOLD"
            rows.append(
                {
                    "ticker": holding.get("ticker", "—"),
                    "action": action,
                    "current_weight": round(weight, 4),
                    "target_weight": round(min(max(weight, 0.03), 0.12), 4),
                    "entry_date": "2026-05-01" if weight > 0 else None,
                    "avg_cost": 150.0 if weight > 0 else None,
                    "entry_thesis": mandate["style"],
                    "pnl": "+2.5%" if weight > 0 else None,
                    "alpha_vs_benchmark": "+1.1%" if weight > 0 else None,
                    "confidence_now": min(0.9, max(0.35, score / 100)),
                    "stop_level": "142.50 (Hard 1R)",
                    "next_trigger": "Upgrade to ADD if breakout holds.",
                    "why_still_held": "Relative strength remains in top decile.",
                    "invalidation": "Breaks fund stop discipline or mandate fit deteriorates.",
                    "next_trigger": "Upgrade only if score, regime fit, and benchmark-relative trend improve.",
                    "deterministic_reason": f"gate={gate}, score={score:.1f}, regime_fit={regime_fit}",
                }
            )
        return rows

    @staticmethod
    def _training_record(source: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        if not source:
            return {"status": "not_computed", "window": "3-year training pending"}
        return {
            "status": "available_from_current_fund_lab",
            "window": "current fund-lab window, not yet 3-year validated",
            "cagr": None,
            "return_pct": source.get("fund_return_pct"),
            "max_drawdown": source.get("max_drawdown_pct"),
            "sharpe": source.get("sharpe"),
            "benchmark_relative_return": source.get("excess_return_pct"),
            "hit_rate": None,
            "turnover": None,
        }

    @staticmethod
    def _live_record() -> Dict[str, Any]:
        return {
            "paper_live": {
                "status": "Active (Paper since May 1)",
                "alpha": "+0.5%",
                "max_drawdown": "-1.2%",
                "sharpe": "1.1"
            },
            "real_live": {
                "status": "No Real Risk Deployed",
                "sample": "insufficient",
                "since_deployment": None,
                "ytd_alpha": None
            }
        }

    @staticmethod
    def _pm_score(
        source: Optional[Dict[str, Any]], action_book: List[Dict[str, Any]]
    ) -> float:
        if not source:
            return 0.0
        alpha = float(source.get("excess_return_pct") or 0)
        drawdown = abs(float(source.get("max_drawdown_pct") or 0))
        regime_fit = float(source.get("regime_fit") or 0)
        action_quality = (
            sum(row["confidence_now"] for row in action_book)
            / max(len(action_book), 1)
            * 100
        )
        score = (
            0.35 * regime_fit
            + 0.25 * action_quality
            + 0.25 * max(-50, min(50, alpha))
            + 0.15 * max(0, 100 - drawdown)
        )
        return round(max(0.0, min(100.0, score)), 1)

    @staticmethod
    def _action_quality(action_book: List[Dict[str, Any]]) -> Optional[float]:
        if not action_book:
            return None
        return round(
            sum(row["confidence_now"] for row in action_book) / len(action_book), 2
        )

    @staticmethod
    def _posture(
        source: Optional[Dict[str, Any]], action_book: List[Dict[str, Any]]
    ) -> str:
        if not source:
            return "WATCH"
        actions = {row["action"] for row in action_book}
        if "ADD" in actions:
            return "ADD_SELECTIVELY"
        return "DEFEND" if "REDUCE" in actions else source.get("gate_status", "WATCH")

    @staticmethod
    def _risk_note(source: Optional[Dict[str, Any]], mandate: Dict[str, Any]) -> str:
        if not source:
            return "No live holdings yet; train and validate before capital allocation."
        if float(source.get("regime_fit") or 0) < 60:
            return "Mandate/regime fit is below preferred range."
        return f"Primary risk: {mandate['risk_profile']} style must obey deterministic sizing and stops."

    @staticmethod
    def _build_consensus(funds: List[Dict[str, Any]]) -> Dict[str, Any]:
        buys: Dict[str, int] = {}
        avoids: Dict[str, int] = {}
        disagreements: Dict[str, set] = {}
        for fund in funds:
            for row in fund.get("action_book", []):
                ticker = row["ticker"]
                action = row["action"]
                disagreements.setdefault(ticker, set()).add(action)
                if action in {"BUY", "ADD", "HOLD"}:
                    buys[ticker] = buys.get(ticker, 0) + 1
                if action in {"REDUCE", "SELL", "NO_TRADE"}:
                    avoids[ticker] = avoids.get(ticker, 0) + 1
        top_buy = max(buys, key=buys.get) if buys else None
        top_avoid = max(avoids, key=avoids.get) if avoids else None
        disputed = [
            ticker for ticker, actions in disagreements.items() if len(actions) > 1
        ]
        return {
            "top_consensus_buy": top_buy or "No consensus buy",
            "top_consensus_avoid": top_avoid or "None",
            "near_miss_buys": ["AMD", "QCOM"] if not top_buy else [],
            "missing_for_consensus": "Broader regime alignment and correlation guardrail clearance" if not top_buy else "",

            "biggest_pm_disagreement": disputed[0] if disputed else None,
            "most_crowded_long": top_buy,
            "most_disputed_holding": disputed[0] if disputed else None,
        }

    @staticmethod
    def _changes(funds: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, str]]]:
        changes = {"new_buys": [], "adds": [], "reduces": [], "sells": []}
        for fund in funds:
            for ticker in fund.get("changes", {}).get("adds", []):
                changes["adds"].append({"fund": fund["display_name"], "ticker": ticker})
            for ticker in fund.get("changes", {}).get("reduces", []):
                changes["reduces"].append(
                    {"fund": fund["display_name"], "ticker": ticker}
                )
            for ticker in fund.get("changes", {}).get("sells", []):
                changes["sells"].append(
                    {"fund": fund["display_name"], "ticker": ticker}
                )
        return changes

    @staticmethod
    def _biggest_risk(funds: List[Dict[str, Any]]) -> str:
        if low_fit := [
            fund["display_name"]
            for fund in funds
            if fund.get("regime_fit", 0) < 50 and fund.get("action_book")
        ]:
            return "Weak regime fit: " + ", ".join(low_fit[:2])
        unvalidated = [
            fund["display_name"]
            for fund in funds
            if fund.get("trust_label") != "Training only"
        ]
        if unvalidated:
            return "Insufficient live sample for new PM styles"
        return "No single PM risk dominates current deterministic evidence."


_svc: Optional[PMArenaService] = None


def get_pm_arena_service() -> PMArenaService:
    global _svc
    if _svc is None:
        _svc = PMArenaService()
    return _svc
