"""Operator console — system verdict, blockers, next actions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _section_state(
    *,
    active: bool,
    sample: int = 0,
    min_sample: int = 5,
    loaded: bool = False,
    stale: bool = False,
) -> Dict[str, Any]:
    if not active:
        return {"state": "inactive", "label": "Inactive", "detail": "Engine not running"}
    if not loaded:
        return {
            "state": "not_loaded",
            "label": "Not loaded",
            "detail": "Click refresh or start engine",
        }
    if stale:
        return {"state": "stale", "label": "Stale", "detail": "Data older than threshold"}
    if sample < min_sample:
        return {
            "state": "insufficient_sample",
            "label": "Insufficient sample",
            "detail": f"Need {min_sample}+ observations (have {sample})",
        }
    return {"state": "active", "label": "Active", "detail": "Evidence available"}


def _parse_iso_day(ts: Optional[str]) -> Optional[str]:
    if not ts:
        return None
    try:
        normalized = str(ts).replace("Z", "+00:00")
        return datetime.fromisoformat(normalized).date().isoformat()
    except (TypeError, ValueError):
        return None


def _is_today(ts: Optional[str]) -> bool:
    day = _parse_iso_day(ts)
    if not day:
        return False
    return day == datetime.now(timezone.utc).date().isoformat()


def _read_engine_heartbeat() -> Optional[str]:
    try:
        import pathlib

        hb = pathlib.Path("/tmp/engine_heartbeat")
        if hb.exists():
            return hb.read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    return None


def _scheduler_summary(jobs_status: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    jobs_status = jobs_status or {}
    jobs = jobs_status.get("jobs") or {}
    if not jobs:
        return {
            "alive": "unknown",
            "label": "UNKNOWN",
            "detail": "No scheduler telemetry — jobs service may not be running",
            "last_run": None,
            "last_error": None,
        }

    last_runs: List[str] = []
    errors: List[str] = []
    any_success = False
    for job in jobs.values():
        if not isinstance(job, dict):
            continue
        lr = job.get("last_run")
        if lr:
            last_runs.append(str(lr))
        if job.get("status") == "success":
            any_success = True
        err = job.get("last_error")
        if err:
            errors.append(str(err))

    last_run = max(last_runs) if last_runs else None
    failed = jobs_status.get("failed_jobs") or []
    if failed:
        alive = "degraded"
        label = "DEGRADED"
        detail = f"Failed jobs: {', '.join(failed[:3])}"
    elif any_success and _is_today(last_run):
        alive = "yes"
        label = "ALIVE"
        detail = "At least one job succeeded today"
    elif any_success:
        alive = "stale"
        label = "STALE"
        detail = "Jobs ran before but not confirmed today"
    else:
        alive = "no"
        label = "NOT STARTED"
        detail = "Scheduler telemetry present but no successful runs"

    return {
        "alive": alive,
        "label": label,
        "detail": detail,
        "last_run": last_run,
        "last_error": errors[-1] if errors else None,
    }


def _signal_zero_reasons(
    *,
    running: bool,
    cycles: int,
    signals_today: int,
    cached_recs: int,
    today: Dict[str, Any],
    signals_status: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    reasons: List[Dict[str, Any]] = []
    if not running:
        reasons.append(
            {
                "code": "no_cycle_run",
                "label": "Engine stopped — no scan cycle today",
                "severity": "blocker",
            }
        )
        return reasons

    if cycles == 0:
        reasons.append(
            {
                "code": "no_cycle_run",
                "label": "No engine cycle executed this session",
                "severity": "blocker",
            }
        )

    last_gen = (signals_status or {}).get("last_generation")
    if signals_today == 0 and not _is_today(last_gen):
        reasons.append(
            {
                "code": "pipeline_not_executed",
                "label": "Signal pipeline not executed today",
                "severity": "blocker",
            }
        )

    if cached_recs == 0:
        reasons.append(
            {
                "code": "cache_empty",
                "label": "Recommendation cache empty",
                "severity": "blocker",
            }
        )

    diagnosis = today.get("no_setup_diagnosis") or {}
    breakdown = diagnosis.get("breakdown") or {}
    if breakdown:
        total_rejects = sum(int(v or 0) for v in breakdown.values())
        if total_rejects > 0 and signals_today == 0:
            reasons.append(
                {
                    "code": "candidates_failed_gates",
                    "label": "Candidates evaluated but none passed gates",
                    "severity": "info",
                    "breakdown": breakdown,
                }
            )
    elif running and cycles > 0 and signals_today == 0 and cached_recs > 0:
        reasons.append(
            {
                "code": "selective_scanner",
                "label": "Pipeline ran — scanner selective / regime filters",
                "severity": "info",
            }
        )

    if not reasons and signals_today == 0:
        reasons.append(
            {
                "code": "unknown",
                "label": "Zero signals — root cause not classified",
                "severity": "info",
            }
        )

    return reasons


def build_degraded_ops_operator_console(
    *,
    reason: str = "backend importing",
    brief_ok: bool = False,
) -> Dict[str, Any]:
    """Instant / warmup ops-console — honest probes without faking runtime OK."""
    now = datetime.now(timezone.utc)
    runtime_warm = (
        f"Backend warming ({reason}) — engine runtime unconfirmed"
    )
    md_probe_ok = bool(brief_ok)
    md_runtime = (
        "Brief on disk — not consumed by engine this session"
        if md_probe_ok
        else runtime_warm
    )

    def _row(
        name: str,
        *,
        ok: bool,
        probe: str,
        tier: str,
        runtime_ev: str,
    ) -> Dict[str, Any]:
        evidence = runtime_ev if ok else (
            "Probe warming — reachability not confirmed"
            if tier == "warming"
            else "Probe failed or component down"
        )
        return {
            "name": name,
            "ok": ok,
            "tier": tier,
            "label": probe,
            "probe": probe,
            "runtime_evidence": runtime_ev,
            "evidence": evidence,
        }

    component_evidence = [
        _row(
            "market_data",
            ok=md_probe_ok,
            probe="Probe OK" if md_probe_ok else "Warming",
            tier="probe_ok" if md_probe_ok else "warming",
            runtime_ev=md_runtime,
        ),
        _row(
            "regime_router",
            ok=False,
            probe="Warming",
            tier="warming",
            runtime_ev=runtime_warm,
        ),
        _row(
            "broker",
            ok=False,
            probe="Warming",
            tier="warming",
            runtime_ev=runtime_warm,
        ),
    ]

    providers_honest = {
        "market_data": {
            "probe": "Connected" if md_probe_ok else "Warming",
            "runtime": md_runtime,
        },
        "regime_router": {
            "probe": "Warming",
            "runtime": runtime_warm,
        },
        "broker": {
            "probe": "Warming",
            "runtime": runtime_warm,
        },
    }

    blockers = [
        "Backend importing on :8001",
        "No engine cycle this session",
    ]
    if not md_probe_ok:
        blockers.append("Market data probe not confirmed — wait for full API")

    page_intro = (
        "Ops is in API warmup mode. "
        f"{reason.capitalize()}. "
        "Probe OK means limited reachability (e.g. disk brief), not live engine health. "
        "Use Recovery runbook below, then refresh when /health reports mode=full."
    )

    return {
        "as_of": now.isoformat() + "Z",
        "degraded": True,
        "research_only": True,
        "uptime": "0h 0m",
        "startup_time": None,
        "system_verdict": "API WARMING — NOT RUNNABLE",
        "verdict_code": "WARMING",
        "verdict_detail": reason,
        "verdict_summary": f"API WARMING — {reason}",
        "runnable": False,
        "paper_ready": False,
        "blockers": blockers,
        "next_actions": [
            {
                "step": "1",
                "action": "Wait for /health mode=full on :8001",
                "why": "Full backend runs component probes and engine telemetry",
            },
            {
                "step": "2",
                "action": "Refresh Ops health panel",
                "why": "Probe vs runtime table updates after import completes",
            },
        ],
        "engine": {
            "running": False,
            "dry_run": True,
            "cycle_count": 0,
            "signals_today": 0,
            "trades_today": 0,
            "cached_recommendations": 0,
            "circuit_breaker": False,
        },
        "latency": {"regime_ms": -1},
        "providers": {
            "yfinance": md_probe_ok,
            "regime_router": False,
            "alpaca": {"configured": False, "connected": False, "paper": True},
        },
        "component_evidence": component_evidence,
        "providers_honest": providers_honest,
        "diagnostics": {
            "probe_only_mode": True,
            "warming_mode": True,
            "engine_stopped": True,
            "no_cycles": True,
            "no_cache": True,
            "page_intro": page_intro,
            "signals_today_note": (
                "Signals today: 0 — API warming — not evidence the market produced zero opportunities."
            ),
            "probe_table_note": (
                "Warming probes — see Recovery runbook. Do not treat FAIL as final until backend is full."
            ),
            "engine_stopped_banner": (
                "API warming — engine runtime evidence unavailable. "
                "Boards elsewhere may show brief or snapshot fallback only."
            ),
        },
        "ibkr": {
            "connected": False,
            "gateway_reachable": False,
            "session_auth": "unknown",
            "mode": "paper",
            "health_label": "Backend loading",
            "monitoring_only": True,
        },
        "metrics_display": {
            "uptime": {
                "display": "0h 0m",
                "value": 0,
                "reason": "API shell only — engine not started",
            },
            "regime_latency_ms": {
                "display": "—",
                "value": -1,
                "reason": "Regime probe unavailable during warmup",
            },
        },
        "brief_status": {"ok": brief_ok},
        "trust": {"stale": True, "source": "instant-degraded", "reason": reason},
    }


def build_ops_operator_console(
    *,
    ops_status: Optional[Dict[str, Any]] = None,
    cc_header: Optional[Dict[str, Any]] = None,
    today: Optional[Dict[str, Any]] = None,
    self_learn: Optional[Dict[str, Any]] = None,
    jobs_status: Optional[Dict[str, Any]] = None,
    signals_status: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    startup_time: Optional[str] = None,
) -> Dict[str, Any]:
    """Single operator verdict from engine + header + today cache."""
    ops_status = ops_status or {}
    cc_header = cc_header or {}
    today = today or {}
    execution_readiness = execution_readiness or {}

    eng = {**(cc_header.get("engine") or {}), **(ops_status.get("engine") or {})}
    components = {
        **(ops_status.get("components") or {}),
        **(cc_header.get("components") or {}),
    }

    running = bool(eng.get("running"))
    dry_run = bool(eng.get("dry_run", True))
    breaker = bool(eng.get("circuit_breaker"))
    cycles = int(eng.get("cycle_count") or 0)
    signals_today = int(eng.get("signals_today") or 0)
    cached_recs = int(eng.get("cached_recommendations") or 0)
    last_cycle = eng.get("last_cycle") or _read_engine_heartbeat()
    ibkr = {**(cc_header.get("ibkr") or {}), **(execution_readiness or {})}
    freshness = cc_header.get("freshness") or {}
    scheduler = _scheduler_summary(jobs_status)

    gateway_ok = bool(ibkr.get("gateway_reachable"))
    broker_connected = bool(
        ibkr.get("session_usable")
        or ibkr.get("connected")
        or ibkr.get("broker_connected")
    )
    ibkr_health = ibkr.get("health") or {}
    account_api_ok = ibkr_health.get("account_status") == "ok" or bool(
        ibkr.get("account_loaded")
    )
    monitoring_only = bool(
        ibkr.get("monitoring_only")
        or ibkr_health.get("handoff_status") == "monitoring_only"
    )
    session_auth = (
        "active"
        if broker_connected
        else (
            "inactive"
            if gateway_ok
            else "unknown"
        )
    )
    order_path_tested = bool(ibkr.get("last_order_ok")) and _is_today(
        str(ibkr.get("last_order_ok") or "")
    )
    engine_handoff = bool(
        execution_readiness.get("trade_handoff_ready")
        or (broker_connected and running and cycles > 0)
    )

    blockers: List[str] = []
    if not running:
        blockers.append("Trading engine is stopped")
    if breaker:
        blockers.append(
            f"Circuit breaker: {eng.get('circuit_breaker_reason') or 'tripped'}"
        )
    if scheduler["alive"] in ("no", "unknown"):
        blockers.append(f"Scheduler: {scheduler['detail']}")
    elif scheduler["alive"] == "stale":
        blockers.append("No scheduler job confirmed today")
    if cycles == 0:
        blockers.append("No successful engine cycle this session")
    elif not _is_today(last_cycle):
        blockers.append("No engine cycle completed today")
    if cached_recs == 0:
        blockers.append("Recommendation cache empty")
    if gateway_ok and not broker_connected:
        blockers.append("Broker gateway reachable but session auth inactive")
    elif broker_connected and account_api_ok and monitoring_only:
        pass  # partial broker state — not a hard blocker
    if broker_connected and ibkr_health.get("market_data_status") == "degraded":
        pass  # farm degradation is surfaced in health, not as full disconnect
    if signals_today == 0 and running and cycles > 0:
        blockers.append("Signal pipeline produced zero signals today")
    if freshness.get("worst_tier") not in (None, "FRESH"):
        blockers.append(f"Market data tier: {freshness.get('worst_tier')}")
    if not gateway_ok and not broker_connected and not components.get("broker"):
        blockers.append("Broker path not reachable — paper handoff unavailable")

    paper_ready = running and dry_run and not breaker and cycles > 0 and cached_recs > 0
    live_ready = running and not dry_run and not breaker and cycles > 0 and engine_handoff

    if breaker:
        verdict_code = "LIVE_BLOCKED"
        system_verdict = "NOT READY FOR LIVE EXECUTION"
        verdict_detail = "Circuit breaker active — do not deploy capital"
    elif not running:
        verdict_code = "NOT_RUNNABLE"
        system_verdict = (
            "NOT READY FOR PAPER EXECUTION"
            if dry_run
            else "NOT READY FOR LIVE EXECUTION"
        )
        verdict_detail = "Engine stopped — infrastructure may be up but trading loop is off"
    elif dry_run:
        verdict_code = "PAPER_READY" if paper_ready and len(blockers) <= 1 else "PAPER_ONLY"
        system_verdict = (
            "PAPER EXECUTION READY"
            if paper_ready and not [b for b in blockers if "cache" in b.lower() or "cycle" in b.lower()]
            else "NOT READY FOR PAPER EXECUTION"
        )
        verdict_detail = (
            "Paper/dry-run path can accept handoff after checklist"
            if paper_ready
            else "Paper mode — complete operator checklist before trusting signals"
        )
    elif live_ready:
        verdict_code = "RUNNABLE"
        system_verdict = "LIVE EXECUTION READY"
        verdict_detail = "Engine running live — verify gates and risk before deploy"
    else:
        verdict_code = "NOT_RUNNABLE"
        system_verdict = "NOT READY FOR LIVE EXECUTION"
        verdict_detail = "Live mode — blockers remain on execution path"

    next_actions: List[Dict[str, str]] = []
    step = 1

    def _add(action: str, why: str) -> None:
        nonlocal step
        next_actions.append({"step": str(step), "action": action, "why": why})
        step += 1

    if not running:
        _add("Start trading engine", "Loop is stopped — nothing else will run")
    if scheduler["alive"] in ("unknown", "no", "stale"):
        _add("Verify scheduler heartbeat", scheduler["detail"])
    if cycles == 0 or not _is_today(last_cycle):
        _add("Run one full engine scan cycle", "Confirms signal + cache pipeline")
    if gateway_ok and not broker_connected:
        _add(
            "Confirm broker auth / paper session login",
            "Gateway up but IBKR session not active",
        )
    elif not gateway_ok:
        _add("Start IB Gateway / verify host:port", "Broker path unreachable")
    if cached_recs == 0:
        _add("Refresh recommendation cache", "Today tab needs cached ranked recs")
    if running and signals_today == 0 and cycles > 0:
        _add("Inspect filter funnel / regime gate", "Cycles ran but zero signals")
    if not next_actions:
        next_actions.append(
            {
                "step": "✓",
                "action": "Monitor positions, alerts, and last successful times",
                "why": "Core loop appears healthy",
            }
        )

    signal_zero_reason = _signal_zero_reasons(
        running=running,
        cycles=cycles,
        signals_today=signals_today,
        cached_recs=cached_recs,
        today=today,
        signals_status=signals_status,
    )

    why_no_signals: List[Dict[str, Any]] = []
    for r in signal_zero_reason:
        row: Dict[str, Any] = {"gate": r["code"], "note": r["label"]}
        if r.get("breakdown"):
            for k, v in sorted(r["breakdown"].items(), key=lambda x: -int(x[1] or 0)):
                why_no_signals.append({"gate": k, "count": int(v or 0)})
        else:
            why_no_signals.append(row)

    diagnosis = today.get("no_setup_diagnosis") or {}
    breakdown = diagnosis.get("breakdown") or {}
    if breakdown and not any(w.get("count") for w in why_no_signals):
        for k, v in sorted(breakdown.items(), key=lambda x: -int(x[1] or 0)):
            why_no_signals.append({"gate": k, "count": int(v or 0)})

    last_rec_refresh = today.get("generated_at") or today.get("trust", {}).get("as_of")
    last_times = {
        "last_successful_engine_cycle": last_cycle,
        "last_recommendation_refresh": last_rec_refresh,
        "last_broker_heartbeat": ibkr.get("last_heartbeat"),
        "last_paper_order_test": ibkr.get("last_order_ok"),
        "last_ibkr_disconnect": ibkr_health.get("last_disconnect_at")
        or ibkr.get("last_disconnect_at"),
        "last_ibkr_restore": ibkr_health.get("last_restore_at")
        or ibkr.get("last_restore_at"),
        "last_scheduler_run": scheduler.get("last_run"),
    }

    uptime_raw = ops_status.get("uptime")
    regime_ms = (ops_status.get("latency") or {}).get("regime_ms")
    regime_probe_ok = regime_ms is not None and regime_ms >= 0
    boot_label = startup_time[:19] if startup_time else "boot"

    if uptime_raw:
        uptime_display = uptime_raw
        if not running:
            uptime_reason = (
                f"API process up ({uptime_raw}) — trading engine stopped"
            )
        elif cycles == 0:
            uptime_reason = (
                f"API up ({uptime_raw}) — no engine cycles this session yet"
            )
        else:
            uptime_reason = f"API up since {boot_label}"
    else:
        uptime_display = "Unknown"
        uptime_reason = "API startup time unavailable"

    if regime_probe_ok:
        latency_display = f"{regime_ms}ms"
        if not running:
            latency_reason = "Live regime probe — engine loop not running"
        elif cycles == 0:
            latency_reason = "Live regime probe — no scan cycle yet"
        else:
            latency_reason = "Last regime probe this session"
    elif not running:
        latency_display = "Probe pending"
        latency_reason = "Start engine or run a cycle to probe regime path"
    elif cycles == 0:
        latency_display = "No cycle yet"
        latency_reason = "Run a scan cycle to measure regime latency"
    else:
        latency_display = "Probe failed"
        latency_reason = "Regime probe unavailable this session"

    if cached_recs:
        cache_display = str(cached_recs)
        cache_reason = f"{cached_recs} cached recommendation(s)"
    elif not running:
        cache_display = "0"
        cache_reason = "Start engine, then run a scan cycle to populate cache"
    elif cycles == 0:
        cache_display = "0"
        cache_reason = "Run a scan cycle to generate recommendation cache"
    else:
        cache_display = "0"
        cache_reason = "Cycle ran but cache empty — inspect signal pipeline"

    metrics_display = {
        "uptime": {
            "value": uptime_raw,
            "display": uptime_display,
            "reason": uptime_reason,
        },
        "regime_latency_ms": {
            "value": regime_ms if regime_probe_ok else None,
            "display": latency_display,
            "reason": latency_reason,
        },
        "cached_recommendations": {
            "value": cached_recs,
            "display": cache_display,
            "reason": cache_reason,
        },
    }

    engine_controls = {
        "running": running,
        "can_start": not running,
        "can_stop": running,
        "can_run_cycle": True,
        "auto_start_env": "CC_AUTO_START_ENGINE",
        "start_endpoint": "/api/ops/engine/start",
        "run_cycle_endpoint": "/api/ops/engine/run-cycle",
    }

    execution_layers = [
        {
            "layer": "Service reachable",
            "status": "OK" if gateway_ok or components.get("market_data") else "FAIL",
            "tone": "ok" if gateway_ok else "warn",
            "detail": "Gateway / market data probe",
        },
        {
            "layer": "Engine running",
            "status": "YES" if running else "NO",
            "tone": "ok" if running else "fail",
            "detail": "Trading loop",
        },
        {
            "layer": "Scheduler alive",
            "status": scheduler["label"],
            "tone": (
                "ok"
                if scheduler["alive"] == "yes"
                else "warn"
                if scheduler["alive"] in ("stale", "unknown")
                else "fail"
            ),
            "detail": scheduler["detail"],
        },
        {
            "layer": "Session auth",
            "status": session_auth.upper(),
            "tone": "ok" if session_auth == "active" else "warn",
            "detail": "IBKR login / Alpaca keys",
        },
        {
            "layer": "Order path tested",
            "status": "YES" if order_path_tested else "NO",
            "tone": "ok" if order_path_tested else "warn",
            "detail": "Paper/live order exercised this session",
        },
        {
            "layer": "Engine handoff",
            "status": "ACTIVE" if engine_handoff else "NOT ACTIVE",
            "tone": "ok" if engine_handoff else "warn",
            "detail": "Broker + engine ready for orders",
        },
        {
            "layer": "Last successful cycle",
            "status": "TODAY" if _is_today(last_cycle) else "NONE TODAY",
            "tone": "ok" if _is_today(last_cycle) else "warn",
            "detail": last_cycle or "No cycle timestamp",
        },
    ]

    boundary = {
        "market_data": (
            "real-time"
            if freshness.get("worst_tier") == "FRESH"
            else str(freshness.get("worst_tier") or "off/degraded").lower()
        ),
        "signal_engine": "on" if running else "off",
        "execution_mode": "paper" if dry_run else "live",
        "broker_path": (
            "connected + exercised"
            if broker_connected and order_path_tested
            else (
                "monitoring only"
                if broker_connected and account_api_ok and monitoring_only
                else (
                    "connected, not exercised"
                    if broker_connected
                    else (
                        "reachable, not logged in"
                        if gateway_ok
                        else "disconnected"
                    )
                )
            )
        ),
        "portfolio_sync": (
            "synced"
            if execution_readiness.get("portfolio_synced")
            else str(execution_readiness.get("portfolio_source") or "unknown/manual")
        ),
    }

    closed_trades = 0
    if self_learn and self_learn.get("engine_state"):
        closed_trades = int(self_learn.get("closed_trades_available") or 0)

    engine_related = {
        "regime_router",
        "ensembler",
        "context_assembler",
        "leaderboard",
        "position_mgr",
        "learning_loop",
        "edge_calculator",
        "circuit_breaker",
        "broker",
        "market_data",
    }

    def _runtime_evidence(name: str) -> str:
        if name == "market_data":
            if cycles > 0 and _is_today(last_cycle):
                tier = freshness.get("worst_tier") or "unknown"
                return f"Consumed in completed cycle ({tier})"
            return "Runtime none this session"
        if name == "regime_router":
            if cycles > 0 and regime_ms is not None and regime_ms >= 0:
                return f"Routed in session (last probe {regime_ms}ms)"
            if cycles > 0:
                return "Cycle executed — regime output present"
            return "No cycle executed"
        if name == "broker":
            if broker_connected and order_path_tested:
                return "Live handoff exercised this session"
            if broker_connected:
                return "Session active — no order test this session"
            if gateway_ok:
                return "Gateway reachable — session inactive"
            transport = ibkr.get("transport") or {}
            if transport.get("failed_handshake_count_1m"):
                return "Connect failed — verify Gateway host:port and API client ID"
            if transport.get("ib_handshake_started"):
                return "Handshake incomplete — retry Connect on IBKR tab"
            return "Not connected — IBKR tab → Connect (Gateway may still be up; no TCP probe)"
        if name == "leaderboard":
            if cached_recs > 0:
                return f"{cached_recs} cached recs generated"
            return "No cache generated"
        if name == "learning_loop":
            if closed_trades >= 5:
                return f"{closed_trades} closed trades in runtime sample"
            if closed_trades > 0:
                return f"Insufficient sample ({closed_trades} trades)"
            return "No runtime sample"
        if not running and name in engine_related:
            return "Engine off — no runtime path"
        if cycles == 0 and name in engine_related:
            return "No cycle executed this session"
        if components.get(name):
            return "Probe only — runtime unconfirmed"
        return "Probe failed — no runtime path"

    component_evidence = []
    for name, ok in sorted(components.items()):
        runtime_ev = _runtime_evidence(name)
        if not ok:
            tier = "fail"
            probe_label = "FAIL"
            evidence = "Probe failed or component down"
        elif name in ("broker",) and broker_connected and cycles > 0 and order_path_tested:
            tier = "trading_ready"
            probe_label = "Probe OK"
            evidence = runtime_ev
        elif ok:
            tier = "probe_ok"
            probe_label = "Probe OK"
            evidence = runtime_ev
        else:
            tier = "fail"
            probe_label = "FAIL"
            evidence = runtime_ev

        component_evidence.append(
            {
                "name": name,
                "ok": bool(ok),
                "tier": tier,
                "label": probe_label,
                "probe": probe_label,
                "runtime_evidence": runtime_ev,
                "evidence": evidence,
            }
        )

    probe_only_mode = (not running) or cycles == 0 or cached_recs == 0
    intro_parts: List[str] = []
    if not running:
        intro_parts.append("the engine is stopped")
    if cycles == 0:
        intro_parts.append("no cycle has executed this session")
    if cached_recs == 0:
        intro_parts.append("no cache has been generated")
    intro_detail = ", ".join(intro_parts)
    if probe_only_mode:
        page_intro = (
            "Ops is currently in probe-only mode. "
            + (f"{intro_detail.capitalize()}. " if intro_detail else "")
            + "Probe checks may still pass, but probe health is not the same as live runtime health. "
            "Treat this page as a diagnostics surface until fresh runtime evidence exists."
        )
    else:
        page_intro = (
            "Runtime evidence is present this session. "
            "Probe OK still means reachability — verify runtime column before trusting capital decisions."
        )

    if signals_today == 0:
        if not running or cycles == 0:
            signals_today_note = (
                "Signals today: 0 — Reason: no engine cycle executed this session — "
                "not evidence that the market produced zero opportunities."
            )
        else:
            signals_today_note = (
                f"Signals today: 0 — pipeline ran ({cycles} cycle(s)) — "
                "scanner/regime filters may have rejected all candidates."
            )
    else:
        signals_today_note = f"Signals today: {signals_today} — from engine runtime this session."

    market_data_probe = bool(components.get("market_data"))
    if market_data_probe and (cycles == 0 or not _is_today(last_cycle)):
        market_data_runtime = (
            "Reachable, but not recently consumed by a completed engine cycle"
        )
    elif market_data_probe:
        market_data_runtime = "Consumed in last completed engine cycle"
    else:
        market_data_runtime = "Probe failed — no runtime consumption possible"

    if components.get("regime_router"):
        regime_runtime = (
            "Service available, runtime output this session"
            if cycles > 0
            else "Service available, no runtime output this session"
        )
    else:
        regime_runtime = "Service unavailable"

    if broker_connected and order_path_tested:
        broker_runtime = "Connected — live handoff exercised"
    elif broker_connected:
        broker_runtime = "Connected — handoff not exercised this session"
    elif gateway_ok:
        broker_runtime = "Gateway reachable — no live handoff possible"
    else:
        broker_runtime = "Unreachable, no live handoff possible"

    providers_honest = {
        "market_data": {
            "probe": "Connected" if market_data_probe else "Disconnected",
            "runtime": market_data_runtime,
        },
        "regime_router": {
            "probe": "Available" if components.get("regime_router") else "Down",
            "runtime": regime_runtime,
        },
        "broker": {
            "probe": (
                "Session active"
                if broker_connected
                else ("Gateway OK" if gateway_ok else "Not connected")
            ),
            "runtime": broker_runtime,
        },
    }

    diagnostics = {
        "probe_only_mode": probe_only_mode,
        "engine_stopped": not running,
        "no_cycles": cycles == 0,
        "no_cache": cached_recs == 0,
        "page_intro": page_intro,
        "signals_today_note": signals_today_note,
        "engine_stopped_banner": (
            "Runtime override active — engine is stopped. Any board state shown elsewhere "
            "is cached, fallback, or precomputed output, not fresh engine execution from this session."
            if not running
            else None
        ),
        "collapsed_diagnostics_note": (
            "Engine off or insufficient trade sample — Ops experimental panels below "
            "(self-learning, Thompson sizing, execution metrics) need runtime evidence before "
            "they affect capital. Dossier / stock-intel research loads from market data independently."
            if probe_only_mode
            else None
        ),
    }

    failed_jobs = (jobs_status or {}).get("failed_jobs") or []
    operational_events = {
        "last_engine_error": eng.get("last_error"),
        "last_failed_job": failed_jobs[0] if failed_jobs else scheduler.get("last_error"),
        "last_heartbeat": ibkr.get("last_heartbeat") or last_cycle,
        "last_cycle": last_cycle,
        "scheduler_detail": scheduler.get("detail"),
    }

    sections = {
        "self_learning": _section_state(
            active=running,
            sample=closed_trades,
            min_sample=20,
            loaded=bool(self_learn),
        ),
        "thompson_sizing": _section_state(
            active=running, sample=closed_trades, min_sample=30, loaded=False
        ),
        "feature_ic": _section_state(
            active=running, sample=closed_trades, min_sample=50, loaded=False
        ),
        "pipeline_stats": _section_state(active=running, loaded=cycles > 0),
        "execution_metrics": _section_state(
            active=running,
            sample=int(eng.get("trades_today") or 0),
            min_sample=1,
            loaded=bool(eng.get("trades_today")),
        ),
    }

    machines_health: Dict[str, Any] = {}
    try:
        from src.services.decision_machines import build_machines_health_panel
        from src.services.platform_error_log import get_error_log

        err_count = int(get_error_log(limit=50).get("total_buffered") or 0)
        today_with_posture = {
            **today,
            "principles_posture": today.get("principles_posture"),
            "decision_model": today.get("decision_model"),
            "market_regime": today.get("market_regime"),
            "trust": today.get("trust"),
        }
        machines_health = build_machines_health_panel(
            ops_status=ops_status,
            today=today_with_posture,
            cc_header=cc_header,
            execution_readiness=execution_readiness,
            error_log_count=err_count,
        )
    except Exception:
        machines_health = {}

    return {
        "as_of": datetime.now(timezone.utc).isoformat() + "Z",
        "system_verdict": system_verdict,
        "verdict_code": verdict_code,
        "verdict_detail": verdict_detail,
        "verdict_summary": f"{system_verdict} — {verdict_detail}",
        "runnable": verdict_code == "RUNNABLE",
        "paper_ready": paper_ready,
        "blockers": blockers[:8],
        "next_actions": next_actions[:6],
        "last_times": last_times,
        "metrics_display": metrics_display,
        "engine_controls": engine_controls,
        "execution_layers": execution_layers,
        "execution_boundary": boundary,
        "signal_zero_reason": signal_zero_reason,
        "operational_events": operational_events,
        "scheduler": scheduler,
        "last_events": {
            "last_cycle": last_cycle,
            "last_brief": (cc_header.get("brief_status") or {}).get("latest", {}).get(
                "as_of"
            ),
            "ibkr_heartbeat": ibkr.get("last_heartbeat"),
            "market_data_tier": freshness.get("worst_tier"),
        },
        "engine": {
            "running": running,
            "dry_run": dry_run,
            "cycle_count": cycles,
            "signals_today": signals_today,
            "trades_today": int(eng.get("trades_today") or 0),
            "cached_recommendations": cached_recs,
            "circuit_breaker": breaker,
        },
        "why_no_signals": why_no_signals,
        "section_states": sections,
        "component_evidence": component_evidence,
        "diagnostics": diagnostics,
        "providers_honest": providers_honest,
        "machines_health": machines_health,
        "ibkr": {
            "connected": broker_connected,
            "gateway_reachable": gateway_ok,
            "session_auth": session_auth,
            "host": ibkr.get("host") or execution_readiness.get("host"),
            "port": ibkr.get("port") or execution_readiness.get("port"),
            "mode": ibkr.get("mode") or "paper",
            "account_sync": ibkr.get("account") or execution_readiness.get("portfolio_source"),
            "health": ibkr_health or execution_readiness.get("health") or {},
            "health_label": ibkr.get("health_label")
            or execution_readiness.get("health_label"),
            "monitoring_only": monitoring_only,
            "degraded_reasons": list(
                ibkr_health.get("degraded_reasons")
                or execution_readiness.get("degraded_reasons")
                or []
            ),
            "last_disconnect_at": ibkr_health.get("last_disconnect_at")
            or execution_readiness.get("last_disconnect_at"),
            "last_restore_at": ibkr_health.get("last_restore_at")
            or execution_readiness.get("last_restore_at"),
        },
        "providers": cc_header.get("providers") or ops_status.get("providers"),
        "uptime": ops_status.get("uptime"),
        "latency": ops_status.get("latency"),
        "startup_time": startup_time,
    }
