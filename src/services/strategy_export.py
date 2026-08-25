"""Strategy export — Pine / JSON / pseudo-code with research disclaimers."""

from __future__ import annotations

import json
from typing import Any, Dict, List

from src.services.research_safety import PINE_DISCLAIMER, sanitize_research_payload


def export_pine_draft(
    *,
    name: str = "CC_Research_Draft",
    entry_rules: List[str] | None = None,
    exit_rules: List[str] | None = None,
    regime_filters: List[str] | None = None,
) -> str:
    """Pine Script v6 research draft — no live broker hooks."""
    entry = entry_rules or ["// define entry"]
    exit_r = exit_rules or ["// define exit"]
    regime = regime_filters or []
    lines = [
        PINE_DISCLAIMER.strip(),
        "// @version=6",
        f'indicator("{name}", overlay=true)',
        "",
        "// --- Entry logic (research draft) ---",
    ]
    for i, rule in enumerate(entry):
        lines.append(f"// Entry {i + 1}: {rule}")
    lines.append("longCondition = false  // TODO: map validated rules")
    lines.append("")
    lines.append("// --- Exit logic ---")
    for i, rule in enumerate(exit_r):
        lines.append(f"// Exit {i + 1}: {rule}")
    lines.append("exitCondition = false")
    lines.append("")
    if regime:
        lines.append("// --- Regime filters ---")
        for r in regime:
            lines.append(f"// Filter: {r}")
    lines.extend(
        [
            "",
            "// NO strategy.order calls in research export — validate in CC Strategy Lab",
            "plotshape(longCondition, title='Research signal', style=shape.triangleup, location=location.belowbar, color=color.new(color.green, 0))",
        ]
    )
    return "\n".join(lines) + "\n"


def export_strategy_contract_json(draft: Dict[str, Any]) -> str:
    contract = sanitize_research_payload(
        {
            "version": "cc-strategy-contract-1",
            "action": "research_only",
            "authority_effect": "none",
            "universe": draft.get("universe"),
            "timeframe": draft.get("timeframe"),
            "entryRules": draft.get("entryRules"),
            "exitRules": draft.get("exitRules"),
            "riskRules": draft.get("riskRules"),
            "regimeFilters": draft.get("regimeFilters"),
            "invalidation": draft.get("invalidation"),
            "disclaimer": "Research draft — not deploy authority",
        }
    )
    return json.dumps(contract, ensure_ascii=False, indent=2)


def export_python_pseudo(draft: Dict[str, Any]) -> str:
    header = (
        '"""CC research strategy pseudo-code — NOT for live execution."""\n\n'
        "def on_bar(ctx):\n"
        "    # Research only — confirm in Playbook before any sizing\n"
    )
    body = []
    for rule in draft.get("entryRules") or []:
        body.append(f"    # entry: {rule}")
    body.append("    return {'signal': None, 'authority': 'research_only'}")
    return header + "\n".join(body) + "\n"


def export_watch_rules_csv(rules: List[Dict[str, Any]]) -> str:
    lines = ["asset,ruleType,condition,action,authorityEffect,expiry"]
    for r in rules:
        lines.append(
            ",".join(
                [
                    str(r.get("asset") or ""),
                    str(r.get("ruleType") or ""),
                    '"' + str(r.get("condition") or "").replace('"', "'") + '"',
                    "alert_only",
                    "none",
                    str(r.get("expiry") or ""),
                ]
            )
        )
    return "\n".join(lines) + "\n"
