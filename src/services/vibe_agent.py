"""Vibe Agent — overnight watch, intent parsing, rule evaluation (monitoring only)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from src.services.vibe_agent_safety import (
    authority_notice_for_state,
    sanitize_agent_payload,
)
from src.services.vibe_agent_store import (
    list_alerts,
    list_rules,
    log_agent_decision,
    save_alert,
    save_intent,
    save_rule,
    store_snapshot,
)

_TICKER_RE = re.compile(r"\b([A-Z]{1,5}(?:\.[A-Z])?)\b")
_CRYPTO = re.compile(r"\b(BTC|ETH|SOL)\b", re.I)

_INTENT_KEYWORDS = {
    "pullback": "pullback",
    "回調": "pullback",
    "突破": "breakout",
    "breakout": "breakout",
    "oversold": "oversold",
    "超賣": "oversold",
    "drawdown": "drawdown_risk",
    "回撤": "drawdown_risk",
    "高勝率": "high_quality_setup",
    "rs": "rs_leader",
    "相對強度": "rs_leader",
    "volume": "volume_expansion",
    "量能": "volume_expansion",
    "regime": "regime_watch",
    "vix": "vix_threshold",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat() + "Z"


def _default_expiry(days: int = 14) -> str:
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat() + "Z"


def _extract_assets(text: str) -> List[str]:
    found: List[str] = []
    for m in _CRYPTO.finditer(text):
        t = m.group(1).upper()
        if t not in found:
            found.append(t)
    for m in _TICKER_RE.finditer(text.upper()):
        t = m.group(1)
        if t in {"I", "A", "TO", "THE", "AND", "OR", "RS", "MA", "VIX"}:
            continue
        if t not in found:
            found.append(t)
    return found[:8]


def parse_vibe_intent(raw_text: str) -> Dict[str, Any]:
    """Convert vague user intent into structured hypothesis — plan, not permission."""
    text = str(raw_text or "").strip()
    lower = text.lower()
    assets = _extract_assets(text)
    intent_type = "monitor_setup"
    if "drawdown" in lower or "回撤" in lower:
        intent_type = "portfolio_risk"
    elif "regime" in lower or "vix" in lower:
        intent_type = "regime_watch"
    elif "breakout" in lower or "突破" in lower:
        intent_type = "breakout_watch"
    elif "pullback" in lower or "回調" in lower:
        intent_type = "pullback_watch"

    desired = "monitor"
    for kw, setup in _INTENT_KEYWORDS.items():
        if kw in lower:
            desired = setup
            break

    risk = "conservative"
    if "唔想追高" in text or "don't chase" in lower or "no chase" in lower:
        risk = "no_chase"
    if "高勝率" in text or "high quality" in lower:
        risk = "selective"

    invalidation = "Setup fails if RS deteriorates or volume fades on reclaim"
    if "pullback" in desired:
        invalidation = "Pullback thesis fails if price breaks prior swing low on volume"
    if intent_type == "portfolio_risk":
        invalidation = "Risk boundary breached — reduce exposure per portfolio rule"

    plan = sanitize_agent_payload(
        {
            "intentType": intent_type,
            "assets": assets,
            "timeframe": "1-5 sessions"
            if "星期" in text or "week" in lower
            else "overnight",
            "hypothesis": text[:240] if text else "Monitor hypothesis pending detail",
            "desiredSetup": desired,
            "riskTolerance": risk,
            "requiredEvidence": [
                "Playbook watch-qualified or near-miss",
                "RS vs benchmark improving",
                "Volume confirmation on trigger",
            ],
            "invalidation": invalidation,
            "suggestedWatchRules": build_watch_rules_from_intent(
                {
                    "assets": assets,
                    "desiredSetup": desired,
                    "intentType": intent_type,
                    "invalidation": invalidation,
                }
            ),
            "confirmationPath": "Dashboard → Playbook → Dossier",
            "expiry": _default_expiry(),
            "authority_notice": [
                "Research / monitoring only",
                "Requires Dashboard + Playbook confirmation",
            ],
        }
    )
    return plan


def build_watch_rules_from_intent(intent_plan: Dict[str, Any]) -> List[Dict[str, Any]]:
    """buildWatchRule — one or more monitor rules from structured intent."""
    assets = intent_plan.get("assets") or ["WATCHLIST"]
    rules: List[Dict[str, Any]] = []
    setup = str(intent_plan.get("desiredSetup") or "monitor")
    rule_type = "setup_upgrade"
    if setup == "pullback":
        rule_type = "price_zone_touch"
    elif setup == "breakout":
        rule_type = "price_cross"
    elif setup == "rs_leader":
        rule_type = "rs_acceleration"
    elif setup == "volume_expansion":
        rule_type = "volume_expansion"
    elif setup == "drawdown_risk":
        rule_type = "drawdown_breach"
    elif setup == "regime_watch":
        rule_type = "regime_change"

    for asset in assets[:5]:
        rules.append(
            sanitize_agent_payload(
                {
                    "id": str(uuid.uuid4())[:12],
                    "name": f"{asset} · {rule_type}",
                    "asset": asset,
                    "ruleType": rule_type,
                    "condition": _rule_condition_for_type(rule_type, intent_plan),
                    "dataRequired": ["market_data", "playbook_rank"],
                    "freshnessRequired": "FRESH",
                    "confirmationRequired": True,
                    "authorityEffect": "none",
                    "action": "alert_only",
                    "expiry": intent_plan.get("expiry") or _default_expiry(),
                    "status": "proposed",
                }
            )
        )
    return rules


def build_watch_rule(
    intent_plan: Dict[str, Any], *, intent_id: str = ""
) -> List[Dict[str, Any]]:
    rules = build_watch_rules_from_intent(intent_plan)
    for r in rules:
        r["intentId"] = intent_id
        r["createdFromIntentId"] = intent_id
    return rules


def _rule_condition_for_type(rule_type: str, plan: Dict[str, Any]) -> str:
    asset = (plan.get("assets") or ["—"])[0]
    if rule_type == "price_zone_touch":
        return f"{asset} enters monitor zone with RS stable"
    if rule_type == "price_cross":
        return f"{asset} reclaims key level on volume"
    if rule_type == "rs_acceleration":
        return f"{asset} RS percentile improves vs SPY"
    if rule_type == "drawdown_breach":
        return "Portfolio drawdown exceeds user boundary"
    if rule_type == "regime_change":
        return "Regime/tradeability drift detected"
    return f"{asset} setup upgrade signals >= 2"


def evaluate_watch_rules(
    *,
    system_state: Optional[Dict[str, Any]] = None,
    market_data: Optional[Dict[str, Any]] = None,
    playbook_state: Optional[Dict[str, Any]] = None,
    portfolio_state: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate active rules — alerts are monitor-only."""
    ss = system_state or {}
    md = market_data or {}
    pb = playbook_state or {}
    pf = portfolio_state or {}
    tb = str(ss.get("tradeability") or "WAIT").upper()
    data_tier = str(ss.get("data_freshness") or md.get("worst_tier") or "FRESH")
    stale = data_tier in ("STALE", "CRITICAL")
    deploy_blocked = tb in ("WAIT", "NO_TRADE") or not ss.get("deploy_open")

    triggered: List[Dict[str, Any]] = []
    provisional: List[Dict[str, Any]] = []
    expired: List[Dict[str, Any]] = []
    suppressed: List[Dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    monitor_rows = pb.get("monitor_rows") or []
    near_miss = pb.get("near_miss") or []
    rank_map = {str(r.get("ticker") or "").upper(): r for r in monitor_rows + near_miss}

    for rule in list_rules(status="active"):
        exp = rule.get("expiry")
        if exp:
            try:
                exp_dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                if exp_dt < now:
                    expired.append(rule)
                    continue
            except ValueError:
                pass
        if rule.get("status") == "muted":
            suppressed.append(rule)
            continue

        asset = str(rule.get("asset") or "").upper()
        row = rank_map.get(asset)
        hit = False
        reason = ""
        if row and str(row.get("action") or "").upper() not in (
            "AVOID",
            "NO_TRADE",
            "BLOCKED",
        ):
            hit = True
            reason = f"候選升級 · Candidate upgraded — Playbook {row.get('action')}"
        elif asset in (pf.get("heat_tickers") or []):
            hit = True
            reason = "Portfolio heat boundary proximity"

        if not hit:
            continue

        alert = sanitize_agent_payload(
            {
                "ruleId": rule.get("id"),
                "asset": asset,
                "triggeredAt": _now(),
                "triggerReason": reason,
                "dataSnapshot": {"data_tier": data_tier, "ticker": asset},
                "systemStateSnapshot": {
                    "tradeability": tb,
                    "deploy_blocked": deploy_blocked,
                },
                "authorityNotice": authority_notice_for_state(ss),
                "nextAction": (
                    "開 Playbook 確認 watch-qualified"
                    if deploy_blocked
                    else "Review Playbook then Dashboard gate"
                ),
                "status": "provisional" if stale else "triggered",
                "confidence": "low" if stale else "medium",
                "candidate_only": deploy_blocked,
            }
        )
        if stale:
            provisional.append(alert)
            try:
                from src.notifications.discord_dispatch import push_notice

                push_notice(
                    title=f"Agent · {asset} (provisional)",
                    message=f"{reason}\nData stale — monitor only",
                    severity="info",
                    event_type="agent_alert",
                    meta={"asset": asset, "provisional": True},
                )
            except Exception:
                pass
        else:
            triggered.append(alert)
            saved = save_alert(alert)
            log_agent_decision(
                {
                    "type": "alert_generated",
                    "rule_id": rule.get("id"),
                    "alert_id": saved.get("id"),
                    "detail": reason,
                    "authority_state": tb,
                }
            )
            try:
                from src.notifications.discord_dispatch import push_notice

                push_notice(
                    title=f"Agent · {asset}",
                    message=(
                        f"{reason}\n"
                        f"Gate: {tb} · {'provisional' if stale else 'monitor'}\n"
                        f"Next: {alert.get('nextAction', '開 Playbook 確認')}"
                    ),
                    severity="warning" if deploy_blocked else "info",
                    event_type="agent_alert",
                    meta={"asset": asset, "rule_id": rule.get("id")},
                )
            except Exception:
                pass

    return {
        "triggeredAlerts": triggered,
        "provisionalAlerts": provisional,
        "expiredRules": expired,
        "suppressedAlerts": suppressed,
        "recommendedNextChecks": [
            "Review Playbook watch-qualified",
            "Confirm structure in Dossier",
            "Check Dashboard gate before any sizing",
        ],
    }


def generate_overnight_brief(
    *,
    system_state: Optional[Dict[str, Any]] = None,
    today_payload: Optional[Dict[str, Any]] = None,
    alerts: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Morning briefing — Chinese first, concise English labels."""
    ss = system_state or {}
    today = today_payload or {}
    tb = str(ss.get("tradeability") or today.get("tradeability") or "WAIT").upper()
    regime = today.get("market_regime") or {}
    lines: List[str] = []

    lines.append(f"1. Regime 狀態：{regime.get('trend') or tb} · {tb}。")
    if ss.get("data_freshness") in ("STALE", "CRITICAL"):
        lines.append("2. 資料過期 — alerts 只供 provisional monitor。")
    else:
        lines.append("2. Data freshness acceptable for monitor review。")

    monitors = today.get("dashboard_monitors") or []
    if monitors:
        lines.append(
            f"3. Top monitors：{' / '.join(monitors[:3])} — 需 Playbook 確認。"
        )
    else:
        lines.append(
            "3. 暫無 valid monitor candidates — 檢查 Playbook rejected bucket。"
        )

    broker = str(ss.get("broker_state") or "")
    if broker in ("GATEWAY_DOWN", "DISCONNECTED", "SESSION_INACTIVE", "EXEC_BLOCKED"):
        lines.append("4. IBKR 離線，今日不可 handoff。")
    else:
        lines.append("4. Broker path — confirm in IBKR tab before handoff。")

    alert_rows = alerts or list_alerts(limit=5)
    if alert_rows:
        lines.append(f"5. Agent alerts ({len(alert_rows)}) — review timeline first。")

    lines.append(
        "下一步：先修復 data freshness（如需要），再睇 Playbook watch-qualified。"
    )

    return sanitize_agent_payload(
        {
            "title": "昨晚重點 · Overnight",
            "lines": lines,
            "summary": "\n".join(lines),
            "regime": tb,
            "top_monitors": monitors[:3],
            "alert_count": len(alert_rows),
            "authority_notice": authority_notice_for_state(ss),
            "generated_at": _now(),
        }
    )


def create_calm_down_guardrail(
    action_type: str,
    *,
    system_state: Optional[Dict[str, Any]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    from src.services.vibe_agent_safety import guardrail_for_action

    result = guardrail_for_action(
        action_type=action_type, system_state=system_state, context=context
    )
    if result.get("triggered"):
        log_agent_decision(
            {
                "type": "guardrail",
                "user_action": action_type,
                "detail": ",".join(result.get("violated_rules") or []),
            }
        )
        try:
            from src.notifications.discord_dispatch import push_notice

            push_notice(
                title="情緒警戒 · Calm-down guardrail",
                message=result.get("warning_sentence", ""),
                severity="warning",
                event_type="agent_guardrail",
                meta={"action": action_type, "rules": result.get("violated_rules")},
            )
        except Exception:
            pass
    return result


def review_agent_outcome(
    alert_id: str,
    *,
    user_action: str = "ignored",
    outcome_1d: Optional[float] = None,
    outcome_5d: Optional[float] = None,
    outcome_20d: Optional[float] = None,
    lesson: str = "",
) -> Dict[str, Any]:
    """Learning loop — track alert usefulness."""
    entry = log_agent_decision(
        {
            "type": "outcome_review",
            "alert_id": alert_id,
            "user_action": user_action,
            "detail": lesson,
            "outcome_1d": outcome_1d,
            "outcome_5d": outcome_5d,
            "outcome_20d": outcome_20d,
        }
    )
    quality = "noisy"
    if user_action == "playbook_confirmed" and (outcome_5d or 0) > 0:
        quality = "useful"
    elif user_action == "ignored" and (outcome_5d or 0) < -2:
        quality = "missed_winner"
    elif user_action == "acted_without_gate":
        quality = "emotional_error"
    return sanitize_agent_payload(
        {
            "review_id": entry.get("id"),
            "alert_id": alert_id,
            "rule_quality": quality,
            "user_action": user_action,
            "outcome1D": outcome_1d,
            "outcome5D": outcome_5d,
            "outcome20D": outcome_20d,
            "lesson": lesson,
        }
    )


def agent_status(
    *,
    system_state: Optional[Dict[str, Any]] = None,
    paused: bool = False,
) -> Dict[str, Any]:
    ss = system_state or {}
    data_tier = str(ss.get("data_freshness") or "FRESH")
    running = not paused
    mode = "running"
    if paused:
        mode = "paused"
    elif data_tier in ("STALE", "CRITICAL") or ss.get("fallback_mode"):
        mode = "degraded"
    elif str(ss.get("broker_state") or "") in ("GATEWAY_DOWN", "DISCONNECTED"):
        mode = "offline"

    snap = store_snapshot()
    return sanitize_agent_payload(
        {
            "mode": mode,
            "running": running,
            "last_check": _now(),
            "data_freshness": data_tier,
            "watch_scope": f"{snap.get('rule_count', 0)} active rules",
            "alert_count": snap.get("alert_count", 0),
            "authority_label": "Research / Monitoring only · 非部署權限",
            "authority_notice": authority_notice_for_state(ss),
            "operator_sentence": {
                "now": f"Agent {mode}",
                "blocker": ss.get("blocker_compact") or "—",
                "next_action": "Review alerts → Playbook → Dossier",
            },
        }
    )


def persist_intent_and_rules(raw_text: str) -> Dict[str, Any]:
    plan = parse_vibe_intent(raw_text)
    intent = save_intent(
        {
            "rawText": raw_text,
            "parsedAt": _now(),
            "assets": plan.get("assets"),
            "timeframe": plan.get("timeframe"),
            "hypothesis": plan.get("hypothesis"),
            "riskTolerance": plan.get("riskTolerance"),
            "desiredSetup": plan.get("desiredSetup"),
            "invalidation": plan.get("invalidation"),
            "expiry": plan.get("expiry"),
            "status": "parsed",
            "plan": plan,
        }
    )
    rules = build_watch_rule(plan, intent_id=intent["id"])
    saved_rules = []
    for r in rules:
        r["status"] = "active"
        saved_rules.append(save_rule(r))
    log_agent_decision(
        {
            "type": "intent_parsed",
            "intent_id": intent["id"],
            "detail": raw_text[:120],
        }
    )
    return {"intent": intent, "plan": plan, "rules": saved_rules}
