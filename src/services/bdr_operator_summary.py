"""BDR-style operator decision brief — auto-generated from live system state."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.utils.numeric_parse import parse_ratio

_AVOID_ACTIONS = frozenset(
    {"AVOID", "NO_TRADE", "NO_TOUCH", "DO_NOT_TOUCH", "AVOID_NOW"}
)
_WATCH_ACTIONS = frozenset(
    {"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR", "MONITOR", "PILOT"}
)
_DEPLOY_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "TRADE_NOW", "STRONG_TRADE"})


def _bi(zh: str, en: str) -> str:
    """Operator-facing bilingual line (繁中 · English)."""
    return f"{zh} · {en}"


_AVOID_REASON_LABELS = {
    "poor_rr": "R:R below deploy bar",
    "regime_conflict": "Regime / setup mismatch",
    "execution_weak": "Execution confidence weak",
    "low_data_quality": "Data quality insufficient",
    "weak_thesis": "Thesis not confirmed",
    "laggard": "Sector laggard",
    "other": "Setup mismatch",
}


def _norm_action(row: Dict[str, Any]) -> str:
    return str(row.get("action") or row.get("effective_action") or "WATCH").upper()


def _row_rr(row: Dict[str, Any]) -> float:
    return parse_ratio(row.get("risk_reward") or row.get("rr"), 0.0) or 0.0


def _row_main_issue(row: Dict[str, Any]) -> str:
    for key in ("avoid_reason", "invalidation", "action_reason", "why_not"):
        val = row.get(key)
        if isinstance(val, list):
            val = val[0] if val else ""
        if val:
            return str(val)[:120]
    rr = _row_rr(row)
    act = _norm_action(row)
    if rr > 0 and rr < 2.5:
        return f"R:R {rr:.1f} — below 2.5 deploy bar"
    if act in _AVOID_ACTIONS:
        return "AVOID — not monitor/deploy priority"
    if not row.get("execution_ready") and act in _DEPLOY_ACTIONS:
        return "Not execution-ready"
    return "Monitor — timing / confirmation pending"


def _deploy_qualified_count(rows: List[Dict[str, Any]]) -> int:
    return sum(
        1
        for row in rows
        if row.get("execution_ready") and _norm_action(row) in _DEPLOY_ACTIONS
    )


def _decision_headline(
    *,
    tradeability: str,
    should_trade: bool,
    deploy_open: bool,
    gates_active: bool,
    deploy_count: int,
) -> Tuple[str, str]:
    tb = (tradeability or "WAIT").upper()
    if deploy_open and deploy_count >= 1 and not gates_active:
        return "DEPLOY", _bi(
            "DEPLOY — bracket 就緒時以 1R 選擇性 sizing",
            "DEPLOY. Selective sizing at 1R when brackets ready.",
        )
    if tb in ("SELECTIVE", "TRADE", "STRONG_TRADE") and deploy_count >= 1:
        if gates_active:
            return "SELECTIVE", _bi(
                "SELECTIVE — 閘門開啟後 deploy",
                "SELECTIVE. Deploy when gates open.",
            )
        return (
            "SELECTIVE",
            _bi(
                "SELECTIVE — 複核 deploy-qualified，確認 execution ladder",
                "SELECTIVE. Review deploy-qualified — verify execution ladder.",
            ),
        )
    if tb in ("NO_TRADE",) or not should_trade:
        return "NO_TRADE", _bi("NO TRADE — 只 monitor", "NO TRADE. Monitor only.")
    if tb == "WAIT":
        return "NO_TRADE", _bi("NO TRADE — 只 monitor", "NO TRADE. Monitor only.")
    return "NO_TRADE", _bi("NO TRADE — 只 monitor", "NO TRADE. Monitor only.")


def _regime_gate_detail(
    *,
    tradeability: str,
    should_trade: bool,
    market_regime: Dict[str, Any],
) -> str:
    tb = (tradeability or "WAIT").upper()
    trend = str(market_regime.get("trend") or market_regime.get("label") or "—").upper()
    risk = str(
        market_regime.get("risk_state") or market_regime.get("label") or ""
    ).upper()
    parts = [f"tradeability {tb}"]
    if trend:
        parts.append(f"market {trend}")
    if risk in ("RISK_OFF", "NO_TRADE"):
        parts.append(risk)
    if not should_trade:
        parts.append("should_trade=false")
    return " · ".join(parts)


def _broker_gate_detail(
    *,
    ibkr_status: Optional[Dict[str, Any]],
    execution_readiness: Optional[Dict[str, Any]],
    ops: Optional[Dict[str, Any]],
) -> Tuple[bool, str]:
    ib = ibkr_status or {}
    ex = execution_readiness or {}
    ops_obj = ops or {}
    connected = bool(
        ib.get("connected")
        or ib.get("session_usable")
        or ex.get("ibkr_connected")
        or ex.get("broker_connected")
    )
    handoff = bool(ex.get("trade_handoff_ready") or ex.get("bracket_order_ready"))
    label = (
        ex.get("unified_label")
        or ex.get("readiness_label")
        or ("CONNECTED" if connected else "OFFLINE")
    )
    if ops_obj.get("breaker"):
        return True, f"EXEC BLOCKED — {label}"
    if not connected:
        gw = ib.get("gateway_reachable")
        if gw is False:
            return True, "IBKR gateway down"
        return True, f"IBKR offline — {label}"
    if not handoff and not ex.get("bracket_ready"):
        return True, f"Broker connected — handoff not ready ({label})"
    return False, str(label)


def _pick_rr_table_rows(
    playbook_rows: List[Dict[str, Any]], limit: int = 5
) -> List[Dict[str, Any]]:
    """Top names for R:R quality table — prefer AVOID/monitor from ranked board."""
    ranked: List[Dict[str, Any]] = []
    for i, row in enumerate(playbook_rows or [], 1):
        act = _norm_action(row)
        if act in _AVOID_ACTIONS or act in _WATCH_ACTIONS:
            ranked.append(
                {
                    "rank": row.get("rank") or i,
                    "ticker": row.get("ticker") or "—",
                    "action": act,
                    "risk_reward": round(_row_rr(row), 2) if _row_rr(row) else "—",
                    "main_issue": _row_main_issue(row),
                }
            )
    if ranked:
        return ranked[:limit]
    fallback = []
    for i, row in enumerate(playbook_rows or [], 1):
        fallback.append(
            {
                "rank": row.get("rank") or i,
                "ticker": row.get("ticker") or "—",
                "action": _norm_action(row),
                "risk_reward": round(_row_rr(row), 2) if _row_rr(row) else "—",
                "main_issue": _row_main_issue(row),
            }
        )
    return fallback[:limit]


def _plain_english_read(
    *,
    deploy_count: int,
    tradeability: str,
    should_trade: bool,
    no_setup_diagnosis: Optional[Dict[str, Any]],
    regime_wait_explanation: Optional[List[str]],
    playbook_rows: List[Dict[str, Any]],
) -> str:
    diag = no_setup_diagnosis or {}
    lines = list(regime_wait_explanation or [])
    watch_count = sum(1 for r in playbook_rows if _norm_action(r) in _WATCH_ACTIONS)
    avoid_count = sum(1 for r in playbook_rows if _norm_action(r) in _AVOID_ACTIONS)
    if lines:
        lead = lines[0]
    elif diag.get("headline"):
        lead = str(diag["headline"])
    elif deploy_count >= 1:
        lead = _bi(
            f"{deploy_count} 個 deploy-qualified — 清單通過前 sizing 仍受閘門約束",
            f"{deploy_count} deploy-qualified name(s) — gates still bind sizing until checklist clears.",
        )
    elif watch_count and not avoid_count:
        lead = _bi(
            "板面有 watch 級 idea，但未達 deploy bar — 質素篩選正常，非 idea 不足",
            "Board has watch-grade ideas but none cleared deploy bar — "
            "quality filters are doing their job, not an idea shortage.",
        )
    elif watch_count or avoid_count:
        lead = _bi(
            "板面標的未過時機、R:R 或 execution 閘門 — 屬質素門檻問題，非掃描器故障",
            "Names on the board fail timing, R:R, or execution gates — "
            "this is a quality bar issue, not a broken scanner.",
        )
    elif not should_trade or (tradeability or "").upper() == "NO_TRADE":
        lead = _bi(
            "體制閘門關閉 — 守護資金優先於個別 setup",
            "Regime gate closed — capital preservation overrides individual setups.",
        )
    else:
        lead = _bi(
            "無 deploy-qualified — 耐心同 monitor queue 為主決策",
            "No deploy-qualified setups — patience and monitor queue are the active decision.",
        )
    return lead


def _what_to_do_now(
    *,
    decision_authority: Optional[Dict[str, Any]],
    todays_decision: Optional[Dict[str, Any]],
    monitor_tickers: List[str],
    repair_priority: str,
) -> Dict[str, List[str]]:
    da = decision_authority or {}
    td = todays_decision or {}
    monitor_only: List[str] = []
    do_not_deploy: List[str] = []

    for t in monitor_tickers[:5]:
        if t:
            monitor_only.append(
                _bi(
                    f"追蹤 {t} 升級觸發 — 僅 Playbook monitor queue",
                    f"Track {t} for upgrade triggers — Playbook monitor queue only.",
                )
            )

    for ln in (td.get("monitor_triggers") or [])[:3]:
        s = str(ln).strip()
        if s and s not in monitor_only:
            monitor_only.append(s)

    if not monitor_only:
        monitor_only.append(
            _bi(
                "跟 Dashboard monitor queue 同 near-miss 升級候選",
                "Follow Dashboard monitor queue and near-miss upgrade candidates.",
            )
        )
    monitor_only.append(
        _bi(
            "資料／IBKR 修復後重新整理 Dashboard＋Playbook",
            "Refresh Dashboard + Playbook after data / IBKR repair.",
        )
    )
    if repair_priority:
        monitor_only.append(repair_priority)

    degraded = da.get("degraded_copy") or {}
    if degraded.get("decision_authority_line"):
        do_not_deploy.append(str(degraded["decision_authority_line"]))
    if degraded.get("fallback_board_line"):
        do_not_deploy.append(str(degraded["fallback_board_line"]))
    for ln in (td.get("risk_blockers") or [])[:4]:
        s = str(ln).strip()
        if s:
            do_not_deploy.append(s)
    for ln in (td.get("why_not_aggressive") or [])[:3]:
        s = str(ln).strip()
        if s and s not in do_not_deploy:
            do_not_deploy.append(s)
    if da.get("gates_active"):
        gates = da.get("gates") or {}
        for key, active in gates.items():
            if active:
                do_not_deploy.append(f"Gate active: {key.replace('_', ' ')}")
    if not do_not_deploy:
        do_not_deploy.append(
            _bi(
                "禁止部署 — board 閘門關閉，待 unlock 清單通過",
                "Do not deploy — board gate closed until unlock checklist clears.",
            )
        )
    do_not_deploy.append(
        _bi(
            "deploy_open 且 authority=deploy 前，勿 sizing、bracket 或 handoff",
            "No sizing, bracket send, or handoff until deploy_open and authority=deploy.",
        )
    )

    return {
        "monitor_only": monitor_only[:6],
        "do_not_deploy": do_not_deploy[:6],
    }


def _unlock_checklist(
    unlock_deploy: Optional[Dict[str, Any]],
    *,
    tradeability: str,
    deploy_count: int,
    execution_readiness: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if unlock_deploy and unlock_deploy.get("conditions"):
        out = []
        for cond in unlock_deploy["conditions"]:
            key = str(cond.get("key") or "")
            labels = {
                "regime": "可交易性 · Tradeability",
                "deployable": "部署名單 · Deploy-qualified count",
                "broker": "券商交付 · Broker handoff",
                "board": "板面質素 · Board quality",
            }
            out.append(
                {
                    "key": key,
                    "label": labels.get(key, cond.get("label") or key),
                    "met": bool(cond.get("met")),
                    "current": cond.get("detail") or "",
                    "target": {
                        "regime": "SELECTIVE+",
                        "deployable": "≥1 deploy-qualified",
                        "broker": "Live handoff ready",
                        "board": "≥1 watch-qualified on fresh data",
                    }.get(key, ""),
                }
            )
        return out

    ex = execution_readiness or {}
    tb = (tradeability or "WAIT").upper()
    broker_ready = bool(
        ex.get("trade_handoff_ready")
        or (ex.get("broker_connected") and ex.get("bracket_order_ready"))
    )
    return [
        {
            "key": "regime",
            "label": "可交易性 · Tradeability",
            "met": tb in ("SELECTIVE", "TRADE", "STRONG_TRADE"),
            "current": f"Current: {tb}",
            "target": "SELECTIVE+",
        },
        {
            "key": "deployable",
            "label": "部署名單 · Deploy-qualified count",
            "met": deploy_count >= 1,
            "current": f"Current: {deploy_count}",
            "target": "≥1 deploy-qualified",
        },
        {
            "key": "broker",
            "label": "券商交付 · Broker handoff",
            "met": broker_ready,
            "current": f"Current: {ex.get('unified_label') or ex.get('readiness_label') or 'Offline'}",
            "target": "Live handoff ready",
        },
        {
            "key": "board",
            "label": "板面質素 · Board quality",
            "met": deploy_count >= 1,
            "current": f"Current: {deploy_count} deploy-qualified",
            "target": "≥1 watch-qualified on fresh data",
        },
    ]


def _best_concise_note(
    *,
    decision_code: str,
    tradeability: str,
    deploy_count: int,
    gates_active: bool,
) -> str:
    tb = (tradeability or "WAIT").upper()
    if decision_code == "DEPLOY" and deploy_count >= 1:
        return _bi(
            "Deploy 窗口 — 僅以 1R＋bracket sizing；閘門已清",
            "Deploy window — size only at 1R with bracket; gates cleared.",
        )
    if decision_code == "SELECTIVE" and deploy_count >= 1:
        return _bi(
            "SELECTIVE 日 — handoff 前確認清單",
            "Selective day — verify checklist before any handoff.",
        )
    if gates_active and deploy_count < 1:
        return _bi(
            "守護／monitor 日 — 有 idea 但未達 deploy bar",
            "Preservation / monitor day — ideas exist but deploy bar not met.",
        )
    if tb in ("WAIT", "NO_TRADE"):
        return _bi(
            "只 monitor 日 — 待 tradeability 改善前守護資金",
            "Monitor-only day — protect capital until tradeability improves.",
        )
    return _bi(
        "Monitor session — 閘門開啟前勿全倉 deploy",
        "Monitor session — no full-size deploy until gates open.",
    )


def format_bdr_summary_text(summary: Dict[str, Any]) -> str:
    """Plain-text copy-paste format matching operator BDR brief."""
    lines: List[str] = []
    lines.append(f"**Decision:** {summary.get('decision_line', '—')}")
    lines.append("")
    lines.append("**Hard gates blocking · 硬性閘門**")
    for gate in summary.get("hard_gates_blocking") or []:
        lines.append(f"{gate.get('n')}. {gate.get('label')} — {gate.get('detail')}")
    lines.append("")
    lines.append("**R:R quality · top names · 風險回報**")
    lines.append("Rank | Ticker | Action | R:R | Main issue")
    for row in summary.get("rr_quality_table") or []:
        lines.append(
            f"{row.get('rank')} | {row.get('ticker')} | {row.get('action')} | "
            f"{row.get('risk_reward')} | {row.get('main_issue')}"
        )
    lines.append("")
    lines.append("**Plain-English read · 白話解讀**")
    lines.append(str(summary.get("plain_english_read") or ""))
    lines.append("")
    lines.append("**What to do now · 現在要做什麼**")
    wtd = summary.get("what_to_do_now") or {}
    lines.append("Monitor only · 只監察:")
    for item in wtd.get("monitor_only") or []:
        lines.append(f"• {item}")
    lines.append("Do not deploy · 不可部署:")
    for item in wtd.get("do_not_deploy") or []:
        lines.append(f"• {item}")
    lines.append("")
    lines.append("**Unlock checklist · 解鎖清單**")
    for item in summary.get("unlock_checklist") or []:
        status = "✓" if item.get("met") else "✗"
        lines.append(
            f"{status} {item.get('label')}: {item.get('current')} → target {item.get('target')}"
        )
    lines.append("")
    lines.append("**Best concise note · 一句重點**")
    lines.append(str(summary.get("best_concise_note") or ""))
    if summary.get("as_of"):
        lines.append("")
        lines.append(f"As of: {summary['as_of']}")
    return "\n".join(lines)


def build_bdr_operator_summary(
    state: Dict[str, Any],
    playbook_rows: List[Dict[str, Any]],
    *,
    ibkr_status: Optional[Dict[str, Any]] = None,
    ops: Optional[Dict[str, Any]] = None,
    unlock_deploy: Optional[Dict[str, Any]] = None,
    todays_decision: Optional[Dict[str, Any]] = None,
    no_setup_diagnosis: Optional[Dict[str, Any]] = None,
    regime_wait_explanation: Optional[List[str]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    monitor_tickers: Optional[List[str]] = None,
    as_of: Optional[str] = None,
) -> Dict[str, Any]:
    """Build BDR operator summary from live dashboard / playbook state."""
    market_regime = state.get("market_regime") or {}
    cc_state = state.get("cc_state") or {}
    system_state = state.get("system_state") or {}
    decision_authority = state.get("decision_authority") or {}

    tradeability = str(
        market_regime.get("honest_tradeability")
        or market_regime.get("tradeability")
        or cc_state.get("tradeability_state", {}).get("tradeability")
        or system_state.get("tradeability")
        or "WAIT"
    ).upper()
    should_trade = bool(
        market_regime.get(
            "should_trade",
            cc_state.get("tradeability_state", {}).get("should_trade", False),
        )
    )
    deploy_open = bool(system_state.get("deploy_open"))
    gates_active = bool(decision_authority.get("gates_active"))
    deploy_count = _deploy_qualified_count(playbook_rows)
    if state.get("deploy_qualified_count") is not None:
        deploy_count = int(state.get("deploy_qualified_count") or 0)

    decision_code, decision_line = _decision_headline(
        tradeability=tradeability,
        should_trade=should_trade,
        deploy_open=deploy_open,
        gates_active=gates_active,
        deploy_count=deploy_count,
    )
    if gates_active and decision_code == "DEPLOY":
        decision_code = "SELECTIVE"
        decision_line = _bi(
            "SELECTIVE — 閘門開啟後 deploy",
            "SELECTIVE. Deploy when gates open.",
        )

    hard_gates: List[Dict[str, Any]] = []
    n = 0

    regime_blocked = (
        not should_trade
        or tradeability in ("WAIT", "NO_TRADE")
        or str(market_regime.get("risk_state") or "").upper()
        in ("RISK_OFF", "NO_TRADE")
    )
    if regime_blocked:
        n += 1
        hard_gates.append(
            {
                "n": n,
                "key": "regime",
                "label": "Regime gate · 市場狀態閘門",
                "detail": _regime_gate_detail(
                    tradeability=tradeability,
                    should_trade=should_trade,
                    market_regime=market_regime,
                ),
            }
        )

    broker_blocked, broker_detail = _broker_gate_detail(
        ibkr_status=ibkr_status,
        execution_readiness=execution_readiness or state.get("execution_readiness"),
        ops=ops,
    )
    if broker_blocked:
        n += 1
        hard_gates.append(
            {
                "n": n,
                "key": "broker",
                "label": "Broker / execution · 券商執行",
                "detail": broker_detail,
            }
        )

    if deploy_count < 1:
        n += 1
        hard_gates.append(
            {
                "n": n,
                "key": "deploy_count",
                "label": "Deploy-qualified count · 可部署數量",
                "detail": "0 deploy-qualified (target ≥1)",
            }
        )

    rr_rows = _pick_rr_table_rows(playbook_rows, limit=5)
    poor_rr = [
        r
        for r in rr_rows
        if isinstance(r.get("risk_reward"), (int, float))
        and float(r["risk_reward"]) < 2.5
    ]
    if rr_rows:
        n += 1
        rr_detail = (
            f"{len(poor_rr)}/{len(rr_rows)} top monitor/avoid names below R:R 2.5"
            if poor_rr
            else f"Top {len(rr_rows)} names on board — see R:R table"
        )
        hard_gates.append(
            {
                "n": n,
                "key": "rr_quality",
                "label": "R:R quality on top names · 風險回報",
                "detail": rr_detail,
            }
        )

    repair = str(system_state.get("repair_priority") or "")
    monitors = list(monitor_tickers or state.get("dashboard_monitors") or [])
    if not monitors:
        for row in playbook_rows:
            act = _norm_action(row)
            if act in _WATCH_ACTIONS and row.get("ticker"):
                monitors.append(str(row["ticker"]).upper())
            if len(monitors) >= 3:
                break

    what_to_do = _what_to_do_now(
        decision_authority=decision_authority,
        todays_decision=todays_decision,
        monitor_tickers=monitors,
        repair_priority=repair,
    )
    unlock = _unlock_checklist(
        unlock_deploy,
        tradeability=tradeability,
        deploy_count=deploy_count,
        execution_readiness=execution_readiness or state.get("execution_readiness"),
    )
    plain = _plain_english_read(
        deploy_count=deploy_count,
        tradeability=tradeability,
        should_trade=should_trade,
        no_setup_diagnosis=no_setup_diagnosis,
        regime_wait_explanation=regime_wait_explanation,
        playbook_rows=playbook_rows,
    )
    note = _best_concise_note(
        decision_code=decision_code,
        tradeability=tradeability,
        deploy_count=deploy_count,
        gates_active=gates_active,
    )

    payload = {
        "decision_code": decision_code,
        "decision_line": decision_line,
        "hard_gates_blocking": hard_gates,
        "rr_quality_table": rr_rows,
        "plain_english_read": plain,
        "what_to_do_now": what_to_do,
        "unlock_checklist": unlock,
        "best_concise_note": note,
        "deploy_qualified_count": deploy_count,
        "gates_active": gates_active,
        "deploy_open": deploy_open,
        "tradeability": tradeability,
        "as_of": as_of or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    payload["text"] = format_bdr_summary_text(payload)
    return payload


def build_bdr_from_today_payload(
    today: Dict[str, Any], *, ops: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Convenience wrapper for /api/v7/today-shaped payloads."""
    state = {
        "market_regime": today.get("market_regime") or {},
        "cc_state": today.get("cc_state") or {},
        "system_state": today.get("system_state") or {},
        "decision_authority": today.get("decision_authority") or {},
        "execution_readiness": today.get("execution_readiness") or {},
        "dashboard_monitors": today.get("dashboard_monitors") or [],
        "deploy_qualified_count": (today.get("filter_funnel") or {}).get(
            "execution_ready_setups"
        ),
    }
    ex = today.get("execution_readiness") or {}
    ibkr_status = {
        "connected": ex.get("ibkr_connected") or ex.get("broker_connected"),
        "gateway_reachable": ex.get("gateway_reachable"),
    }
    return build_bdr_operator_summary(
        state,
        list(today.get("top_5") or today.get("opportunities") or []),
        ibkr_status=ibkr_status,
        ops=ops,
        unlock_deploy=today.get("unlock_deploy"),
        todays_decision=today.get("todays_decision"),
        no_setup_diagnosis=today.get("no_setup_diagnosis"),
        regime_wait_explanation=today.get("regime_wait_explanation"),
        execution_readiness=ex,
        monitor_tickers=today.get("dashboard_monitors"),
        as_of=today.get("generated_at"),
    )
