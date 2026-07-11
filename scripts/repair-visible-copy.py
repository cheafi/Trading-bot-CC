#!/usr/bin/env python3
"""Repair known UTF-8 / emoji corruption in CC index.html visible copy."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "src/api/templates/index.html"


def repair_index(text: str) -> tuple[str, int]:
    original = text
    fixes = 0

    replacements = [
        (
            "'Dashboard ? Playbook ? Discovery ? Dossier ? Portfolio / IBKR. Export is monitor-only ? not trade authority.'",
            "'Dashboard → Playbook → Discovery → Dossier → Portfolio / IBKR. Export is monitor-only — not trade authority.'",
        ),
        (">? Ops Console<", ">⚙ Ops Console<"),
        ("Strategy Lab ? research-only", "Strategy Lab — research-only"),
        ("More ? Strategy Lab", "More → Strategy Lab"),
        ("'2?45+'", "'2–45+'"),
        ("<!-- Agent ? default monitor copilot", "<!-- Agent — default monitor copilot"),
        ("<!-- Board-level gate comment (Playbook) ? collapsed", "<!-- Board-level gate comment (Playbook) — collapsed"),
        ("<!-- Best Action Now (Playbook) ? shown", "<!-- Best Action Now (Playbook) — shown"),
        ("<!-- Deploy unlock conditions ? collapsed", "<!-- Deploy unlock conditions — collapsed"),
        ("<!-- Near-miss board ? consolidated", "<!-- Near-miss board — consolidated"),
        ("<!-- Ranked Cards ? single primary", "<!-- Ranked Cards — single primary"),
        ("<!-- Strategy Health ? collapsed", "<!-- Strategy Health — collapsed"),
        (" ? trusted?<span", " · trusted n=<span"),
        (" ? Calibrated ? n=", " · Calibrated · n="),
        (" ? ECE=", " · ECE="),
        ("'discoveryRowLabel('action')+' ? '+(h.urgency", "'discoveryRowLabel('action')+' · '+(h.urgency"),
        ("'weight_pct+'% ? '+r.reason", "'weight_pct+'% · '+r.reason"),
        ("'Stock '+panel.summary.total_return.stock+'% ? SPY '+panel.summary.total_return.spy+'% ? ? '+panel.summary.total_return.alpha+'%'",
         "'Stock '+panel.summary.total_return.stock+'% · SPY '+panel.summary.total_return.spy+'% · α '+panel.summary.total_return.alpha+'%'"),
        ("'detected||'?')+' ? '+(dos.intel.candlestick_analysis", "'detected||'—')+' · '+(dos.intel.candlestick_analysis"),
    ]

    for old, new in replacements:
        if old in text:
            text = text.replace(old, new)
            fixes += 1

    prefix_map = [
        ("x-text=\"'? '+h.risk_note", "x-text=\"'⚠ '+h.risk_note"),
        ("x-text=\"'? '+(h.next_action", "x-text=\"'→ '+(h.next_action"),
        ("x-text=\"'? '+h.next_action", "x-text=\"'→ '+h.next_action"),
        ("x-text=\"'? '+r.invalidation", "x-text=\"'✕ '+r.invalidation"),
        ("x-text=\"'? '+ra", "x-text=\"'✗ '+ra"),
        ("x-text=\"'? '+pm", "x-text=\"'⚠ '+pm"),
        ("x-text=\"'? '+r.why_wait", "x-text=\"'⏳ '+r.why_wait"),
        ("x-text=\"'? '+(Array.isArray(r.why_now)", "x-text=\"'✓ '+(Array.isArray(r.why_now)"),
        ("x-text=\"'? '+(nm.upgrade_trigger", "x-text=\"'→ '+(nm.upgrade_trigger"),
        ("x-text=\"'? '+rankedOpps.overlapWarning", "x-text=\"'⚠ '+rankedOpps.overlapWarning"),
        ("x-text=\"'? '+scannerHub.error", "x-text=\"'⚠ '+scannerHub.error"),
        ("x-text=\"'? '+scannerHub.data.diagnostics.reason_no_hits", "x-text=\"'ℹ '+scannerHub.data.diagnostics.reason_no_hits"),
        ("x-text=\"'? '+b\"", "x-text=\"'• '+b\""),
        ("x-text=\"'? '+w\"", "x-text=\"'• '+w\""),
        ("x-text=\"'? '+t\"", "x-text=\"'• '+t\""),
        ("x-text=\"'? '+u\"", "x-text=\"'• '+u\""),
        ("x-text=\"'? '+kf\"", "x-text=\"'• '+kf\""),
        ("x-text=\"'? '+ku\"", "x-text=\"'• '+ku\""),
        ("x-text=\"'? '+imp\"", "x-text=\"'• '+imp\""),
        ("x-text=\"'? '+det\"", "x-text=\"'• '+det\""),
        ("x-text=\"'? '+na\"", "x-text=\"'• '+na\""),
        ("x-text=\"'? '+(r.conflict_level", "x-text=\"'⚖ '+(r.conflict_level"),
        ("x-text=\"'? '+(Math.round((r.data_freshness_minutes", "x-text=\"'⏱ '+(Math.round((r.data_freshness_minutes"),
        ("x-text=\"'? '+(sig.mode||'?')", "x-text=\"'● '+(sig.mode||'—')"),
        ("x-text=\"'? '+pfBrokerSource().pill", "x-text=\"'● '+pfBrokerSource().pill"),
        ("x-text=\"'? '+(dos.data&&dos.data.trust", "x-text=\"'● '+(dos.data&&dos.data.trust"),
        ("x-text=\"'? '+pfDecision.return_attribution.top_contributor", "x-text=\"'↑ '+pfDecision.return_attribution.top_contributor"),
        ("x-text=\"'? '+pfDecision.return_attribution.top_detractor", "x-text=\"'↓ '+pfDecision.return_attribution.top_detractor"),
        ("x-text=\"'? '+pfEquity.active_return_pct", "x-text=\"'↔ '+pfEquity.active_return_pct"),
        ("x-text=\"'? '+(r.recommended_action", "x-text=\"'→ '+(r.recommended_action"),
    ]

    for old, new in prefix_map:
        if old in text:
            count = text.count(old)
            text = text.replace(old, new)
            fixes += count

    # Generic remaining Alpine visible prefixes in x-text only
    def _fix_generic(m: re.Match[str]) -> str:
        nonlocal fixes
        fixes += 1
        return m.group(1) + "'• '+" + m.group(2)

    text, n = re.subn(
        r"(x-text=\")'\\? '\\+(\\w)",
        _fix_generic,
        text,
    )
    fixes += n

    return text, fixes if text != original else 0


def main() -> int:
    if not INDEX.exists():
        print(f"missing {INDEX}", file=sys.stderr)
        return 1
    raw = INDEX.read_text(encoding="utf-8")
    repaired, count = repair_index(raw)
    if count:
        INDEX.write_text(repaired, encoding="utf-8")
        print(f"repaired {count} visible-copy issue(s) in index.html")
    else:
        print("no repairs needed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
