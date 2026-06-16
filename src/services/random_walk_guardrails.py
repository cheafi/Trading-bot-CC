"""Random-walk guardrails for dossier surfaces.

Minimal heuristic implementation that keeps dossier aggregation alive and
produces the fields the UI expects. The goal is operator-safe humility, not
precision forecasting.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _clamp_0_100(value: Any, default: int = 50) -> int:
    try:
        return max(0, min(100, int(round(float(value)))))
    except Exception:
        return default


def _level_from_score(score: int, *, low: int = 35, high: int = 70) -> str:
    if score >= high:
        return "high"
    if score <= low:
        return "low"
    return "medium"


def _data_completeness(layers: Dict[str, Any], module_errors: Dict[str, Any]) -> Dict[str, Any]:
    layer_count = len(layers or {})
    available = sum(1 for v in (layers or {}).values() if bool(v))
    ratio = (available / layer_count) if layer_count else 0.0
    score = int(round(ratio * 100))
    missing = sorted(str(k) for k, v in (module_errors or {}).items() if v)
    label = "high" if score >= 80 else "medium" if score >= 50 else "low"
    return {
        "score": score,
        "label": label,
        "summary": (
            f"{available}/{layer_count or 0} evidence layers available"
            + (f" · missing {', '.join(missing[:3])}" if missing else "")
        ),
    }


def build_random_walk_guardrails(
    *,
    ticker: str,
    dossier: Dict[str, Any],
    unified: Dict[str, Any],
    timing: Dict[str, Any],
    confluence: Dict[str, Any],
    portfolio_fit: Dict[str, Any],
    options_block: Dict[str, Any],
    smart_money: Dict[str, Any],
    confidence_metrics: Dict[str, Any],
    conf_display: Dict[str, Any],
    layers: Dict[str, Any],
    module_errors: Dict[str, Any],
    narrative: Dict[str, Any],
    peers_block: Dict[str, Any],
    regime_ok: bool,
) -> Dict[str, Any]:
    thesis_quality = _clamp_0_100(confidence_metrics.get("thesis_quality"), default=55)
    timing_quality = _clamp_0_100(confidence_metrics.get("timing_quality"), default=50)
    rr_quality = _clamp_0_100(confidence_metrics.get("rr_quality"), default=50)
    predictive_confidence = _clamp_0_100(conf_display.get("predictive_confidence"), default=50)
    evidence = _data_completeness(layers or {}, module_errors or {})
    net_edge = unified.get("net_deploy_score")
    try:
        net_edge_num = round(float(net_edge), 1)
    except Exception:
        net_edge_num = None

    extended = bool(timing.get("extended"))
    timing_weak = bool(timing.get("timing_weak"))
    partial = bool(dossier.get("_partial")) or bool(module_errors)
    options_live = bool(options_block.get("has_data"))
    peer_count = len(peers_block.get("rows") or [])
    portfolio_score = _clamp_0_100((portfolio_fit or {}).get("score"), default=55)
    confluence_score = _clamp_0_100((confluence or {}).get("score"), default=50)

    efficiency_score = max(
        0,
        min(
            100,
            100
            - abs(thesis_quality - predictive_confidence)
            - (12 if partial else 0)
            - (10 if timing_weak else 0),
        ),
    )
    bubble_score = min(
        100,
        20
        + (25 if extended else 0)
        + (15 if options_live else 0)
        + (10 if confluence_score >= 70 else 0),
    )
    cost_realism_score = max(
        0,
        min(
            100,
            70
            - (15 if extended else 0)
            - (10 if partial else 0)
            + (10 if net_edge_num is not None and net_edge_num >= 6.0 else -10),
        ),
    )
    portfolio_need_score = max(
        0,
        min(
            100,
            portfolio_score
            + (10 if regime_ok else -10)
            + (5 if peer_count >= 3 else 0),
        ),
    )

    guardrail_labels: List[str] = []
    if partial:
        guardrail_labels.append("Partial data")
    if extended:
        guardrail_labels.append("Extended timing")
    if not regime_ok:
        guardrail_labels.append("Regime blocked")
    if net_edge_num is not None and net_edge_num < 6.0:
        guardrail_labels.append("Weak net edge")
    if bubble_score >= 70:
        guardrail_labels.append("Crowding risk")
    if not guardrail_labels:
        guardrail_labels.append("Evidence stack intact")

    return {
        "ticker": str(ticker or "").upper(),
        "guardrail_labels": guardrail_labels[:5],
        "evidence_strength": evidence["label"],
        "predictive_confidence": predictive_confidence,
        "data_completeness": evidence["label"],
        "cost_adjusted_expected_edge": net_edge_num,
        "market_efficiency_warning": {
            "level": _level_from_score(efficiency_score, low=40, high=75),
            "score": efficiency_score,
            "summary": (
                "Evidence still looks heuristic; do not assume persistent edge."
                if efficiency_score < 50
                else "Edge may exist, but only as a fragile, non-stationary setup."
            ),
        },
        "bubble_crowding_risk": {
            "level": _level_from_score(bubble_score, low=30, high=70),
            "score": bubble_score,
            "summary": (
                "Crowding / chase risk elevated; promotion still needs board + broker confirmation."
                if bubble_score >= 70
                else "Crowding risk not dominant, but still not a deploy permission."
            ),
        },
        "cost_realism": {
            "level": _level_from_score(cost_realism_score, low=35, high=70),
            "score": cost_realism_score,
            "summary": (
                f"Net edge {net_edge_num:.1f} after cost drag."
                if net_edge_num is not None
                else "Cost-adjusted edge unavailable; treat as research-only."
            ),
        },
        "portfolio_necessity": {
            "level": _level_from_score(portfolio_need_score, low=35, high=70),
            "score": portfolio_need_score,
            "summary": (
                "Portfolio fit is acceptable."
                if portfolio_need_score >= 70
                else "Portfolio need is not strong enough to override current blockers."
            ),
        },
        "operator_verdict": {
            "summary": (
                "Research-only until board, broker, execution, and live data all align."
            )
        },
        "meta": {
            "thesis_quality": thesis_quality,
            "timing_quality": timing_quality,
            "rr_quality": rr_quality,
            "confluence_score": confluence_score,
            "options_live": options_live,
            "smart_money_present": bool(smart_money),
            "narrative_present": bool(narrative),
        },
    }
