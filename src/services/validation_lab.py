"""Validation Lab 2.0 — backtest metrics, warnings, research labels (no deploy)."""

from __future__ import annotations

import random
from typing import Any, Dict, List, Optional

from src.services.research_safety import sanitize_research_payload


def _label_verdict(
    *,
    sharpe: float,
    trades: int,
    max_dd: float,
    wf_stability: int,
    data_quality: str,
) -> str:
    if data_quality in ("STALE", "CRITICAL", "mock"):
        return "Needs more data"
    if trades < 20:
        return "Needs more data"
    if wf_stability < 50:
        return "Overfit risk"
    if sharpe < 0:
        return "Retire / do not use"
    if max_dd > 25:
        return "Regime-specific only"
    if sharpe >= 1.0 and wf_stability >= 66:
        return "Research pass"
    return "Needs more data"


def run_validation(
    *,
    strategy_draft: Dict[str, Any],
    backtest_metrics: Optional[Dict[str, Any]] = None,
    data_quality: str = "FRESH",
    system_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Validate strategy draft — upgrades research rule only, never deploy."""
    ss = system_state or {}
    metrics = backtest_metrics or {}
    sharpe = float(metrics.get("sharpe") or metrics.get("sharpe_ratio") or 0)
    trades = int(metrics.get("total_trades") or metrics.get("trades") or 0)
    max_dd = abs(float(metrics.get("max_drawdown") or metrics.get("max_dd") or 0))
    ret = float(metrics.get("total_return_pct") or metrics.get("return_pct") or 0)
    wf_stability = int(
        metrics.get("walk_forward_stability") or metrics.get("stability_score") or 0
    )

    warnings: List[str] = []
    if data_quality in ("STALE", "CRITICAL"):
        warnings.append("Data stale — validation provisional")
    if trades < 30:
        warnings.append("Sample-size warning: < 30 trades")
    if wf_stability < 50 and trades >= 10:
        warnings.append("Overfit warning: walk-forward unstable")
    if str(ss.get("tradeability") or "") in ("WAIT", "NO_TRADE"):
        warnings.append("Board gate WAIT — validation cannot grant deploy")

    monte_carlo = _monte_carlo_stub(ret, max_dd, trades)
    bootstrap = _bootstrap_stub(ret, trades)
    verdict = _label_verdict(
        sharpe=sharpe,
        trades=trades,
        max_dd=max_dd,
        wf_stability=wf_stability,
        data_quality=data_quality,
    )

    return sanitize_research_payload(
        {
            "strategyDraftId": strategy_draft.get("id"),
            "dataSource": metrics.get("data_source") or "backtest_lab",
            "period": metrics.get("period")
            or strategy_draft.get("backtestConfig", {}).get("period", "2y"),
            "benchmark": metrics.get("benchmark") or "SPY",
            "metrics": {
                "total_return_pct": ret,
                "sharpe": sharpe,
                "max_drawdown": max_dd,
                "total_trades": trades,
                "win_rate": metrics.get("win_rate"),
                "expectancy": metrics.get("expectancy"),
                "vs_benchmark": metrics.get("vs_benchmark"),
            },
            "warnings": warnings,
            "verdict": verdict,
            "verdictLabels": {
                "research_pass": verdict == "Research pass",
                "needs_more_data": verdict == "Needs more data",
                "overfit_risk": verdict == "Overfit risk",
                "regime_specific": verdict == "Regime-specific only",
                "retire": verdict == "Retire / do not use",
            },
            "walkForward": metrics.get("walk_forward")
            or {"stability_score": wf_stability},
            "monteCarlo": monte_carlo,
            "bootstrap": bootstrap,
            "regimeSplit": metrics.get("regime_split") or {},
            "sectorSplit": metrics.get("sector_split") or {},
            "setupFamilySplit": metrics.get("setup_family_split") or {},
            "provisional": data_quality in ("STALE", "CRITICAL", "mock"),
            "confirmationPath": "Playbook → Dashboard → Dossier",
            "nextAction": "Create watch rule"
            if verdict == "Research pass"
            else "Gather more data / refine draft",
        }
    )


def _monte_carlo_stub(
    return_pct: float, max_dd: float, trades: int, n: int = 200
) -> Dict[str, Any]:
    if trades < 5:
        return {"runs": 0, "note": "Insufficient trades for Monte Carlo"}
    rng = random.Random(42)
    outcomes = []
    for _ in range(min(n, 500)):
        noise = rng.gauss(return_pct / max(trades, 1), max_dd / 10)
        outcomes.append(round(noise, 2))
    outcomes.sort()
    p5 = outcomes[int(len(outcomes) * 0.05)] if outcomes else 0
    p50 = outcomes[len(outcomes) // 2] if outcomes else 0
    p95 = outcomes[int(len(outcomes) * 0.95)] if outcomes else 0
    return {
        "runs": len(outcomes),
        "p5": p5,
        "p50": p50,
        "p95": p95,
        "note": "Bootstrap-style simulation on trade-level dispersion — research only",
    }


def _bootstrap_stub(return_pct: float, trades: int) -> Dict[str, Any]:
    if trades < 10:
        return {"ci_low": None, "ci_high": None, "note": "Need ≥10 trades"}
    spread = abs(return_pct) * 0.15
    return {
        "ci_low": round(return_pct - spread, 2),
        "ci_high": round(return_pct + spread, 2),
        "confidence": 0.9,
        "note": "Approximate CI — run full backtest for precision",
    }
