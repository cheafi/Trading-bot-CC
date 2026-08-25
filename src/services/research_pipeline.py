"""One-click research pipeline — stops at watch rule / Playbook review."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.services.reports_library import create_report_from_validation
from src.services.research_committee import run_committee_review
from src.services.research_safety import pipeline_step_labels, sanitize_research_payload
from src.services.research_store import (
    save_backtest_run,
    save_memory_item,
    save_strategy_draft,
)
from src.services.strategy_builder import (
    build_strategy_draft_record,
    strategy_draft_to_watch_intent,
)
from src.services.validation_lab import run_validation
from src.services.vibe_agent import parse_vibe_intent, persist_intent_and_rules


def run_research_pipeline(
    *,
    prompt: str,
    system_state: Optional[Dict[str, Any]] = None,
    backtest_metrics: Optional[Dict[str, Any]] = None,
    steps: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Natural language → draft → validate → watch rule proposal → memory."""
    ss = system_state or {}
    data_quality = str(ss.get("data_freshness") or "FRESH")
    wanted = steps or ["draft", "validate", "watch_rule", "memory", "committee"]
    result: Dict[str, Any] = {
        "stepsCompleted": [],
        "pipeline": pipeline_step_labels(),
        "stoppedAt": None,
        "authority_notice": [
            "Pipeline stops at watch rule / Playbook review",
            "No live execution",
        ],
    }

    draft = None
    validation = None
    watch = None
    committee = None

    if "draft" in wanted:
        draft = build_strategy_draft_record(prompt)
        draft = save_strategy_draft(draft)
        result["strategyDraft"] = draft
        result["stepsCompleted"].append("draft")

    if "validate" in wanted and draft:
        validation = run_validation(
            strategy_draft=draft,
            backtest_metrics=backtest_metrics or {},
            data_quality=data_quality,
            system_state=ss,
        )
        run_row = save_backtest_run(
            {
                "strategyDraftId": draft["id"],
                "dataSource": validation.get("dataSource"),
                "period": validation.get("period"),
                "benchmark": validation.get("benchmark"),
                "metrics": validation.get("metrics"),
                "warnings": validation.get("warnings"),
                "walkForward": validation.get("walkForward"),
                "monteCarlo": validation.get("monteCarlo"),
                "bootstrap": validation.get("bootstrap"),
                "verdict": validation.get("verdict"),
            }
        )
        validation["id"] = run_row["id"]
        report = create_report_from_validation(
            validation, strategy_draft=draft, authority_state=ss
        )
        result["validation"] = validation
        result["report"] = report
        result["stepsCompleted"].append("validate")

    if "watch_rule" in wanted and draft:
        intent_text = strategy_draft_to_watch_intent(draft)
        plan = parse_vibe_intent(intent_text)
        if validation and validation.get("verdict") == "Research pass":
            watch = persist_intent_and_rules(intent_text)
            result["watchRule"] = watch
            result["stepsCompleted"].append("watch_rule")
        else:
            result["watchRuleProposal"] = plan
            result["stoppedAt"] = "watch_rule_pending_validation"
            result["stepsCompleted"].append("watch_rule_proposed_only")

    if "committee" in wanted and draft:
        committee = run_committee_review(subject=draft, system_state=ss)
        result["committee"] = committee
        result["stepsCompleted"].append("committee")

    if "memory" in wanted:
        mem = save_memory_item(
            {
                "type": "pipeline_run",
                "summary": prompt[:200],
                "evidence": [s for s in result["stepsCompleted"]],
                "linkedRuns": [
                    x
                    for x in [
                        draft.get("id") if draft else None,
                        validation.get("id") if validation else None,
                    ]
                    if x
                ],
                "confidence": validation.get("verdict") if validation else "draft",
                "expiry": draft.get("expiry") if draft else None,
            }
        )
        result["memoryItem"] = mem
        result["stepsCompleted"].append("memory")

    result["nextActions"] = [
        "Run validation" if not validation else "Review validation report",
        "Open Playbook for watch-qualified",
        "Open Dossier for structure",
    ]
    return sanitize_research_payload(result)
