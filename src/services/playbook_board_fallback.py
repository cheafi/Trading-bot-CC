"""Playbook 3-layer board fallback — full live, compressed, emergency."""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BOARD_MODE_FULL = "full_live"
BOARD_MODE_COMPRESSED = "compressed_fallback"
BOARD_MODE_EMERGENCY = "emergency"

_COMPRESSED_LABEL = "Fallback board"
_LIVE_BOARD_LABEL = "Live board"
_SNAPSHOT_BOARD_LABEL = "Snapshot board"
_DEGRADED_BOARD_LABEL = "Degraded board view"
_COMPRESSED_MESSAGE = (
    "Live ranking pipeline unavailable — serving compressed fallback board "
    "to preserve speed."
)
_COMPRESSED_EXPLANATION = (
    "If live validation is delayed, fallback mode shows ranked watch candidates, "
    "rejection clusters, and unlock conditions instead of an empty board."
)

_CLUSTER_LABELS = {
    "laggard": "Laggard sector / RS",
    "regime_conflict": "Contradiction-heavy / regime conflict",
    "poor_rr": "Weak R:R",
    "low_data_quality": "Weak data quality",
    "weak_thesis": "Weak thesis",
    "execution_weak": "Execution / broker gap",
    "other": "Other filters",
}

_DEFAULT_SNAPSHOT_KEY = "30::"


def _cache_dir() -> str:
    return os.path.join(os.path.dirname(__file__), "..", "..", "data", "cache")


def _snapshot_path() -> str:
    return os.path.join(_cache_dir(), "playbook_ranked_snapshot.json")


def load_playbook_snapshot(
    cache_key: str | None = None,
) -> Dict[str, Any] | None:
    """Load last-good ranked board from disk."""
    path = _snapshot_path()
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            store = json.load(fh)
    except Exception as exc:
        logger.warning("Playbook snapshot read failed: %s", exc)
        return None
    key = cache_key or _DEFAULT_SNAPSHOT_KEY
    entry = store.get(key) or store.get(_DEFAULT_SNAPSHOT_KEY)
    if not entry or not isinstance(entry, dict):
        return None
    payload = entry.get("data")
    if not isinstance(payload, dict):
        return None
    age = time.time() - float(entry.get("ts") or 0)
    return {
        **payload,
        "cached": True,
        "stale": True,
        "age_seconds": int(age),
        "snapshot_timestamp": entry.get("saved_at") or payload.get("snapshot_timestamp"),
    }


def save_playbook_snapshot(
    payload: Dict[str, Any],
    cache_key: str | None = None,
) -> None:
    """Persist last-good ranked board (full or compressed with content)."""
    if payload.get("board_mode") == BOARD_MODE_EMERGENCY:
        return
    opps = payload.get("opportunities") or []
    near = payload.get("near_miss") or []
    clusters = payload.get("rejection_clusters") or []
    if not opps and not near and not clusters:
        return
    key = cache_key or _DEFAULT_SNAPSHOT_KEY
    path = _snapshot_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        store: Dict[str, Any] = {}
        if os.path.isfile(path):
            try:
                with open(path, encoding="utf-8") as fh:
                    store = json.load(fh)
            except Exception:
                store = {}
        saved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        store[key] = {
            "ts": time.time(),
            "saved_at": saved_at,
            "data": {**payload, "snapshot_timestamp": saved_at},
        }
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(store, fh, default=str)
            os.replace(tmp, path)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
    except Exception as exc:
        logger.warning("Playbook snapshot write failed: %s", exc)


def _brief_row_to_opportunity(row: Dict[str, Any], brief: Dict[str, Any]) -> Dict[str, Any]:
    entry = row.get("entry") or row.get("entry_price") or row.get("price")
    stop = row.get("stop") or row.get("stop_price")
    target = (
        row.get("target_3r")
        or row.get("target_2r")
        or row.get("target")
        or row.get("target_price")
    )
    risk_reward = row.get("risk_reward") or row.get("rr")
    from src.utils.numeric_parse import parse_ratio

    risk_reward = parse_ratio(risk_reward, default=None)
    if risk_reward is None and entry and stop and target and entry != stop:
        try:
            risk_reward = round(
                (float(target) - float(entry)) / (float(entry) - float(stop)), 1
            )
        except Exception:
            risk_reward = None
    conviction = str(row.get("conviction") or row.get("action") or "WATCH").upper()
    score = float(row.get("rs_score") or row.get("score") or 0)
    try:
        from src.engines.scanner_matrix import ScannerMatrix

        tier = ScannerMatrix.fallback_priority_tier(score)
    except Exception:
        tier = "High" if score >= 7.5 else ("Medium" if score >= 6 else "Low")
    why_not = row.get("why_not") or []
    if isinstance(why_not, str):
        why_not = [why_not] if why_not else []
    upgrade = row.get("upgrade_trigger") or row.get("upgrade") or ""
    return {
        "ticker": row.get("ticker") or row.get("symbol"),
        "sector_type": row.get("sector") or "",
        "theme": row.get("theme") or "Brief fallback",
        "setup": row.get("setup") or "brief",
        "stage": (row.get("stage") or row.get("sector_stage") or "").strip(),
        "leader": row.get("leader")
        or row.get("leader_status")
        or ("LEADER" if row.get("near_52w_high") else ""),
        "score": score,
        "score_display_mode": "fallback_rank",
        "score_display": tier,
        "score_display_label": "Fallback rank · relevance only",
        "priority_tier": tier,
        "score_source": "brief-fallback",
        "grade": (
            "A" if conviction == "TRADE" else "B" if conviction == "LEADER" else "C"
        ),
        "thesis_conf": 0,
        "timing_conf": 0,
        "exec_conf": 0,
        "data_conf": 0,
        "final_conf": None,
        "confidence_fallback_only": True,
        "card_display_mode": "reference_only",
        "levels_indicative_only": True,
        "deploy_authority": False,
        "monitor_zone_only": True,
        "action": "WATCH",
        "raw_action": "WATCH",
        "action_reason": (
            "Reference plan only — indicative levels · monitor zone · "
            "no deploy authority"
        ),
        "risk_level": "NORMAL",
        "entry_price": entry,
        "target_price": target,
        "stop_price": stop,
        "risk_reward": risk_reward,
        "why_now": row.get("why_now")
        or row.get("reason")
        or f"RS:{row.get('rs_score', '—')} · ATR:{row.get('atr_pct', '—')}% · Vol:{row.get('vol_ratio', '—')}x",
        "why_not": why_not,
        "upgrade_trigger": upgrade or "Reclaim entry zone on volume",
        "evidence_badge": "stale-brief" if brief.get("synthetic") else "brief-fallback",
        "invalidation": row.get("invalidation")
        or (
            f"Close below stop ${stop}"
            if stop
            else "Regime gate closes or structure breaks down"
        ),
    }


def _rejection_clusters_from_grouped(avoid_grouped: Dict[str, Any]) -> List[Dict[str, Any]]:
    clusters: List[Dict[str, Any]] = []
    for g in avoid_grouped.get("groups") or []:
        key = g.get("group") or "other"
        clusters.append(
            {
                "key": key,
                "label": _CLUSTER_LABELS.get(key, g.get("label") or key),
                "count": g.get("count") or 0,
                "sample_tickers": (g.get("tickers") or [])[:4],
                "sample_reason": g.get("sample_reason") or "",
            }
        )
    return clusters


def build_unlock_deploy_fallback(
    *,
    watch_qualified_count: int,
    deployable_count: int,
    scanner_degraded: bool = True,
    scan_ranked_count: int = 0,
    degradation_notes: Optional[List[str]] = None,
) -> Dict[str, Any]:
    from src.services.today_insights import build_unlock_deploy

    wq = int(watch_qualified_count or 0)
    notes = list(degradation_notes or [])
    if scanner_degraded and not notes:
        notes = ["board context: fallback board", "rank input: cache stale"]
    return build_unlock_deploy(
        tradeability="WAIT",
        should_trade=True,
        watch_qualified_count=wq,
        deployable_count=deployable_count,
        scan_ranked_count=int(scan_ranked_count or 0),
        scanner_degraded=scanner_degraded,
        degradation_notes=notes or None,
        execution_readiness={},
    )


def build_compressed_fallback(
    limit: int,
    action: str | None = None,
    sector: str | None = None,
    *,
    brief: Dict[str, Any] | None = None,
    reason: str = "ranked pipeline unavailable",
) -> Dict[str, Any]:
    """Layer 2 — watch candidates, near-misses, rejection clusters, unlock."""
    if sector:
        return build_emergency_response(
            reason="Sector filter active but live ranking unavailable",
            detail="Compressed fallback cannot filter by sector without live pipeline.",
        )
    if brief is None:
        try:
            from src.services.brief_data_service import load_brief

            brief = load_brief()
        except Exception as exc:
            logger.warning("Compressed fallback brief load failed: %s", exc)
            brief = {}

    if not brief:
        return build_emergency_response(
            reason="No live board and no brief data for compressed fallback",
            detail=reason,
        )

    watch_pool: List[Dict[str, Any]] = []
    review_pool: List[Dict[str, Any]] = []
    for section, bucket in (("actionable", watch_pool), ("watch", watch_pool), ("review", review_pool)):
        for row in brief.get(section, []) or []:
            opp = _brief_row_to_opportunity(row, brief)
            if action and str(opp.get("action") or "").upper() != action.upper():
                continue
            if section == "review":
                opp["action"] = "AVOID"
                review_pool.append(opp)
            else:
                if str(opp.get("action") or "").upper() in ("AVOID", "NO_TRADE"):
                    review_pool.append(opp)
                else:
                    watch_pool.append(opp)

    watch_pool.sort(key=lambda r: float(r.get("score") or 0), reverse=True)
    review_pool.sort(key=lambda r: float(r.get("score") or 0), reverse=True)

    watch_limit = min(5, max(3, limit // 6 or 5))
    watch_rows = watch_pool[:watch_limit]
    near_miss = []
    for row in watch_pool[watch_limit : watch_limit + 8]:
        if float(row.get("score") or 0) >= 6.0:
            nm = dict(row)
            nm.setdefault(
                "whats_missing",
                "stronger timing, confirmed volume, monitor-pipeline support",
            )
            near_miss.append(nm)
        if len(near_miss) >= 3:
            break
    if len(near_miss) < 3:
        for row in review_pool:
            if float(row.get("score") or 0) >= 5.5:
                near_miss.append(
                    {
                        **row,
                        "action": "WATCH",
                        "whats_missing": "Passed scan but failed validation gates",
                    }
                )
            if len(near_miss) >= 3:
                break

    all_for_avoid = review_pool + [
        r for r in watch_pool if str(r.get("action") or "").upper() in ("AVOID", "NO_TRADE")
    ]
    try:
        from src.services.decision_truth_model import build_avoid_grouped_from_rows

        avoid_grouped = build_avoid_grouped_from_rows(all_for_avoid, limit_per_group=6)
    except ImportError:
        avoid_grouped = {"total": len(all_for_avoid), "groups": []}

    rejection_clusters = _rejection_clusters_from_grouped(avoid_grouped)
    scanned = len(watch_pool) + len(review_pool) + int(avoid_grouped.get("total") or 0)
    watch_qualified = len(watch_pool)
    saved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    funnel = {
        "universe_scanned": scanned,
        "watch_qualified_setups": watch_qualified,
        "deploy_qualified_setups": 0,
        "high_score_setups": len(
            [r for r in watch_pool if float(r.get("score") or 0) >= 6.0]
        ),
        "execution_ready_setups": 0,
        "near_miss_setups": len(near_miss),
        "avoid_filtered_setups": avoid_grouped.get("total", 0),
        "note": (
            "Fallback board — scanned → watch-qualified → deploy-qualified. "
            "Near-miss and monitor ranking are upgrade / priority layers only."
        ),
    }
    try:
        from src.services.decision_truth_model import (
            normalize_playbook_funnel,
            playbook_scan_ranked_count,
            rejection_clusters_reconcile_note,
        )

        funnel = normalize_playbook_funnel(
            funnel, opportunities=watch_rows, near_miss=near_miss
        )
        scan_ranked = playbook_scan_ranked_count(
            funnel, opportunity_count=len(watch_pool) + len(review_pool)
        )
        cluster_note = rejection_clusters_reconcile_note(
            rejection_clusters, avoid_grouped
        )
    except ImportError:
        scan_ranked = 0
        cluster_note = ""

    payload: Dict[str, Any] = {
        "count": len(watch_rows),
        "opportunities": watch_rows,
        "near_miss": near_miss[:3],
        "avoid_grouped": avoid_grouped,
        "rejection_clusters": rejection_clusters,
        "filter_funnel": funnel,
        "unlock_deploy": build_unlock_deploy_fallback(
            watch_qualified_count=int(funnel.get("watch_qualified_setups") or 0),
            deployable_count=0,
            scan_ranked_count=scan_ranked,
            scanner_degraded=True,
        ),
        "rejection_clusters_note": cluster_note,
        "cached": False,
        "stale": True,
        "compressed": True,
        "source": "compressed_fallback",
        "warning": _COMPRESSED_MESSAGE,
        "board_mode": BOARD_MODE_COMPRESSED,
        "board_mode_label": _COMPRESSED_LABEL,
        "board_message": _COMPRESSED_MESSAGE,
        "board_explanation": _COMPRESSED_EXPLANATION,
        "snapshot_timestamp": saved_at,
        "avoid_collapsed_default": True,
    }
    return payload


def build_emergency_response(
    *,
    reason: str,
    detail: str = "",
) -> Dict[str, Any]:
    """Layer 3 — explain, retry, navigation CTAs."""
    saved_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "count": 0,
        "opportunities": [],
        "near_miss": [],
        "avoid_grouped": {"total": 0, "groups": []},
        "rejection_clusters": [],
        "filter_funnel": {
            "universe_scanned": 0,
            "watch_qualified_setups": 0,
            "deploy_qualified_setups": 0,
            "high_score_setups": 0,
            "execution_ready_setups": 0,
        },
        "cached": False,
        "stale": True,
        "source": "emergency",
        "warning": reason,
        "board_mode": BOARD_MODE_EMERGENCY,
        "board_mode_label": "Board unavailable",
        "board_message": reason,
        "board_explanation": detail or reason,
        "snapshot_timestamp": saved_at,
        "emergency": {
            "reason": reason,
            "detail": detail or reason,
            "reasons": [
                "Live ranked pipeline timed out or returned no data",
                "Morning brief not available for compressed fallback",
                "No prior successful board snapshot cached",
            ],
            "actions": [
                {"key": "retry", "label": "Retry ranked board"},
                {"key": "dashboard", "label": "Open Dashboard"},
                {"key": "discovery", "label": "Open Discovery / Scanner"},
            ],
        },
    }


_AVOID_ACTIONS = frozenset({"AVOID", "NO_TRADE"})


def visible_opportunities(opportunities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Rows that are not hard-filtered from the default playbook board."""
    return [
        r
        for r in opportunities
        if str(r.get("action") or "").upper() not in _AVOID_ACTIONS
    ]


def board_has_content(payload: Dict[str, Any]) -> bool:
    """True when the board has anything meaningful to render (not a blank WAIT day)."""
    opps = payload.get("opportunities") or []
    if visible_opportunities(opps):
        return True
    if payload.get("near_miss"):
        return True
    if payload.get("rejection_clusters"):
        return True
    avoid = payload.get("avoid_grouped") or {}
    return bool(avoid.get("total"))


def supplement_zero_deploy_board(
    payload: Dict[str, Any],
    limit: int = 30,
    *,
    action: str | None = None,
    sector: str | None = None,
) -> Dict[str, Any]:
    """Ensure WAIT / zero-deploy boards still show watch + near-miss when data exists."""
    opps = list(payload.get("opportunities") or [])
    near = list(payload.get("near_miss") or [])
    funnel = payload.get("filter_funnel") or {}
    deploy = int(funnel.get("execution_ready_setups") or 0)
    visible = visible_opportunities(opps)

    if deploy > 0 or visible or near:
        return payload

    merged = dict(payload)

    # Top ranked scan names — relabel as monitor candidates even when council marked AVOID.
    if opps:
        sorted_opps = sorted(
            opps,
            key=lambda r: float(r.get("score") or r.get("final_conf") or 0),
            reverse=True,
        )
        derived: List[Dict[str, Any]] = []
        for row in sorted_opps:
            score = float(row.get("score") or row.get("final_conf") or 0)
            if score < 4.0:
                continue
            nm = {**row, "action": "WATCH"}
            nm.setdefault(
                "whats_missing",
                "Ranked by scan but blocked by deploy gates — monitor for upgrade",
            )
            derived.append(nm)
            if len(derived) >= 3:
                break
        if derived:
            merged["near_miss"] = derived
            merged.setdefault(
                "board_message",
                "WAIT day — no deployable setups; showing top monitor candidates from live scan.",
            )
            if funnel:
                merged["filter_funnel"] = {
                    **funnel,
                    "near_miss_setups": len(derived),
                }
            return merged

    if sector:
        return payload

    compressed = build_compressed_fallback(limit, action, sector)
    if compressed.get("board_mode") == BOARD_MODE_EMERGENCY:
        return payload

    cf_opps = compressed.get("opportunities") or []
    cf_near = compressed.get("near_miss") or []
    if not cf_opps and not cf_near:
        return payload

    if cf_near:
        merged["near_miss"] = cf_near
    if cf_opps:
        merged["opportunities"] = cf_opps
        merged["count"] = len(cf_opps)
    if not merged.get("rejection_clusters") and compressed.get("rejection_clusters"):
        merged["rejection_clusters"] = compressed["rejection_clusters"]
    if not (merged.get("avoid_grouped") or {}).get("total") and compressed.get(
        "avoid_grouped"
    ):
        merged["avoid_grouped"] = compressed["avoid_grouped"]
    if not merged.get("unlock_deploy") and compressed.get("unlock_deploy"):
        merged["unlock_deploy"] = compressed["unlock_deploy"]
    if not merged.get("filter_funnel") and compressed.get("filter_funnel"):
        merged["filter_funnel"] = compressed["filter_funnel"]
    merged["wait_day_supplement"] = True
    merged.setdefault(
        "board_message",
        "WAIT day — live scan had no deployable names; watch candidates from brief.",
    )
    merged.setdefault("board_explanation", _COMPRESSED_EXPLANATION)
    if str(merged.get("source") or "") == "ranked_pipeline":
        merged["board_mode_label"] = "Degraded board view · brief watch supplement"
    return merged


def resolve_board_mode_label(
    payload: Dict[str, Any], *, from_live: bool = False
) -> str:
    """Human label for board authority — never imply full live when fallback/snapshot."""
    if payload.get("emergency"):
        return "Board unavailable"
    source = str(payload.get("source") or "")
    if payload.get("compressed") or "fallback" in source or source == "compressed_fallback":
        return _COMPRESSED_LABEL
    if payload.get("cached") or payload.get("stale"):
        return _SNAPSHOT_BOARD_LABEL
    if from_live or source == "ranked_pipeline":
        return _LIVE_BOARD_LABEL
    if (payload.get("opportunities") or []) or (payload.get("near_miss") or []):
        return _DEGRADED_BOARD_LABEL
    return "Board unavailable"


def annotate_board_mode(payload: Dict[str, Any], *, from_live: bool = False) -> Dict[str, Any]:
    """Set board_mode and labels on any ranked payload."""
    if payload.get("board_mode"):
        payload.setdefault(
            "snapshot_timestamp",
            payload.get("snapshot_timestamp")
            or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        return payload
    if payload.get("emergency"):
        payload["board_mode"] = BOARD_MODE_EMERGENCY
        payload.setdefault("board_mode_label", "Board unavailable")
        return payload
    source = str(payload.get("source") or "")
    if payload.get("compressed") or "fallback" in source or source == "compressed_fallback":
        payload["board_mode"] = BOARD_MODE_COMPRESSED
        payload.setdefault("board_mode_label", _COMPRESSED_LABEL)
        payload.setdefault("board_message", _COMPRESSED_MESSAGE)
        payload.setdefault("board_explanation", _COMPRESSED_EXPLANATION)
        payload.setdefault("avoid_collapsed_default", True)
        if not payload.get("rejection_clusters") and payload.get("avoid_grouped"):
            payload["rejection_clusters"] = _rejection_clusters_from_grouped(
                payload["avoid_grouped"]
            )
        return payload
    if from_live or source == "ranked_pipeline":
        payload["board_mode"] = BOARD_MODE_FULL
        payload["board_mode_label"] = resolve_board_mode_label(payload, from_live=from_live)
        payload.setdefault(
            "snapshot_timestamp",
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
        return payload
    if (payload.get("opportunities") or []) or (payload.get("near_miss") or []):
        payload["board_mode"] = BOARD_MODE_COMPRESSED
        payload.setdefault("board_mode_label", resolve_board_mode_label(payload))
        return payload
    payload["board_mode"] = BOARD_MODE_EMERGENCY
    payload.setdefault("board_mode_label", "Board unavailable")
    return payload
