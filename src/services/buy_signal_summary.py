"""Clean buy-signal labels for Playbook rows — monitor/research tier, not deploy authority."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_SIGNAL_TYPES = frozenset(
    {"BREAKOUT", "TREND", "RS_LEADER", "ETF_THEME", "REVERSAL"}
)
_DEPLOY_ACTIONS = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "TRADE_NOW", "STRONG_TRADE"})
_PILOT_ACTIONS = frozenset({"PILOT"})
_WATCH_ACTIONS = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER", "LEADER", "LEADER_MONITOR"})
_AVOID_ACTIONS = frozenset({"AVOID", "NO_TRADE", "NO_TOUCH", "DO_NOT_TOUCH", "PASS"})


def _f(val: Any, default: float = 0.0) -> float:
    try:
        return float(val if val is not None else default)
    except (TypeError, ValueError):
        return default


def classify_signal_type(row: Dict[str, Any]) -> str:
    """Map row context to a primary buy/setup archetype."""
    ac = str(row.get("asset_class") or "").lower()
    if ac in ("etf", "index") or row.get("source") == "coverage_pad":
        return "ETF_THEME"
    strategy = str(row.get("strategy") or row.get("setup") or "").lower()
    pattern = str(row.get("pattern") or "").lower()
    text = f"{strategy} {pattern}"
    if row.get("near_52w_high") or "breakout" in text or "squeeze" in text:
        return "BREAKOUT"
    if "reversal" in text or "mean_reversion" in text or "pullback" in text:
        return "REVERSAL"
    if str(row.get("leader") or "").upper() == "LEADER" or _f(row.get("rs_rank")) >= 72:
        return "RS_LEADER"
    if "uptrend" in str(row.get("trend_structure") or "").lower() or row.get("above_50sma"):
        return "TREND"
    if _f(row.get("vol_ratio")) >= 1.4:
        return "BREAKOUT"
    return "TREND"


def _confidence_tier(row: Dict[str, Any]) -> str:
    score = _f(row.get("score") or row.get("final_conf"))
    thesis = _f(row.get("thesis_conf"))
    timing = _f(row.get("timing_conf"))
    data_c = _f(row.get("data_conf"))
    if row.get("execution_ready") and row.get("trade_bar", {}).get("passes_trade_bar"):
        return "DEPLOY"
    if score >= 7.5 and thesis >= 0.6 and timing >= 0.55:
        return "HIGH"
    if score >= 6.5 or (thesis >= 0.5 and timing >= 0.48):
        return "MEDIUM"
    if score >= 5.0:
        return "LOW"
    return "RESEARCH"


def _authority_label(row: Dict[str, Any]) -> str:
    if row.get("execution_ready") and row.get("trade_bar", {}).get("passes_trade_bar"):
        return "DEPLOY"
    act = str(row.get("action") or "").upper()
    if act in _AVOID_ACTIONS:
        return "AVOID"
    if act in _PILOT_ACTIONS:
        return "MONITOR"
    if act in _WATCH_ACTIONS or row.get("near_miss_label") in ("watch", "near_miss"):
        return "WATCH"
    if act in _DEPLOY_ACTIONS:
        return "MONITOR"
    return "MONITOR"


def _primary_blocker(row: Dict[str, Any]) -> str:
    for key in ("primary_blocker", "whats_missing", "blocker"):
        val = row.get(key)
        if isinstance(val, list):
            val = "; ".join(str(x) for x in val if x)
        if val:
            return str(val)[:200]
    oi = row.get("operator_insight") or {}
    if oi.get("blocker"):
        return str(oi["blocker"])[:200]
    gaps = row.get("gaps") or row.get("upgrade_gaps") or {}
    if isinstance(gaps, dict):
        parts = [f"{k} {v}" for k, v in gaps.items() if v not in ("ok", "n/a", None)]
        if parts:
            return "; ".join(parts)[:200]
    if row.get("rr_below_trade_threshold"):
        return "R:R below TRADE gate · 未達全倉 R:R 門檻"
    if not row.get("execution_ready"):
        return "Not execution-ready · 未達部署就緒"
    return "Deploy gates incomplete · 部署門檻未齊"


def _why_now(row: Dict[str, Any], signal_type: str) -> str:
    raw = row.get("why_now")
    if isinstance(raw, list):
        raw = " · ".join(str(x) for x in raw if x)
    if raw:
        return str(raw)[:220]
    ticker = str(row.get("ticker") or "").upper()
    vol = _f(row.get("vol_ratio"), 1.0)
    rs = _f(row.get("rs_rank"))
    parts_en: List[str] = []
    parts_zh: List[str] = []
    if signal_type == "BREAKOUT":
        parts_en.append("price/volume breakout setup")
        parts_zh.append("價量突破型態")
    elif signal_type == "RS_LEADER":
        parts_en.append(f"relative strength leader (RS ~{rs:.0f})")
        parts_zh.append(f"相對強勢領先 (RS ~{rs:.0f})")
    elif signal_type == "ETF_THEME":
        theme = row.get("theme") or row.get("sector_type") or "sector/theme"
        parts_en.append(f"{theme} ETF/theme tape")
        parts_zh.append(f"{theme} 主題/ETF 資金流")
    elif signal_type == "REVERSAL":
        parts_en.append("mean-reversion / pullback bounce candidate")
        parts_zh.append("均值回歸/回檔反彈候選")
    else:
        parts_en.append("trend continuation monitor")
        parts_zh.append("趨勢延續監控")
    if vol >= 1.2:
        parts_en.append(f"vol {vol:.1f}x")
        parts_zh.append(f"量能 {vol:.1f}x")
    en = f"{ticker}: " + ", ".join(parts_en)
    zh = " · ".join(parts_zh)
    return f"{zh} · {en}"[:240]


def _bilingual_summary(row: Dict[str, Any], signal_type: str, authority: str) -> str:
    ticker = str(row.get("ticker") or "").upper()
    type_zh = {
        "BREAKOUT": "突破",
        "TREND": "趨勢",
        "RS_LEADER": "強勢領先",
        "ETF_THEME": "ETF/主題",
        "REVERSAL": "反轉",
    }.get(signal_type, "監控")
    type_en = signal_type.replace("_", " ").title()
    auth_zh = {
        "DEPLOY": "可部署",
        "WATCH": "監控",
        "MONITOR": "觀察",
        "AVOID": "回避",
    }.get(authority, "監控")
    score = _f(row.get("score"))
    return (
        f"{ticker} · {type_zh}買點 · {auth_zh} · {score:.1f}分"
        f" · {type_en} · {authority}"
    )


def _upgrade_path(row: Dict[str, Any], authority: str) -> str:
    if authority == "DEPLOY":
        return "Deploy gate open — confirm bracket/IBKR · 部署門檻已過，確認下單"
    trigger = row.get("upgrade_trigger") or row.get("alert_trigger")
    if trigger:
        return str(trigger)[:160]
    gaps = row.get("upgrade_gaps") or {}
    needs: List[str] = []
    for key, label in (
        ("timing", "timing confirm"),
        ("thesis", "thesis depth"),
        ("rr", "R:R to TRADE bar"),
        ("exec", "execution readiness"),
        ("data", "fresh data"),
    ):
        if gaps.get(key) not in ("ok", "n/a", None):
            needs.append(label)
    if needs:
        return "Upgrade if: " + ", ".join(needs[:3]) + " · 升級需：" + "、".join(needs[:3])
    return "Confirm volume + sector rank · 確認量能與板塊排名"


def build_buy_signal_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """Attach clean buy labeling — never grants deploy permission."""
    signal_type = classify_signal_type(row)
    if signal_type not in _SIGNAL_TYPES:
        signal_type = "TREND"
    authority = _authority_label(row)
    tier = _confidence_tier(row)
    blocker = _primary_blocker(row)
    why = _why_now(row, signal_type)
    summary = _bilingual_summary(row, signal_type, authority)
    return {
        "buy_signal_summary": summary,
        "signal_type": signal_type,
        "confidence_tier": tier,
        "primary_blocker": blocker,
        "why_now": why,
        "authority_label": authority,
        "upgrade_path": _upgrade_path(row, authority),
        "surface_authority": "monitor_only" if authority != "DEPLOY" else row.get("surface_authority"),
    }


def attach_buy_signal_summary(row: Dict[str, Any]) -> Dict[str, Any]:
    """Merge buy_signal fields onto a playbook row."""
    extra = build_buy_signal_summary(row)
    merged = {**row, **extra}
    if extra["authority_label"] != "DEPLOY":
        merged.setdefault("surface_authority", "monitor_only")
    return merged


def attach_buy_signal_to_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [attach_buy_signal_summary(dict(r)) for r in rows if isinstance(r, dict)]
