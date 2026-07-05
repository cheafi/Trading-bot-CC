"""
Daily trading mode — practical deploy/pilot/paper paths without faking authority.

CC_DAILY_TRADING_MODE=1 (default ON in development) lowers council thresholds and
enables selective board gate + paper deploy when broker is offline but data is fresh.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from src.services.cc_perf_cache import env_float
from src.utils.numeric_parse import parse_ratio

TIER_ALLOWED = "allowed"
TIER_PAPER_ONLY = "paper_only"
TIER_PILOT_ONLY = "pilot_only"
TIER_BLOCKED = "blocked"

_STRICT_SCORE = 7.5
_STRICT_CONF = 0.60
_STRICT_RR = 2.0

_DAILY_SCORE = 7.0
_DAILY_CONF = 0.55
_DAILY_RR = 1.8

_PILOT_GRADES = frozenset({"B+", "B"})
_DISPLAY_GRADES = frozenset({"A+", "A", "A-", "B+", "B"})
_DISPLAY_RR_MIN = 1.5
_DISPLAY_SCORE_MIN = 6.5
_AVOID = frozenset({"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE", "BLOCKED"})
_TRADE_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"})


def is_daily_trading_mode() -> bool:
    raw = os.environ.get("CC_DAILY_TRADING_MODE", "").strip()
    if raw:
        return raw.lower() in ("1", "true", "yes", "on")
    app_env = os.environ.get("APP_ENV", "development").strip().lower()
    return app_env in ("development", "dev", "local")


def default_authority_mode() -> str:
    return os.environ.get("CC_DEFAULT_AUTHORITY", "paper_first").strip().lower()


def is_paper_first_authority() -> bool:
    mode = default_authority_mode()
    return mode in ("paper_first", "paper", "paper-only", "paper_only")


def top_monitor_display_count() -> int:
    try:
        return max(3, min(20, int(os.environ.get("CC_TOP_MONITOR_COUNT", "10"))))
    except (TypeError, ValueError):
        return 10


def _norm_action(row: Dict[str, Any]) -> str:
    return str(row.get("effective_action") or row.get("action") or "WATCH").upper().strip()


def _row_score(row: Dict[str, Any]) -> float:
    try:
        return float(row.get("score") or 0)
    except (TypeError, ValueError):
        return 0.0


def _row_rr(row: Dict[str, Any]) -> float:
    return parse_ratio(row.get("risk_reward"), 0.0) or 0.0


def is_trade_display_qualified(
    row: Dict[str, Any],
    *,
    regime_state: str = "WAIT",
) -> bool:
    """Display-only — structure B or better + R:R≥1.5; not deploy authority."""
    if _norm_action(row) in _AVOID:
        return False
    if str(regime_state or "").upper() == "NO_TRADE":
        return False
    grade = str(row.get("grade") or "").upper().strip()
    score = _row_score(row)
    structure_ok = grade in _DISPLAY_GRADES or score >= _DISPLAY_SCORE_MIN
    if not structure_ok:
        return False
    rr = _row_rr(row)
    if rr > 0 and rr < _DISPLAY_RR_MIN:
        return False
    return bool(row.get("ticker"))


def is_actionable_today_row(
    row: Dict[str, Any],
    *,
    regime_state: str = "WAIT",
    deploy_authority: bool = False,
) -> bool:
    """Trade-qualified, pilot-qualified, or display-qualified — never rejected."""
    if _norm_action(row) in _AVOID:
        return False
    if str(regime_state or "").upper() == "NO_TRADE":
        return False
    act = _norm_action(row)
    if deploy_authority and bool(row.get("execution_ready")) and act in _TRADE_ACTIONS:
        return True
    if act == "PILOT":
        return True
    if is_daily_pilot_row(row, regime_state=regime_state):
        return True
    try:
        from src.services.qualification_levels import _row_trade_qualified

        if _row_trade_qualified(row):
            return True
    except Exception:
        pass
    if act in _TRADE_ACTIONS and is_trade_display_qualified(row, regime_state=regime_state):
        return True
    return is_trade_display_qualified(row, regime_state=regime_state)


def _sizing_hint(row: Dict[str, Any], *, pilot: bool = False) -> str:
    entry = float(row.get("entry_price") or row.get("entry") or 0)
    stop = float(row.get("stop_price") or row.get("stop") or 0)
    if entry > 0 and stop > 0 and entry > stop:
        risk_pct = abs(entry - stop) / entry * 100.0
        if risk_pct > 0:
            size = min(10.0, max(0.1, 100.0 / risk_pct))
            label = "½ pilot" if pilot else "1R"
            return f"~{size:.1f}% equity ({label})"
    return "½ pilot or 1R when broker ready" if pilot else "~1R equity when levels confirm"


def _actionable_action_label(
    row: Dict[str, Any],
    *,
    deploy_tier: str,
    deploy_authority: bool,
    regime_state: str,
) -> str:
    act = _norm_action(row)
    if deploy_authority and bool(row.get("execution_ready")) and act in _TRADE_ACTIONS:
        return "LIVE BUY" if deploy_tier == "allowed" else "PAPER BUY"
    if act == "PILOT" or is_daily_pilot_row(row, regime_state=regime_state):
        return "PILOT"
    if deploy_tier == "paper_only":
        return "PAPER BUY"
    return "PAPER BUY" if act in _TRADE_ACTIONS else "PILOT"


def build_actionable_today_card(
    row: Dict[str, Any],
    *,
    deploy_tier: str = TIER_BLOCKED,
    deploy_authority: bool = False,
    broker_offline: bool = False,
    regime_state: str = "WAIT",
) -> Dict[str, Any]:
    from src.services.position_sizing import (
        sanitize_sizing_for_authority,
        suggest_position_size,
    )

    pilot = _actionable_action_label(
        row,
        deploy_tier=deploy_tier,
        deploy_authority=deploy_authority,
        regime_state=regime_state,
    ) == "PILOT"
    entry = float(row.get("entry_price") or 0)
    stop = float(row.get("stop_price") or 0)
    target = float(row.get("target_price") or 0)
    rr = _row_rr(row)
    truth = {
        "deploy_authority": deploy_authority,
        "deploy_authority_tier": deploy_tier,
        "regime_state": regime_state,
        "broker_freshness": "offline" if broker_offline else "fresh",
    }
    sizing = sanitize_sizing_for_authority(
        suggest_position_size(row, truth),
        truth,
        row,
    )
    return {
        "ticker": str(row.get("ticker") or "").upper(),
        "action": pilot and "PILOT" or "PAPER BUY",
        "action_label": _actionable_action_label(
            row,
            deploy_tier=deploy_tier,
            deploy_authority=deploy_authority,
            regime_state=regime_state,
        ),
        "grade": str(row.get("grade") or ""),
        "score": _row_score(row),
        "entry_price": entry,
        "stop_price": stop,
        "target_price": target,
        "entry_zone": (
            f"${entry:.2f}" if entry > 0 else "confirm in Dossier"
        ),
        "risk_reward": rr,
        "risk_reward_label": f"{rr:.1f}" if rr > 0 else "—",
        "sizing_hint": _sizing_hint(row, pilot=pilot),
        "sizing": sizing,
        "execution_ready": bool(row.get("execution_ready")),
        "paper_draft_enabled": deploy_tier in (TIER_PAPER_ONLY, TIER_PILOT_ONLY, TIER_ALLOWED),
        "ibkr_handoff_enabled": (
            deploy_tier == TIER_ALLOWED
            and not broker_offline
            and bool(row.get("execution_ready"))
        ),
        "display_qualified": is_trade_display_qualified(row, regime_state=regime_state),
        "primary_bucket": row.get("primary_bucket") or "",
    }


def build_actionable_today(
    rows: Optional[List[Dict[str, Any]]],
    *,
    system_truth: Optional[Dict[str, Any]] = None,
    near_miss: Optional[List[Dict[str, Any]]] = None,
    limit: int = 3,
) -> Dict[str, Any]:
    """Top actionable names for Dashboard — separate from deploy authority."""
    truth = system_truth or {}
    regime = str(truth.get("regime_state") or "WAIT").upper()
    tier = str(truth.get("deploy_authority_tier") or TIER_BLOCKED)
    deploy_auth = bool(truth.get("deploy_authority"))
    broker_off = str(truth.get("broker_freshness") or "offline").lower() in (
        "offline",
        "blocked",
    )
    pool: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for source in (rows or [], near_miss or []):
        for row in source:
            tk = str(row.get("ticker") or "").upper()
            if not tk or tk in seen:
                continue
            if not is_actionable_today_row(
                row,
                regime_state=regime,
                deploy_authority=deploy_auth,
            ):
                continue
            seen.add(tk)
            pool.append(row)
    pool.sort(
        key=lambda r: (
            0 if bool(r.get("execution_ready")) else 1,
            0 if _norm_action(r) in _TRADE_ACTIONS else 1,
            -_row_score(r),
            -_row_rr(r),
        )
    )
    cards = [
        build_actionable_today_card(
            row,
            deploy_tier=tier,
            deploy_authority=deploy_auth,
            broker_offline=broker_off,
            regime_state=regime,
        )
        for row in pool[: max(1, int(limit))]
    ]
    empty_reason = ""
    if not cards:
        if regime == "NO_TRADE":
            empty_reason = "Regime NO_TRADE — no new risk today"
        elif truth.get("brief_freshness") in ("expired", "fallback"):
            empty_reason = "Brief expired or fallback — board not actionable"
        elif truth.get("ranked_board_freshness") in ("stale", "fallback", "unavailable"):
            empty_reason = "Ranked board stale — refresh scanner"
        elif not pool and not (rows or near_miss):
            empty_reason = "Scanner returned zero candidates — check engine / CC_LIVE_DATA_ONLY"
        else:
            empty_reason = "No names pass structure + R:R display gates today"
    return {
        "title": "今日可執行 · Actionable Today",
        "title_zh": "今日可試",
        "cards": cards,
        "count": len(cards),
        "empty": not bool(cards),
        "empty_reason": empty_reason,
        "empty_reason_zh": (
            "今日無可執行標的 — " + empty_reason if empty_reason else ""
        ),
        "paper_only_badge": tier == TIER_PAPER_ONLY,
        "broker_offline": broker_off,
        "deploy_tier": tier,
        "monitor_display_limit": top_monitor_display_count(),
    }


def ensure_minimum_board_rows(
    top5: List[Dict[str, Any]],
    all_rows: List[Dict[str, Any]],
    *,
    min_score: float = 6.0,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    """Backfill top_5 when council filtered all but scanner has score>min_score."""
    if top5:
        return top5
    backfill: List[Dict[str, Any]] = []
    for row in all_rows or []:
        if _norm_action(row) in _AVOID:
            continue
        if _row_score(row) <= min_score:
            continue
        backfill.append(row)
    backfill.sort(key=lambda r: (-_row_score(r), -_row_rr(r)))
    return backfill[:limit]


def council_deploy_score_default() -> float:
    return _DAILY_SCORE if is_daily_trading_mode() else _STRICT_SCORE


def council_deploy_conf_default() -> float:
    return _DAILY_CONF if is_daily_trading_mode() else _STRICT_CONF


def council_deploy_rr_default() -> float:
    return _DAILY_RR if is_daily_trading_mode() else _STRICT_RR


def council_deploy_score_min() -> float:
    return env_float("CC_COUNCIL_DEPLOY_SCORE_MIN", council_deploy_score_default())


def council_deploy_conf_min() -> float:
    return env_float("CC_COUNCIL_DEPLOY_CONF_MIN", council_deploy_conf_default())


def council_deploy_rr_min() -> float:
    return env_float("CC_COUNCIL_DEPLOY_RR_MIN", council_deploy_rr_default())


def board_data_blocks_deploy(
    *,
    brief_freshness: str,
    ranked_board_freshness: str,
    market_data_freshness: str = "fresh",
    scanner_degraded: bool = False,
) -> bool:
    if brief_freshness in ("expired", "fallback"):
        return True
    if ranked_board_freshness in ("stale", "fallback", "unavailable"):
        return True
    if market_data_freshness in ("unavailable", "stale") and scanner_degraded:
        return True
    return False


def resolve_board_gate(
    regime_state: str,
    *,
    brief_freshness: str = "fresh",
    ranked_board_freshness: str = "fresh",
    market_data_freshness: str = "fresh",
    scanner_degraded: bool = False,
) -> str:
    """open | selective | wait | closed — selective only in daily mode on fresh data."""
    regime = str(regime_state or "WAIT").upper()
    if regime == "NO_TRADE":
        return "closed"
    stale = board_data_blocks_deploy(
        brief_freshness=brief_freshness,
        ranked_board_freshness=ranked_board_freshness,
        market_data_freshness=market_data_freshness,
        scanner_degraded=scanner_degraded,
    )
    if is_daily_trading_mode() and not stale:
        if regime in ("TRADE", "STRONG_TRADE"):
            return "open"
        if regime == "SELECTIVE":
            return "selective"
    if regime in ("WAIT", "SELECTIVE"):
        return "wait"
    return "open"


def is_daily_pilot_row(
    row: Dict[str, Any],
    *,
    regime_state: str = "WAIT",
) -> bool:
    """B+ structure + R:R≥1.8 + regime not no_trade — pilot without execution_ready."""
    if not is_daily_trading_mode():
        return False
    if str(regime_state or "").upper() == "NO_TRADE":
        return False
    act = str(row.get("effective_action") or row.get("action") or "WATCH").upper()
    if act in _AVOID:
        return False
    if row.get("execution_ready"):
        return False
    grade = str(row.get("grade") or "").upper().strip()
    try:
        score = float(row.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    b_plus = grade in _PILOT_GRADES or score >= 7.0
    if not b_plus:
        return False
    rr = parse_ratio(row.get("risk_reward"), 0.0) or 0.0
    if rr > 0 and rr < _DAILY_RR:
        return False
    if grade in _PILOT_GRADES:
        return True
    stop = float(row.get("stop_price") or row.get("stop") or 0)
    if stop <= 0 and act not in _PILOT_GRADES and act != "PILOT":
        thesis = float(row.get("thesis_conf") or 0)
        if thesis < 0.50 and score < 7.5:
            return False
    return True


def resolve_deploy_authority_tier(
    today: Dict[str, Any],
    *,
    board_gate: str,
    execution_gate: str,
    brief_freshness: str,
    ranked_board_freshness: str,
    broker_freshness: str,
    market_data_freshness: str,
    regime_state: str,
    trade_qualified: int,
    execution_qualified: int,
    live_deploy_allowed: bool,
) -> str:
    """
    allowed — live handoff when execution-qualified + broker ready.
    paper_only — simulation/paper path when trade-qualified + broker offline + fresh board.
    pilot_only — B+ pilot probe path (half size when broker ready).
    blocked — monitor only.
    """
    if live_deploy_allowed:
        return TIER_ALLOWED

    auth = today.get("decision_authority") or {}
    if auth.get("source") in ("fallback_brief", "stale_cache"):
        return TIER_BLOCKED
    if board_gate == "closed" or str(regime_state or "").upper() == "NO_TRADE":
        return TIER_BLOCKED
    if board_data_blocks_deploy(
        brief_freshness=brief_freshness,
        ranked_board_freshness=ranked_board_freshness,
        market_data_freshness=market_data_freshness,
        scanner_degraded=bool(today.get("scanner_degraded")),
    ):
        return TIER_BLOCKED
    if auth.get("gates_active") and not auth.get("allows_trade_labels"):
        return TIER_BLOCKED
    if auth.get("authority_level") == "suspended":
        return TIER_BLOCKED

    broker_off = broker_freshness in ("offline", "blocked") or execution_gate == "offline"
    if auth.get("authority_level") not in ("deploy", "research") and auth.get("gates_active"):
        return TIER_BLOCKED
    board_ok = board_gate in ("open", "selective", "wait")

    if is_daily_trading_mode() and board_ok:
        if broker_off and trade_qualified >= 1:
            return TIER_PAPER_ONLY
        pilot_n = int(today.get("pilot_eligible_count") or 0)
        if pilot_n >= 1 and board_gate in ("open", "selective"):
            return TIER_PILOT_ONLY
        if execution_qualified >= 1 and not broker_off and execution_gate != "ready":
            return TIER_PILOT_ONLY

    if is_paper_first_authority() and board_ok and broker_off and trade_qualified >= 1:
        if board_data_blocks_deploy(
            brief_freshness=brief_freshness,
            ranked_board_freshness=ranked_board_freshness,
            market_data_freshness=market_data_freshness,
            scanner_degraded=bool(today.get("scanner_degraded")),
        ):
            return TIER_BLOCKED
        return TIER_PAPER_ONLY

    return TIER_BLOCKED


def tier_operator_copy(tier: str, *, broker_offline: bool = False) -> Dict[str, str]:
    """Dashboard operator lines keyed by authority tier."""
    if tier == TIER_ALLOWED:
        return {
            "now": "Deploy available · 可部署",
            "now_en": "Deploy available",
            "allowed": "deploy selectively on qualified names",
            "blocked": "",
            "daily_zh": "今日：可部署",
        }
    if tier == TIER_PAPER_ONLY:
        return {
            "now": "PAPER DEPLOY · 紙上可試 · Paper deploy available",
            "now_en": "Paper deploy available",
            "allowed": "paper drafts, pilot probe, open Playbook — live handoff needs IBKR online",
            "blocked": "no live IBKR handoff while broker offline",
            "daily_zh": "今日：紙上可試 · Paper deploy available",
            "allowed_zh": "可做：建立紙上單、試探 Pilot、開啟 Playbook",
            "blocked_zh": "實盤需：IBKR 在線",
        }
    if tier == TIER_PILOT_ONLY:
        return {
            "now": "Pilot probe allowed · 可試探 Pilot · half size when broker ready",
            "now_en": "Pilot probe allowed — half size when broker ready",
            "allowed": "pilot probe on B+ setups — half size when broker ready",
            "blocked": "no full-size deploy until execution-ready",
            "daily_zh": "今日：可試探 Pilot",
        }
    return {
        "now": "MONITOR ONLY · Deploy blocked",
        "now_en": "MONITOR ONLY · Deploy blocked",
        "allowed": "monitor candidates, create watch rules",
        "blocked": "no sizing, no handoff, no pilot entry",
        "daily_zh": "今日：僅監察",
    }


def format_qualification_counts(
    *,
    setup_qualified: int = 0,
    trade_qualified: int = 0,
    execution_qualified: int = 0,
    deploy_qualified: int = 0,
    paper_qualified: int = 0,
    tier: str = TIER_BLOCKED,
) -> str:
    parts = [
        f"Setup-qualified: {setup_qualified}",
        f"Trade-qualified: {trade_qualified}",
        f"Execution-qualified: {execution_qualified}",
    ]
    if tier == TIER_PAPER_ONLY and paper_qualified > 0:
        parts.append(f"Paper-qualified: {paper_qualified}")
    else:
        parts.append(f"Deploy-qualified: {deploy_qualified}")
    return " · ".join(parts)
