"""PM memo generator — one-page summary for portfolio / ticker / sleeve."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def generate_pm_memo(
    *,
    scope: str,
    ticker: Optional[str] = None,
    portfolio_decision: Optional[Dict[str, Any]] = None,
    today: Optional[Dict[str, Any]] = None,
    stock_intel: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Structured PM memo (markdown sections + bullets)."""
    sections: List[Dict[str, str]] = []
    scope_u = (scope or "portfolio").lower()

    if scope_u == "ticker" and stock_intel:
        pm = stock_intel.get("pm_answer") or {}
        sm = stock_intel.get("smart_money") or {}
        sections.append(
            {
                "title": "Summary",
                "body": pm.get("one_line") or f"{ticker} — {pm.get('action_now', 'WAIT')}",
            }
        )
        bull = pm.get("bull_case") or []
        bear = pm.get("bear_case") or []
        if bull:
            sections.append({"title": "Bull case", "body": " · ".join(bull) if isinstance(bull, list) else str(bull)})
        if bear:
            sections.append({"title": "Bear case", "body": " · ".join(bear) if isinstance(bear, list) else str(bear)})
        sections.append(
            {
                "title": "Smart money (supporting only)",
                "body": sm.get("usefulness") or sm.get("summary_headline", ""),
            }
        )
        sections.append(
            {
                "title": "Action",
                "body": f"{pm.get('action_now')} · Setup: {pm.get('best_setup_type')} · {pm.get('investor_fit')}",
            }
        )
    elif portfolio_decision:
        alloc = portfolio_decision.get("allocator_summary") or {}
        why = portfolio_decision.get("why_now") or {}
        sections.append(
            {
                "title": "Portfolio stance",
                "body": f"{alloc.get('stance')} — {alloc.get('recommended_action')}",
            }
        )
        sections.append(
            {
                "title": "Benchmark",
                "body": f"Verdict: {alloc.get('benchmark_relative_verdict')} · Evidence: {alloc.get('evidence_quality')}",
            }
        )
        if why.get("watch_next"):
            sections.append(
                {
                    "title": "Watch next",
                    "body": " · ".join(why.get("watch_next") or []),
                }
            )
        attr = portfolio_decision.get("return_attribution") or {}
        top = attr.get("top_contributor")
        if top:
            sections.append(
                {
                    "title": "Top contributor",
                    "body": f"{top.get('asset')} {top.get('contribution_pct')}%",
                }
            )
    elif today:
        ba = today.get("best_action") or {}
        sections.append(
            {
                "title": "Today",
                "body": ba.get("stance_one_liner") or today.get("narrative", ""),
            }
        )
        avoid = today.get("avoid_now") or today.get("avoid") or []
        if avoid:
            lines = []
            for a in avoid[:5]:
                if isinstance(a, dict):
                    lines.append(f"{a.get('ticker')}: {a.get('reason')}")
                else:
                    lines.append(str(a))
            sections.append({"title": "Avoid", "body": " · ".join(lines)})

    markdown = "\n\n".join(f"## {s['title']}\n{s['body']}" for s in sections if s.get("body"))
    return {
        "scope": scope_u,
        "ticker": ticker,
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "sections": sections,
        "markdown": markdown,
        "one_liner": sections[0]["body"] if sections else "No memo data — load portfolio or dossier first",
    }
