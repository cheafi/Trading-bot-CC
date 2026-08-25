"""Unified SystemState / PageCapability contract for Clarity Console."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_REJECT_ACTIONS = frozenset({"AVOID", "NO_TRADE", "BLOCKED"})
_MONITOR_ACTIONS = frozenset({"WATCH", "PILOT", "MONITOR"})
_DEPLOY_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"})


def format_operator_sentence(
    *,
    now: str,
    blocker: str,
    next_action: str,
    scope: str = "",
) -> Dict[str, str]:
    """Reusable NOW / BLOCKER / NEXT ACTION strip (bilingual line)."""
    now_s = str(now or "").strip()
    blocker_s = str(blocker or "").strip()
    next_s = str(next_action or "").strip()
    return {
        "now": now_s,
        "blocker": blocker_s,
        "next_action": next_s,
        "scope": str(scope or "").strip(),
        "line": " · ".join(
            p
            for p in (
                f"現況 · NOW: {now_s}" if now_s else "",
                f"阻擋 · BLOCKER: {blocker_s}" if blocker_s else "",
                f"下一步 · NEXT: {next_s}" if next_s else "",
            )
            if p
        ),
    }


def _norm_action(row: Dict[str, Any]) -> str:
    return str(row.get("action") or row.get("effective_action") or "WATCH").upper()


def structural_valid_for_monitor(row: Dict[str, Any]) -> bool:
    """Monitor ranking requires non-rejected structural validity."""
    act = _norm_action(row)
    if act in _REJECT_ACTIONS:
        return False
    if row.get("hard_reject") or row.get("ladder_bucket") == "hard_reject":
        return False
    return True


def _near_miss_signals(row: Dict[str, Any]) -> int:
    """Count upgrade proximity signals (need >=2 for near-miss bucket)."""
    hits = 0
    if float(row.get("thesis_conf") or 0) >= 0.55:
        hits += 1
    if float(row.get("timing_conf") or 0) >= 0.5:
        hits += 1
    if float(row.get("vol_ratio") or 0) >= 1.0:
        hits += 1
    if str(row.get("leader") or "").upper() == "LEADER":
        hits += 1
    rr_raw = row.get("risk_reward")
    if rr_raw is not None and rr_raw != "":
        try:
            rr = (
                float(rr_raw)
                if not isinstance(rr_raw, str)
                else float(str(rr_raw).split(":")[0])
            )
            if rr >= 2.0:
                hits += 1
        except (TypeError, ValueError):
            pass
    return hits


def classify_rank_bucket(row: Dict[str, Any]) -> str:
    act = _norm_action(row)
    bucket = str(row.get("ladder_bucket") or "")
    if act in _REJECT_ACTIONS or bucket == "hard_reject":
        return "rejectedAvoid"
    if bucket == "deploy_ready" and row.get("execution_ready"):
        return "deployQualified"
    if act == "PILOT" or bucket == "pilot_ready":
        return "pilotQualified"
    if act in _MONITOR_ACTIONS or bucket == "watch_upgrade":
        return "watchQualified"
    if _near_miss_signals(row) >= 2 and float(row.get("score") or 0) >= 5:
        return "nearMiss"
    if act in _DEPLOY_ACTIONS and not row.get("execution_ready"):
        return "nearMiss"
    if structural_valid_for_monitor(row):
        return "watchQualified"
    return "rejectedAvoid"


def build_playbook_rank_buckets(
    rows: List[Dict[str, Any]],
    near_miss: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Bucket playbook names — AVOID never in monitor ranking."""
    buckets: Dict[str, List[Dict[str, Any]]] = {
        "deployQualified": [],
        "pilotQualified": [],
        "watchQualified": [],
        "nearMiss": [],
        "rejectedAvoid": [],
    }
    seen: set[str] = set()

    def _add(key: str, row: Dict[str, Any]) -> None:
        t = str(row.get("ticker") or "").upper()
        if not t or t in seen:
            return
        seen.add(t)
        buckets[key].append(row)

    for row in rows:
        key = classify_rank_bucket(row)
        _add(key, row)

    for row in near_miss or []:
        t = str(row.get("ticker") or "").upper()
        if not t or t in seen:
            continue
        if _norm_action(row) in _REJECT_ACTIONS:
            _add("rejectedAvoid", row)
        else:
            _add("nearMiss", row)
            seen.add(t)

    monitor_valid = buckets["watchQualified"] + buckets["nearMiss"]
    return {
        "buckets": buckets,
        "monitor_rows": monitor_valid[:12],
        "monitor_section_label": (
            "Monitor ranking" if monitor_valid else "No valid monitor candidates"
        ),
        "rejected_section_label": "Rejected / Avoid — not monitor priority",
        "has_valid_monitors": bool(monitor_valid),
        "counts": {k: len(v) for k, v in buckets.items()},
    }


def pick_dashboard_monitors(
    *,
    watch_qualified: List[Dict[str, Any]],
    near_miss: List[Dict[str, Any]],
    top_ranked: List[Dict[str, Any]],
    limit: int = 3,
) -> List[str]:
    """Dashboard top monitors: watchQualified → nearMiss, never rejectedAvoid."""
    out: List[str] = []

    def _take(pool: List[Dict[str, Any]]) -> None:
        for row in pool:
            if len(out) >= limit:
                return
            if not structural_valid_for_monitor(row):
                continue
            t = str(row.get("ticker") or "").upper()
            if t and t not in out:
                out.append(t)

    _take(watch_qualified)
    _take(near_miss)
    if len(out) < limit:
        for row in top_ranked:
            if len(out) >= limit:
                break
            if structural_valid_for_monitor(row):
                t = str(row.get("ticker") or "").upper()
                if t and t not in out:
                    out.append(t)
    return out[:limit]


_TAB_ALIASES: Dict[str, str] = {
    "today": "today",
    "signals": "signals",
    "scanners": "scanners",
    "discovery": "scanners",
    "dossier": "dossier",
    "stock-intel": "dossier",
    "flow": "flow",
    "funds": "funds",
    "rs": "scanners",
    "command": "scanners",
    "notrade": "scanners",
    "rejections": "scanners",
    "guide": "guide",
    "ops": "ops",
    "ibkr": "ibkr",
    "btlab": "btlab",
    "backtest": "btlab",
    "agent": "agent",
    "strategy-lab": "strategy-lab",
    "strategylab": "strategy-lab",
    "shadow": "shadow",
    "reports": "reports",
    "portfolio": "portfolio",
}


def resolve_tab_id(tab: Optional[str]) -> str:
    """Map UI tab id to PageCapability tab key."""
    key = str(tab or "today").strip().lower()
    return _TAB_ALIASES.get(key, key if key in _TAB_ALIASES.values() else "today")


def _compact_blocker_parts(
    *,
    tradeability: str,
    data_tier: str,
    broker_state: str,
    fallback_mode: bool,
) -> str:
    parts: List[str] = []
    tb = str(tradeability or "WAIT").upper()
    if tb in ("WAIT", "NO_TRADE"):
        parts.append(f"{tb} board gate")
    if data_tier in ("STALE", "CRITICAL"):
        parts.append("資料過期")
    if broker_state in (
        "GATEWAY_DOWN",
        "IBAPI_MISSING",
        "SESSION_INACTIVE",
        "DISCONNECTED",
        "ENGINE_OFF",
        "EXEC_BLOCKED",
        "HANDOFF_BLOCKED",
    ):
        parts.append(
            "IBKR 離線 · broker offline"
            if "GATEWAY" in broker_state
            or "IB" in broker_state
            or broker_state == "DISCONNECTED"
            else "執行受阻 · execution blocked"
        )
    if fallback_mode:
        parts.append("brief 後備 · brief fallback")
    if parts:
        return " + ".join(parts) + "，部署權限暫停"
    return "部署權限暫停"


def _repair_priority(
    *,
    broker_state: str,
    data_tier: str,
    engine_running: bool,
) -> str:
    if data_tier in ("STALE", "CRITICAL"):
        return "修復市場資料新鮮度 · repair market data freshness"
    if broker_state in (
        "GATEWAY_DOWN",
        "IBAPI_MISSING",
        "SESSION_INACTIVE",
        "DISCONNECTED",
    ):
        return "恢復 IBKR 連線 · restore IBKR session"
    if not engine_running:
        return "啟動引擎（Ops）· start engine (Ops)"
    if broker_state in ("ENGINE_OFF", "EXEC_BLOCKED", "HANDOFF_BLOCKED"):
        return "清除執行阻擋（Ops／IBKR）· clear execution blockers"
    return "重新整理儀表板＋策略簿 · refresh Dashboard + Playbook"


def build_system_state(
    *,
    tradeability: str,
    should_trade: bool,
    cc_state: Optional[Dict[str, Any]] = None,
    execution_readiness: Optional[Dict[str, Any]] = None,
    trust: Optional[Dict[str, Any]] = None,
    decision_authority: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Global system state — shown once in header strip."""
    da = decision_authority or {}
    cs = cc_state or {}
    trust_obj = trust if isinstance(trust, dict) else {}
    fs = cs.get("freshness_state") or {}
    es = cs.get("execution_state") or {}

    tb = str(tradeability or "WAIT").upper()
    data_tier = str(
        fs.get("worst_tier") or ("STALE" if trust_obj.get("stale") else "FRESH")
    )
    broker_state = str(es.get("state") or "")
    engine_running = bool(es.get("engine_running"))
    board_src = str(fs.get("board_source") or da.get("source") or "")
    fallback_mode = board_src in ("fallback_brief", "stale_cache") or bool(
        da.get("degraded")
    )
    deploy_open = (
        tb not in ("WAIT", "NO_TRADE")
        and bool(should_trade)
        and str((cs.get("board_decision_state") or {}).get("state") or "") == "DEPLOY"
        and not bool(da.get("gates_active"))
    )

    blocker_compact = _compact_blocker_parts(
        tradeability=tb,
        data_tier=data_tier,
        broker_state=broker_state,
        fallback_mode=fallback_mode,
    )
    repair = _repair_priority(
        broker_state=broker_state,
        data_tier=data_tier,
        engine_running=engine_running,
    )

    if deploy_open:
        now = f"今日狀態：{tb} · 部署閘門可能開啟 · deploy gate may be open"
        next_action = (
            "確認 Playbook deploy-qualified 後才 sizing · verify before sizing"
        )
    elif tb in ("WAIT", "NO_TRADE"):
        now = f"今日狀態：{tb} · 只可監察"
        next_action = f"只跟進 monitor queue；先 {repair}"
    else:
        now = f"今日狀態：{tb} · 監控時段 · monitor session"
        next_action = f"閘門解除前僅研究 · research only until gates clear；{repair}"

    authority = (
        "deploy" if deploy_open else "monitor_only" if tb == "WAIT" else "research_only"
    )

    return {
        "regime": tb,
        "tradeability": tb,
        "data_freshness": data_tier,
        "engine_state": "ON" if engine_running else "OFF",
        "broker_state": broker_state or "UNKNOWN",
        "board_mode": board_src or "live",
        "authority": authority,
        "fallback_mode": fallback_mode,
        "deploy_open": deploy_open,
        "global_strip_active": not deploy_open or fallback_mode or data_tier != "FRESH",
        "blocker_compact": blocker_compact,
        "repair_priority": repair,
        "operator_sentence": format_operator_sentence(
            now=now,
            blocker=f"原因：{blocker_compact}",
            next_action=f"下一步：{next_action}",
            scope="global",
        ),
        "chips": [
            {"label": tb, "class": "tradeability"},
            {
                "label": f"DATA {data_tier}",
                "class": "data" if data_tier == "FRESH" else "warn",
            },
            {"label": broker_state.replace("_", " "), "class": "broker"},
            {
                "label": "ENGINE ON" if engine_running else "ENGINE OFF",
                "class": "engine",
            },
        ],
    }


def build_page_capability(
    tab: str,
    *,
    system_state: Dict[str, Any],
    fetch_state: str = "ok",
    mock_only: bool = False,
) -> Dict[str, Any]:
    """Per-page capability contract — one-line blocked reason max."""
    tb = str(system_state.get("tradeability") or "WAIT").upper()
    deploy_open = bool(system_state.get("deploy_open"))
    degraded = bool(system_state.get("fallback_mode")) or str(
        system_state.get("data_freshness") or ""
    ) in ("STALE", "CRITICAL")
    broker_bad = str(system_state.get("broker_state") or "") not in (
        "",
        "CONNECTED",
        "HANDOFF_READY",
        "BRACKET_READY",
    )

    can_deploy = deploy_open and tab in ("today", "signals")
    can_monitor = tab in ("today", "signals")
    can_research = tab in (
        "scanners",
        "flow",
        "funds",
        "rs",
        "command",
        "notrade",
        "agent",
        "strategy-lab",
        "shadow",
        "reports",
    )
    can_confirm = tab == "dossier"
    can_size = can_deploy and not degraded and not broker_bad
    can_handoff = can_deploy and not broker_bad
    can_cached = degraded or fetch_state in (
        "fallback",
        "failed_fetch_fallback",
        "stale",
    )

    blocked = system_state.get("blocker_compact") or "閘門生效 · gates active"
    primary = (
        system_state.get("repair_priority") or "重新整理即時資料 · refresh live data"
    )

    tab_key = resolve_tab_id(tab)
    sentences: Dict[str, Dict[str, str]] = {
        "today": format_operator_sentence(
            now=f"今日狀態：{tb} · {'只可監察' if not can_deploy else 'board review'}",
            blocker=blocked,
            next_action=f"{'只跟進 monitor queue' if not can_deploy else 'deploy review'}；{primary}",
            scope="dashboard",
        ),
        "signals": format_operator_sentence(
            now="無可部署名單 · No deploy names"
            if not can_deploy
            else "Deploy review · 可檢視 deploy-qualified",
            blocker=f"board gate {tb} + 0 deploy-qualified"
            if not can_deploy
            else "verify execution readiness",
            next_action="只追蹤 near-miss upgrade candidates"
            if not can_deploy
            else "size only deploy-qualified",
            scope="playbook",
        ),
        "scanners": format_operator_sentence(
            now="Scanner unavailable · 掃描暫不可用"
            if fetch_state == "failed_fetch"
            else "Discovery research · 研究模式",
            blocker="API fetch failed" if fetch_state == "failed_fetch" else blocked,
            next_action="用 cached leaders 或 retry scan"
            if can_cached
            else "run live scan",
            scope="discovery",
        ),
        "dossier": format_operator_sentence(
            now="Structure confirm · 結構確認",
            blocker=blocked,
            next_action="review levels; no handoff until gates open",
            scope="dossier",
        ),
        "flow": format_operator_sentence(
            now="Flow unavailable / mock · Flow 暫不可用",
            blocker="live provider not connected" if mock_only else blocked,
            next_action="Ignore flow today · 今日忽略 flow"
            if mock_only
            else "confirm in Playbook only",
            scope="flow",
        ),
        "funds": format_operator_sentence(
            now="Allocation blocked · 配置暫停"
            if degraded or fetch_state == "failed_fetch"
            else "Funds research · 研究模式",
            blocker="live fund/index posture unavailable"
            if fetch_state == "failed_fetch"
            else (blocked if degraded else "await live fund data"),
            next_action="no sleeve allocation today; repair market data first"
            if degraded or fetch_state == "failed_fetch"
            else "index/core posture only",
            scope="funds",
        ),
        "guide": format_operator_sentence(
            now="Reference manual · 參考手冊",
            blocker="",
            next_action="Dashboard → Playbook → Dossier daily flow",
            scope="guide",
        ),
        "agent": format_operator_sentence(
            now="Vibe Agent · 熬夜盯盤副駕 · Research / Monitoring only",
            blocker=blocked,
            next_action="Review alerts → confirm in Playbook → check Dossier",
            scope="agent",
        ),
        "strategy-lab": format_operator_sentence(
            now="Strategy Lab · 策略實驗室 · draft + validation",
            blocker=blocked,
            next_action="Generate draft → validate → watch rule → Playbook review",
            scope="strategy-lab",
        ),
        "shadow": format_operator_sentence(
            now="Shadow Account · 影子帳戶 · behavior diagnostics",
            blocker=blocked,
            next_action="Compare actual vs rule path; improve watch rules",
            scope="shadow",
        ),
        "reports": format_operator_sentence(
            now="Reports · 報告庫 · inspectable research runs",
            blocker=blocked,
            next_action="匯出 MD/JSON；行動前於 Playbook 確認 · Export MD/JSON; confirm in Playbook",
            scope="reports",
        ),
        "portfolio": format_operator_sentence(
            now="持倉與風險 · Portfolio & risk",
            blocker=blocked
            if not can_deploy
            else "sizing 需閘門開啟 · sizing needs open gates",
            next_action="檢視止損／熱度；新倉僅 monitor · review stops/heat; new entries monitor-only"
            if not can_deploy
            else "依 deploy-qualified 調整部位 · size per deploy-qualified",
            scope="portfolio",
        ),
        "ops": format_operator_sentence(
            now="運維 · Ops · health / engine / alerts",
            blocker=blocked,
            next_action="檢查 /health、引擎、Discord；非部署權限 · check health, engine, Discord",
            scope="ops",
        ),
        "ibkr": format_operator_sentence(
            now="IBKR · 券商連線與交付",
            blocker=blocked
            if broker_bad
            else "登入後確認 handoff ladder · login then verify handoff",
            next_action="Gateway → Session → Bracket → Handoff · 逐步確認交付梯",
            scope="ibkr",
        ),
        "btlab": format_operator_sentence(
            now="回測室 · Backtest Lab · historical simulation",
            blocker="回測通過 ≠ 交易許可 · backtest pass ≠ trade permission",
            next_action="只作研究；確認請回 Playbook · research only; confirm in Playbook",
            scope="btlab",
        ),
    }
    sentence = sentences.get(tab_key) or sentences.get("today", {})

    warning_level = "none"
    if fetch_state in ("failed_fetch", "mock_only") or mock_only:
        warning_level = "red"
    elif degraded or not can_deploy:
        warning_level = "amber"

    surface_types = {
        "today": "deploy_authority",
        "signals": "deploy_authority",
        "scanners": "research",
        "dossier": "confirm_structure",
        "flow": "research",
        "funds": "research",
        "guide": "reference",
        "agent": "research_monitoring",
        "strategy-lab": "research_monitoring",
        "shadow": "research_monitoring",
        "reports": "research_monitoring",
        "portfolio": "deploy_authority",
        "ops": "reference",
        "ibkr": "execution_dependent",
        "btlab": "research",
    }
    return {
        "page_id": tab_key,
        "tab": tab_key,
        "surface_type": surface_types.get(tab_key, "research"),
        "can_deploy": can_deploy,
        "can_monitor": can_monitor,
        "can_research": can_research,
        "can_confirm_structure": can_confirm,
        "can_size": can_size,
        "can_handoff": can_handoff,
        "can_use_cached": can_cached,
        "visible_warning_level": warning_level,
        "primary_action": sentence.get("next_action") or primary,
        "blocked_reason_compact": blocked if not can_deploy else "",
        "operator_sentence": sentence,
        "research_only_once": can_research and not can_deploy,
    }
