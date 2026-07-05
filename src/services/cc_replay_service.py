"""Whole-console Time Travel replay — historical brief snapshots for CC."""

from __future__ import annotations

import glob
import json
import os
import re
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

DATE_RX = re.compile(r"^(\d{4}-\d{2}-\d{2})$")
BRIEF_FILE_RX = re.compile(r"brief-(\d{4}-\d{2}-\d{2})\.json$")


class ReplaySnapshotError(ValueError):
    """Raised when no brief snapshot exists for the requested replay date."""

    def __init__(
        self,
        message: str,
        *,
        available_dates: Optional[List[str]] = None,
        requested: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self.available_dates = available_dates or []
        self.requested = requested


def _brief_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "data")


def list_replay_dates() -> List[str]:
    """All brief-YYYY-MM-DD.json dates, newest first."""
    dates: List[str] = []
    for path in glob.glob(os.path.join(_brief_dir(), "brief-*.json")):
        match = BRIEF_FILE_RX.search(os.path.basename(path))
        if match:
            dates.append(match.group(1))
    return sorted(dates, reverse=True)


def resolve_brief_for_as_of(
    as_of: str,
) -> Tuple[str, Dict[str, Any], Optional[str]]:
    """Resolve exact or nearest-prior brief snapshot for ``as_of`` (YYYY-MM-DD)."""
    requested = (as_of or "").strip()
    if not DATE_RX.match(requested):
        raise ReplaySnapshotError(
            "Invalid date — use YYYY-MM-DD",
            requested=requested,
            available_dates=list_replay_dates(),
        )

    available = list_replay_dates()
    if not available:
        raise ReplaySnapshotError(
            "該日期無快照 — 請選擇有 Brief 的日期",
            requested=requested,
            available_dates=[],
        )

    exact_path = os.path.join(_brief_dir(), f"brief-{requested}.json")
    if os.path.isfile(exact_path):
        with open(exact_path, encoding="utf-8") as handle:
            return requested, json.load(handle), None

    target = date.fromisoformat(requested)
    prior = sorted(
        [d for d in available if date.fromisoformat(d) <= target],
        key=lambda d: date.fromisoformat(d),
    )
    if not prior:
        earliest = available[-1]
        raise ReplaySnapshotError(
            f"該日期無快照 — 請選擇有 Brief 的日期（最早：{earliest}）",
            requested=requested,
            available_dates=available,
        )

    resolved = prior[-1]
    path = os.path.join(_brief_dir(), f"brief-{resolved}.json")
    with open(path, encoding="utf-8") as handle:
        brief = json.load(handle)
    note = f"使用最近快照 {resolved}（請求 {requested}）"
    return resolved, brief, note


def replay_snapshot_error_detail(exc: ReplaySnapshotError) -> Dict[str, Any]:
    return {
        "error": str(exc),
        "available_dates": exc.available_dates or list_replay_dates(),
        "requested": exc.requested,
        "replay_mode": True,
    }


def _replay_system_truth(resolved: str, *, note: Optional[str] = None) -> Dict[str, Any]:
    banner = f"Replay: {resolved} · 全頁歷史狀態（非即時）"
    if note:
        banner = f"{banner} · {note}"
    return {
        "deploy_authority": False,
        "regime_state": "REPLAY",
        "primary_blocker": "Replay mode · 僅供回測檢視",
        "operator_sentence": f"Replay {resolved} — historical console only — Allowed: monitor only — 0 deploy-qualified",
        "replay_mode": True,
        "replay_as_of": resolved,
        "research_only": True,
        "truth_strip": f"{banner} · Authority: Blocked",
        "market_data_freshness": "historical",
        "ranked_board_freshness": "historical",
        "brief_freshness": "historical",
        "broker_freshness": "offline",
        "runtime_freshness": "replay",
        "runtime_state": "replay",
        "engine_state": "off",
        "deploy_qualified_count": 0,
        "reason_codes": ["replay_mode"],
        "reason_copy": ["Replay mode · 僅供回測檢視 — no deploy, no handoff"],
    }


def _replay_decision_authority(resolved: str) -> Dict[str, Any]:
    return {
        "deploy_authority": False,
        "research_only": True,
        "replay_mode": True,
        "blocked_reason": "Replay mode · 僅供回測檢視",
        "source": "replay-brief",
        "gates": {"replay_mode": True, "deploy": False, "handoff": False},
        "gates_active": True,
        "degraded": False,
        "as_of": resolved,
    }


def _brief_rows_to_top5(opps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from src.services.decision_truth_model import assemble_confidence_breakdown

    top5: List[Dict[str, Any]] = []
    for index, row in enumerate(opps[:5]):
        why = row.get("why_now")
        base: Dict[str, Any] = {
            "rank": index + 1,
            "ticker": row.get("ticker"),
            "strategy": row.get("setup") or "brief_watch",
            "score": row.get("score", 0),
            "grade": row.get("grade", "C"),
            "timing": "Developing",
            "action": "WATCH",
            "raw_action": row.get("action") or "WATCH",
            "action_reason": (
                "Replay brief snapshot — reference plan only · indicative levels · "
                "monitor zone · no deploy authority"
            ),
            "why_now": [why] if isinstance(why, str) and why else (why or []),
            "entry_price": row.get("entry_price"),
            "target_price": row.get("target_price"),
            "stop_price": row.get("stop_price"),
            "risk_reward": row.get("risk_reward"),
            "invalidation": row.get("invalidation"),
            "execution_ready": False,
            "confidence_fallback_only": True,
            "card_display_mode": "reference_only",
            "levels_indicative_only": True,
            "deploy_authority": False,
            "monitor_zone_only": True,
            "evidence_badge": row.get("evidence_badge") or "replay-brief",
            "thesis_conf": 0,
            "timing_conf": 0,
            "exec_conf": 0,
            "data_conf": 0,
        }
        conf = assemble_confidence_breakdown(base)
        base["confidence_breakdown"] = conf
        base["final_conf"] = conf.get("final")
        top5.append(base)
    return top5


def build_replay_today_payload(as_of: str) -> Dict[str, Any]:
    """Build /api/v7/today payload from a dated morning brief snapshot."""
    resolved, brief, note = resolve_brief_for_as_of(as_of)
    from src.services.playbook_board_fallback import build_compressed_fallback

    fallback = build_compressed_fallback(
        30,
        brief=brief,
        reason=f"replay as_of={resolved}",
    )
    opps = fallback.get("opportunities") or []
    near_miss = fallback.get("near_miss") or []
    top5 = _brief_rows_to_top5(opps)
    generated_at = str(
        brief.get("generated_at") or f"{resolved}T12:00:00Z"
    ).replace("+00:00", "Z")
    system_truth = _replay_system_truth(resolved, note=note)
    narrative = (
        f"重播模式 · Replay: {resolved} · 全頁歷史狀態（非即時） · "
        "選擇日期後，整個控制台會顯示該日的市場狀態、候選名單與決策（研究用，不可下單）"
    )
    if note:
        narrative = f"{narrative} · {note}"

    return {
        "date": resolved,
        "replay_mode": True,
        "replay_as_of": resolved,
        "replay_requested": as_of.strip(),
        "replay_note": note,
        "market_regime": {
            "trend": "SIDEWAYS",
            "trend_regime": "sideways",
            "volatility": "NORMAL",
            "tradeability": "WAIT",
            "should_trade": False,
            "label": "REPLAY",
            "regime": "REPLAY",
            "replay_snapshot": True,
            "score": 0,
            "confidence": 0,
            "vix": None,
            "breadth": None,
            "breadth_pct": None,
            "no_trade_reason": "Replay mode — historical brief only",
        },
        "market_pulse": None,
        "top_5": top5,
        "top_opportunities": top5,
        "near_miss": near_miss,
        "filter_funnel": fallback.get("filter_funnel"),
        "avoid_grouped": fallback.get("avoid_grouped"),
        "avoid_now": [],
        "narrative": narrative,
        "system_truth": system_truth,
        "decision_authority": _replay_decision_authority(resolved),
        "decision_model": {
            "honest_tradeability": "WAIT",
            "guidance": "Replay mode · 僅供回測檢視 — monitor historical board only",
        },
        "unlock_deploy": {
            "unlocked": False,
            "summary": "Replay mode — deploy locked",
            "intro": "Historical replay — research/backtest only; no live orders.",
            "conditions": [],
        },
        "execution_readiness": {
            "trade_handoff_ready": False,
            "readiness_label": "Replay mode — handoff disabled",
            "gateway_reachable": False,
            "broker_connected": False,
            "replay_mode": True,
        },
        "used_brief_fallback": True,
        "brief_fallback": True,
        "brief_status": {"date": resolved, "age_days": 0, "tier": "HISTORICAL"},
        "trust": {
            "source": "replay-brief",
            "stale": False,
            "replay_mode": True,
            "as_of": generated_at,
            "freshness": "HISTORICAL",
            "freshness_tier": "HISTORICAL",
            "reason": note or f"Morning brief snapshot {resolved}",
        },
        "scanner_degraded": False,
        "generated_at": generated_at,
    }


def build_replay_ranked_payload(as_of: str, *, limit: int = 30) -> Dict[str, Any]:
    """Build /api/v7/playbook/ranked payload from a dated brief snapshot."""
    resolved, brief, note = resolve_brief_for_as_of(as_of)
    from src.services.playbook_board_fallback import build_compressed_fallback

    payload = build_compressed_fallback(
        limit,
        brief=brief,
        reason=f"replay as_of={resolved}",
    )
    generated_at = str(
        brief.get("generated_at") or f"{resolved}T12:00:00Z"
    ).replace("+00:00", "Z")
    payload["replay_mode"] = True
    payload["replay_as_of"] = resolved
    payload["replay_requested"] = as_of.strip()
    payload["replay_note"] = note
    payload["snapshot_timestamp"] = generated_at
    payload["decision_authority"] = _replay_decision_authority(resolved)
    payload["system_truth"] = _replay_system_truth(resolved, note=note)
    payload["unlock_deploy"] = {
        "unlocked": False,
        "summary": "Replay mode — deploy locked",
        "intro": "Historical replay — research/backtest only.",
        "conditions": [],
    }
    payload["warning"] = (
        f"重播模式 · Replay: {resolved} · 全頁歷史狀態（非即時）"
        + (f" · {note}" if note else "")
    )
    payload["degraded_banner"] = payload["warning"]
    return payload


def build_replay_cc_header_overlay(as_of: str) -> Dict[str, Any]:
    """Minimal cc-header fields when whole-page replay is active."""
    resolved, _brief, note = resolve_brief_for_as_of(as_of)
    banner = f"重播模式 · Replay: {resolved} · 全頁歷史狀態（非即時）"
    if note:
        banner = f"{banner} · {note}"
    return {
        "display_mode": "BACKTEST",
        "trust_mode": "BACKTEST",
        "replay_mode": True,
        "replay_as_of": resolved,
        "replay_requested": as_of.strip(),
        "replay_note": note,
        "degraded_banner": banner,
        "decision_authority": _replay_decision_authority(resolved),
        "page_authority_mode": "diagnostic",
        "healthy": False,
        "pills": {
            "data": "HISTORICAL",
            "brief": "HISTORICAL",
            "alerts": 0,
        },
    }
