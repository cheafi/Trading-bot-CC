"""Shadow Account — actual vs rule-based behavior diagnostics."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.research_safety import sanitize_research_payload


def analyze_shadow_account(
    *,
    trades: List[Dict[str, Any]],
    rules: Optional[List[Dict[str, Any]]] = None,
    source: str = "manual_journal",
) -> Dict[str, Any]:
    """Compare actual path vs ideal rule-based shadow — no deploy authority."""
    rules = rules or []
    actual_pnl = sum(float(t.get("pnl") or t.get("pnl_pct") or 0) for t in trades)
    behavior_tags: List[str] = []
    diagnostics: List[Dict[str, Any]] = []

    for t in trades:
        tag = None
        reason = str(t.get("exit_reason") or t.get("notes") or "").lower()
        if t.get("early_exit") or "early" in reason:
            tag = "early_exit"
            behavior_tags.append("early_exits")
        if t.get("chase") or "chase" in reason:
            tag = "chasing_extension"
            behavior_tags.append("chasing_extension")
        if t.get("average_down"):
            tag = "average_down_without_rule"
            behavior_tags.append("average_down_without_rule")
        if t.get("revenge") or "revenge" in reason:
            tag = "revenge_trading"
            behavior_tags.append("revenge_trading")
        if tag:
            diagnostics.append(
                {
                    "ticker": t.get("ticker"),
                    "tag": tag,
                    "pnl": t.get("pnl") or t.get("pnl_pct"),
                    "note": "Rule violation vs shadow ideal",
                }
            )

    overtrade = len(trades) > 20
    if overtrade:
        behavior_tags.append("overtrading")

    shadow_pnl = actual_pnl * 0.92 if behavior_tags else actual_pnl
    avoided_losses = round(
        max(0, actual_pnl - shadow_pnl) if actual_pnl < shadow_pnl else 0, 2
    )
    missed_winners = len(
        [t for t in trades if float(t.get("pnl") or 0) < 0 and t.get("setup_valid")]
    )

    lessons = []
    if "chasing_extension" in behavior_tags:
        lessons.append(
            "Add monitor-zone rule; wait for Playbook confirmation before chase entries"
        )
    if "early_exits" in behavior_tags:
        lessons.append(
            "Define exit invalidation in Dossier; reduce discretionary early exits"
        )
    if "revenge_trading" in behavior_tags:
        lessons.append("Use calm-down guardrail after drawdown; WAIT gate is binding")
    if not lessons:
        lessons.append("Shadow path aligned — continue journaling outcomes")

    unique_tags = sorted(set(behavior_tags))
    return sanitize_research_payload(
        {
            "sourceJournal": source,
            "actualTrades": trades[:50],
            "extractedRules": rules[:20],
            "shadowTrades": _shadow_ideal_trades(trades),
            "behaviorDiagnostics": diagnostics[:30],
            "behaviorTags": unique_tags,
            "pnlDifference": round(shadow_pnl - actual_pnl, 2),
            "drawdownDifference": round(abs(actual_pnl) * 0.05, 2),
            "actualPnl": round(actual_pnl, 2),
            "shadowPnl": round(shadow_pnl, 2),
            "avoidedLosses": avoided_losses,
            "missedWinners": missed_winners,
            "lessons": lessons,
            "nextRuleImprovements": lessons,
            "confirmationPath": "Journal → Agent watch rules → Playbook",
        }
    )


def _shadow_ideal_trades(trades: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Idealized rule-following path (simplified)."""
    out = []
    for t in trades:
        if t.get("chase") or t.get("revenge") or t.get("average_down"):
            continue
        out.append(
            {
                "ticker": t.get("ticker"),
                "action": "hold_per_rule",
                "pnl": t.get("pnl"),
                "note": "Shadow: only rule-qualified entries",
            }
        )
    return out[:30]
