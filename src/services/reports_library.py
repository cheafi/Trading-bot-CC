"""Reports library — inspectable runs with export (no deploy)."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from src.services.research_safety import PINE_DISCLAIMER, sanitize_research_payload
from src.services.research_store import get_report, list_reports, save_report
from src.services.strategy_export import export_pine_draft


def create_report_from_validation(
    validation: Dict[str, Any],
    *,
    strategy_draft: Optional[Dict[str, Any]] = None,
    authority_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    report = sanitize_research_payload(
        {
            "type": "validation",
            "linkedRunId": validation.get("id"),
            "strategyDraftId": validation.get("strategyDraftId"),
            "summary": f"Validation: {validation.get('verdict')}",
            "metrics": validation.get("metrics"),
            "warnings": validation.get("warnings"),
            "assumptions": ["Historical simulation", "No fees/slippage unless noted"],
            "dataSources": [validation.get("dataSource") or "backtest_lab"],
            "authorityStateSnapshot": authority_state or {},
            "exportFormats": ["markdown", "json", "html"],
            "body": validation,
        }
    )
    return save_report(report)


def create_report_from_shadow(shadow: Dict[str, Any], *, authority_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    report = sanitize_research_payload(
        {
            "type": "shadow_account",
            "linkedRunId": shadow.get("id"),
            "summary": f"Shadow: Δ P&L {shadow.get('pnlDifference')}",
            "behaviorTags": shadow.get("behaviorTags"),
            "lessons": shadow.get("lessons"),
            "authorityStateSnapshot": authority_state or {},
            "exportFormats": ["markdown", "json", "html"],
            "body": shadow,
        }
    )
    return save_report(report)


def export_report(report_id: str, fmt: str = "markdown") -> str:
    report = get_report(report_id)
    if not report:
        return ""
    fmt = str(fmt or "markdown").lower()
    if fmt == "json":
        return json.dumps(sanitize_research_payload(report), ensure_ascii=False, indent=2)
    if fmt == "html":
        return _report_html(report)
    if fmt == "pine":
        body = report.get("body") or {}
        draft = body if body.get("entryRules") else {}
        return export_pine_draft(
            name="CC_Report_Export",
            entry_rules=draft.get("entryRules") or ["// see report"],
            exit_rules=draft.get("exitRules") or [],
        )
    return _report_markdown(report)


def _report_markdown(report: Dict[str, Any]) -> str:
    lines = [
        "# CC Research Report",
        "",
        f"**Type:** {report.get('type')}",
        f"**Created:** {report.get('createdAt', '')[:19]}",
        "",
        "> Research / Monitoring only · 非部署權限 · No deploy authority",
        "",
        f"## Summary",
        str(report.get("summary") or ""),
        "",
    ]
    if report.get("warnings"):
        lines.append("## Warnings")
        for w in report["warnings"]:
            lines.append(f"- {w}")
        lines.append("")
    if report.get("lessons"):
        lines.append("## Lessons")
        for lesson in report["lessons"]:
            lines.append(f"- {lesson}")
        lines.append("")
    lines.append("---")
    lines.append("*Backtest pass ≠ live trade permission*")
    return "\n".join(lines)


def _report_html(report: Dict[str, Any]) -> str:
    md = _report_markdown(report)
    escaped = md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>CC Report</title></head><body><pre>{escaped}</pre></body></html>"
