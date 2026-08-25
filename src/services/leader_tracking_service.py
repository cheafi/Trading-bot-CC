"""
Leader / Holdings Tracking — business logic, seed data, consensus & flow scores.

Trust rules:
- Never upgrade inferred/speculative rows to verified in API responses.
- Flow confirmation uses heuristic OHLCV/options proxies unless real feed wired.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services import leader_persistence as store

logger = logging.getLogger(__name__)

SOURCE_QUALITY_LABELS = {
    "verified": "Verified",
    "delayed": "Delayed disclosure",
    "derived": "Derived",
    "inferred": "Inferred",
    "speculative": "Speculative",
}

ACTION_LABELS = {
    "new_buy": "New Buy",
    "add": "Add",
    "reduce": "Reduce",
    "exit": "Exit",
    "unchanged": "Unchanged",
    "mention_only": "Mention only",
}


def ensure_seeded(force: bool = False) -> None:
    if not force and store.get_meta("seeded_v1") == "1":
        return
    if force:
        store.clear_demo_data()
    _seed_demo_leaders()
    _rebuild_consensus()
    _seed_flow_signals()
    _seed_baskets()
    _seed_alerts()
    store.set_meta("seeded_v1", "1")
    logger.info("Leader tracking demo data seeded")


def _seed_demo_leaders() -> None:
    leaders = [
        {
            "id": "trump-disclosure",
            "name": "Donald J. Trump (Disclosed)",
            "slug": "trump-disclosure",
            "category": "public_figure",
            "entity_type": "Politician / Public Figure",
            "description": "Tracked from public financial disclosure summaries — delayed, not live execution.",
            "focus_area": "Policy-linked mega-cap rotation",
            "source_type": "official_disclosure",
            "source_quality": "delayed",
            "disclosure_delay_days": 45,
            "region": "US",
        },
        {
            "id": "berkshire-13f",
            "name": "Berkshire Hathaway (13F)",
            "slug": "berkshire-13f",
            "category": "verified_filer",
            "entity_type": "Fund Manager / 13F",
            "description": "Quarterly 13F-HR filings — positions lag ~45 days.",
            "focus_area": "Quality compounders, financials, energy",
            "source_type": "sec_13f",
            "source_quality": "verified",
            "disclosure_delay_days": 45,
            "region": "US",
        },
        {
            "id": "ark-invest",
            "name": "ARK Invest (13F)",
            "slug": "ark-invest",
            "category": "fund_manager",
            "entity_type": "Fund Manager / 13F",
            "description": "High-turnover innovation-focused 13F filer.",
            "focus_area": "Innovation, genomics, fintech",
            "source_type": "sec_13f",
            "source_quality": "verified",
            "disclosure_delay_days": 45,
            "region": "US",
        },
        {
            "id": "pelosi-disclosure",
            "name": "Nancy Pelosi (Congress)",
            "slug": "pelosi-disclosure",
            "category": "public_figure",
            "entity_type": "Politician",
            "description": "Congressional disclosure — STOCK Act delayed reporting.",
            "focus_area": "Tech options / semis",
            "source_type": "congress_disclosure",
            "source_quality": "delayed",
            "disclosure_delay_days": 30,
            "region": "US",
        },
        {
            "id": "kol-tech-leaps",
            "name": "Tech LEAPS Tracker (KOL)",
            "slug": "kol-tech-leaps",
            "category": "influencer",
            "entity_type": "Influencer / Idea Leader",
            "description": "Public posts + flow inference — NOT verified holdings.",
            "focus_area": "LEAPS, semis, mega-cap tech",
            "source_type": "social_interpretation",
            "source_quality": "inferred",
            "disclosure_delay_days": 0,
            "region": "US",
        },
        {
            "id": "spy-etf-holdings",
            "name": "SPY (ETF Holdings)",
            "slug": "spy-etf",
            "category": "etf",
            "entity_type": "ETF / Public Portfolio",
            "description": "ETF disclosed constituents — official but not active manager intent.",
            "focus_area": "Broad US large-cap",
            "source_type": "etf_disclosure",
            "source_quality": "verified",
            "disclosure_delay_days": 1,
            "region": "US",
        },
    ]
    for L in leaders:
        store.upsert_leader(L)

    holdings_seed = [
        # Trump timeline-style (derived from news summaries — delayed)
        ("trump-disclosure", "NVDA", "new_buy", "large", "delayed", "2026-02-10", "Technology", "AI / Semis", 1, 0, "watch"),
        ("trump-disclosure", "ORCL", "new_buy", "medium", "delayed", "2026-02-10", "Technology", "Cloud", 1, 0, "needs_confirmation"),
        ("trump-disclosure", "MSFT", "reduce", "medium", "delayed", "2026-02-10", "Technology", "Mega-cap", 1, 0, "watch"),
        ("trump-disclosure", "AAPL", "add", "medium", "delayed", "2026-03-02", "Technology", "Mega-cap", 1, 0, "follow"),
        ("trump-disclosure", "VOO", "add", "small", "delayed", "2026-03-02", "ETF", "Index", 1, 0, "watch"),
        # Berkshire
        ("berkshire-13f", "AAPL", "unchanged", "very_large", "verified", "2025-11-14", "Technology", "Quality", 1, 0, "watch"),
        ("berkshire-13f", "BAC", "unchanged", "large", "verified", "2025-11-14", "Financials", "Banks", 1, 0, "watch"),
        ("berkshire-13f", "OXY", "add", "medium", "verified", "2025-11-14", "Energy", "Oil", 1, 0, "watch"),
        # ARK
        ("ark-invest", "TSLA", "reduce", "medium", "verified", "2025-11-14", "Consumer", "EV", 1, 0, "avoid"),
        ("ark-invest", "COIN", "add", "small", "verified", "2025-11-14", "Financials", "Crypto", 1, 0, "watch"),
        ("ark-invest", "ROKU", "exit", "small", "verified", "2025-11-14", "Technology", "Streaming", 1, 0, "avoid"),
        # Pelosi
        ("pelosi-disclosure", "NVDA", "add", "medium", "delayed", "2026-01-20", "Technology", "Semis", 1, 0, "too_late"),
        ("pelosi-disclosure", "AVGO", "new_buy", "small", "delayed", "2026-01-20", "Technology", "Semis", 1, 0, "watch"),
        # Influencer (inferred)
        ("kol-tech-leaps", "NVDA", "mention_only", "unknown", "inferred", "2026-03-15", "Technology", "LEAPS", 0, 1, "needs_confirmation"),
        ("kol-tech-leaps", "AMD", "mention_only", "unknown", "inferred", "2026-03-15", "Technology", "LEAPS", 0, 1, "speculative"),
        ("kol-tech-leaps", "SMCI", "mention_only", "unknown", "speculative", "2026-03-18", "Technology", "AI infra", 0, 1, "avoid"),
        # SPY top weights (illustrative)
        ("spy-etf-holdings", "AAPL", "unchanged", "top10", "verified", "2026-03-20", "Technology", "Index", 1, 0, "watch"),
        ("spy-etf-holdings", "MSFT", "unchanged", "top10", "verified", "2026-03-20", "Technology", "Index", 1, 0, "watch"),
        ("spy-etf-holdings", "NVDA", "unchanged", "top10", "verified", "2026-03-20", "Technology", "Index", 1, 0, "watch"),
    ]
    for row in holdings_seed:
        lid, tkr, act, bucket, qual, disc, sector, theme, ver, inf, actionability = row
        store.insert_holding({
            "leader_id": lid,
            "ticker": tkr,
            "security_name": tkr,
            "action_type": act,
            "size_bucket": bucket,
            "source_name": "demo_seed",
            "source_quality": qual,
            "disclosure_date": disc,
            "effective_date": disc,
            "sector": sector,
            "theme": theme,
            "verified_flag": ver,
            "inferred_flag": inf,
            "actionability": actionability,
            "setup_quality": "neutral",
            "notes": "Demo row — replace with live ingestion",
        })

    events_seed = [
        ("trump-disclosure", "2026-02-10", "NVDA,ORCL,BA", "reduce", "Sold MSFT/META/AMZN; added NVDA/ORCL per disclosure summary", "delayed", "Rotation into AI infra"),
        ("trump-disclosure", "2026-03-02", "AAPL,GOOGL,VOO", "add", "Added AAPL, GOOGL, broad index exposure", "delayed", "Mega-cap add"),
        ("berkshire-13f", "2025-11-14", "OXY", "add", "Increased OXY weight in latest 13F", "verified", "Energy overweight"),
        ("ark-invest", "2025-11-14", "ROKU", "exit", "Exited ROKU position", "verified", "Trim speculative"),
        ("kol-tech-leaps", "2026-03-15", "NVDA", "mention_only", "Discussed LEAPS OI build — not a verified holding", "inferred", "Options narrative"),
    ]
    for lid, edate, tkr, etype, summary, qual, ctx in events_seed:
        store.insert_event({
            "leader_id": lid,
            "ticker": tkr,
            "event_type": etype,
            "event_date": edate,
            "disclosure_date": edate,
            "summary": summary,
            "source_quality": qual,
            "context_tag": ctx,
            "source_name": "demo_seed",
        })


def _rebuild_consensus() -> None:
    conn = store._get_db()
    try:
        rows = conn.execute(
            "SELECT ticker, action_type, source_quality, leader_id FROM leader_holdings",
        ).fetchall()
    finally:
        conn.close()

    agg: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "mention_count": 0,
        "verified_count": 0,
        "inferred_count": 0,
        "add_count": 0,
        "reduce_count": 0,
        "exit_count": 0,
        "new_buy_count": 0,
        "leaders": set(),
    })
    for r in rows:
        t = r["ticker"]
        a = agg[t]
        a["mention_count"] += 1
        a["leaders"].add(r["leader_id"])
        sq = r["source_quality"]
        if sq in ("verified", "delayed"):
            a["verified_count"] += 1
        else:
            a["inferred_count"] += 1
        act = r["action_type"]
        if act == "add":
            a["add_count"] += 1
        elif act == "reduce":
            a["reduce_count"] += 1
        elif act == "exit":
            a["exit_count"] += 1
        elif act == "new_buy":
            a["new_buy_count"] += 1

    for ticker, a in agg.items():
        overlap = len(a["leaders"])
        score = (
            overlap * 15
            + a["new_buy_count"] * 10
            + a["add_count"] * 8
            - a["reduce_count"] * 5
            - a["exit_count"] * 8
            + a["verified_count"] * 3
            - a["inferred_count"] * 2
        )
        store.upsert_consensus({
            "ticker": ticker,
            "mention_count": a["mention_count"],
            "verified_count": a["verified_count"],
            "inferred_count": a["inferred_count"],
            "add_count": a["add_count"],
            "reduce_count": a["reduce_count"],
            "exit_count": a["exit_count"],
            "new_buy_count": a["new_buy_count"],
            "consensus_score": round(max(0, score), 1),
            "flow_confirmation_score": 0,
        })


def _seed_flow_signals() -> None:
    """Heuristic flow scores for demo — labeled synthetic in API."""
    demo = [
        ("NVDA", 42, 68, 12, 55, 72, 78),
        ("ORCL", 18, 35, 8, 28, 45, 52),
        ("AAPL", 5, 12, 3, 10, 38, 41),
        ("AMD", 55, 72, 18, 62, 48, 65),
        ("SMCI", 38, 45, 22, 40, 25, 38),
        ("MSFT", -8, 5, -2, 8, 35, 28),
    ]
    for t, leaps, far, iv, unusual, spot, final in demo:
        store.upsert_flow_signal({
            "ticker": t,
            "leaps_oi_change": leaps,
            "far_dated_flow_score": far,
            "iv_term_change": iv,
            "unusual_flow_score": unusual,
            "spot_confirmation_score": spot,
            "final_confirmation_score": final,
            "data_mode": "heuristic",
        })
    # Attach flow scores to consensus
    for row in store.list_consensus():
        fs = store.get_flow_signal(row["ticker"])
        if fs:
            row["flow_confirmation_score"] = fs["final_confirmation_score"]
            store.upsert_consensus(row)


def _seed_baskets() -> None:
    baskets = [
        {
            "id": "basket-trump-disclosed",
            "name": "Trump Disclosed Basket",
            "basket_type": "public_figure",
            "methodology": "Latest disclosed adds from public figure tracker",
            "rebalance_rule": "On new disclosure filing",
            "benchmark": "SPY",
        },
        {
            "id": "basket-13f-tech-accum",
            "name": "13F Tech Accumulation",
            "basket_type": "consensus",
            "methodology": "Overlap of verified 13F adds in technology",
            "rebalance_rule": "Quarterly",
            "benchmark": "QQQ",
        },
        {
            "id": "basket-leaps-confirmed",
            "name": "LEAPS-Confirmed Names",
            "basket_type": "flow",
            "methodology": "Names with disclosure + heuristic flow score > 60",
            "rebalance_rule": "Weekly",
            "benchmark": "SPY",
        },
    ]
    for b in baskets:
        store.upsert_basket(b)

    members = [
        ("basket-trump-disclosed", "NVDA", 0.22),
        ("basket-trump-disclosed", "ORCL", 0.18),
        ("basket-trump-disclosed", "AAPL", 0.15),
        ("basket-trump-disclosed", "VOO", 0.12),
        ("basket-13f-tech-accum", "NVDA", 0.25),
        ("basket-13f-tech-accum", "AAPL", 0.20),
        ("basket-13f-tech-accum", "AVGO", 0.15),
        ("basket-leaps-confirmed", "NVDA", 0.30),
        ("basket-leaps-confirmed", "AMD", 0.20),
    ]
    for bid, tkr, w in members:
        store.insert_basket_member({
            "basket_id": bid,
            "ticker": tkr,
            "weight": w,
            "source_basis": "demo_seed",
        })


def _seed_alerts() -> None:
    alerts = [
        {
            "alert_type": "new_disclosure",
            "related_entity_type": "leader",
            "related_entity_id": "trump-disclosure",
            "ticker": "AAPL",
            "severity": "info",
            "message": "New add: AAPL in public disclosure summary (delayed)",
        },
        {
            "alert_type": "consensus_cluster",
            "ticker": "NVDA",
            "severity": "warn",
            "message": "NVDA: 4 leaders overlap — verify delay before acting",
        },
        {
            "alert_type": "flow_confirmed",
            "ticker": "NVDA",
            "severity": "info",
            "message": "NVDA flow confirmation score 78 (heuristic — not live OI)",
        },
    ]
    for a in alerts:
        store.insert_alert(a)


def _leader_metrics(leader_id: str) -> Dict[str, Any]:
    holdings = store.get_holdings(leader_id)
    events = store.get_events(leader_id)
    adds = sum(1 for h in holdings if h["action_type"] in ("add", "new_buy"))
    reduces = sum(1 for h in holdings if h["action_type"] in ("reduce", "exit"))
    sectors: Dict[str, int] = defaultdict(int)
    for h in holdings:
        if h.get("sector"):
            sectors[h["sector"]] += 1
    top_sectors = sorted(sectors.items(), key=lambda x: -x[1])[:3]
    return {
        "active_holdings": len(holdings),
        "events_30d": len(events),
        "adds_30d": adds,
        "reductions_30d": reduces,
        "top_sectors": [{"sector": s, "count": c} for s, c in top_sectors],
    }


def _decision_box(leader: Dict[str, Any], holding: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sq = (holding or {}).get("source_quality") or leader.get("source_quality")
    verifiable = sq in ("verified", "delayed")
    delayed = sq in ("delayed",) or leader.get("disclosure_delay_days", 0) > 7
    inferred = sq in ("inferred", "speculative") or (holding or {}).get("inferred_flag")
    actionability = (holding or {}).get("actionability") or "watch"
    return {
        "verifiable": verifiable,
        "delayed_disclosure": delayed,
        "disclosure_delay_days": leader.get("disclosure_delay_days", 0),
        "spot_or_options": "options_inferred" if sq == "speculative" else "spot_disclosed",
        "repeat_accumulation": (holding or {}).get("action_type") in ("add", "new_buy"),
        "recommendation": actionability,
        "labels": {
            "verified": verifiable and not inferred,
            "inferred": bool(inferred),
            "not_verified_holding": sq in ("inferred", "speculative"),
        },
        "warnings": _warnings_for(leader, holding),
    }


def _warnings_for(leader: Dict[str, Any], holding: Optional[Dict[str, Any]]) -> List[str]:
    w: List[str] = []
    sq = (holding or {}).get("source_quality") or leader.get("source_quality")
    if sq in ("inferred", "speculative"):
        w.append("Not a verified holding — interpretation / flow inference only")
    if leader.get("disclosure_delay_days", 0) > 30:
        w.append("Disclosure may be delayed 30+ days — not an execution signal")
    if (holding or {}).get("action_type") == "mention_only":
        w.append("Mention only — do not treat as portfolio position")
    return w


def list_leaders_enriched(
    category: Optional[str] = None,
    source_quality: Optional[str] = None,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    ensure_seeded()
    out = []
    for L in store.list_leaders(category=category, source_quality=source_quality, search=search):
        m = _leader_metrics(L["id"])
        holdings = store.get_holdings(L["id"])
        out.append({
            **L,
            "source_quality_label": SOURCE_QUALITY_LABELS.get(L["source_quality"], L["source_quality"]),
            "metrics": m,
            "recent_tickers": [h["ticker"] for h in holdings[:5]],
            "last_update": max((h["last_seen_at"] for h in holdings), default=L["updated_at"]),
        })
    return out


def get_leader_detail(leader_id: str) -> Optional[Dict[str, Any]]:
    ensure_seeded()
    L = store.get_leader(leader_id)
    if not L:
        return None
    holdings = store.get_holdings(leader_id)
    for h in holdings:
        h["action_label"] = ACTION_LABELS.get(h["action_type"], h["action_type"])
        h["source_quality_label"] = SOURCE_QUALITY_LABELS.get(
            h["source_quality"], h["source_quality"],
        )
        h["decision"] = _decision_box(L, h)
    events = store.get_events(leader_id)
    return {
        **L,
        "source_quality_label": SOURCE_QUALITY_LABELS.get(L["source_quality"], L["source_quality"]),
        "metrics": _leader_metrics(leader_id),
        "holdings": holdings,
        "timeline": events,
        "decision": _decision_box(L),
        "trust": {
            "data_mode": "DEMO_SEED" if store.get_meta("seeded_v1") else "LIVE",
            "never_mix_inferred_with_verified": True,
        },
    }


def get_consensus_list(verified_only: bool = False, min_overlap: int = 2) -> Dict[str, Any]:
    ensure_seeded()
    rows = store.list_consensus(verified_only=verified_only, min_overlap=min_overlap)
    for r in rows:
        fs = store.get_flow_signal(r["ticker"])
        r["flow"] = fs
        r["actionability"] = _actionability_from_scores(r)
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "verified_only": verified_only,
        "items": rows,
        "summary": {
            "most_accumulated": sorted(rows, key=lambda x: -(x.get("add_count", 0) + x.get("new_buy_count", 0)))[:8],
            "most_reduced": sorted(rows, key=lambda x: -x.get("reduce_count", 0))[:8],
            "highest_overlap": sorted(rows, key=lambda x: -x.get("mention_count", 0))[:8],
        },
    }


def get_consensus_ticker(ticker: str) -> Dict[str, Any]:
    ensure_seeded()
    t = ticker.upper()
    holders = []
    conn = store._get_db()
    try:
        rows = conn.execute(
            """
            SELECT h.*, l.name AS leader_name, l.category, l.entity_type
            FROM leader_holdings h
            JOIN leaders l ON l.id = h.leader_id
            WHERE h.ticker = ?
            """,
            (t,),
        ).fetchall()
        holders = [dict(r) for r in rows]
    finally:
        conn.close()
    consensus = None
    for row in store.list_consensus(min_overlap=1):
        if row["ticker"] == t:
            consensus = row
            break
    flow = store.get_flow_signal(t)
    return {
        "ticker": t,
        "consensus": consensus,
        "leaders": holders,
        "flow": flow,
        "decision": {
            "actionability": _actionability_from_scores(consensus or {}),
            "warnings": [
                "Cross-check disclosure delay before trading",
                "Flow scores are heuristic unless marked verified feed",
            ],
        },
    }


def _actionability_from_scores(row: Dict[str, Any]) -> str:
    flow = row.get("flow_confirmation_score") or 0
    verified = row.get("verified_count", 0) or 0
    inferred = row.get("inferred_count", 0) or 0
    if inferred > verified:
        return "needs_confirmation"
    if flow >= 70 and verified >= 2:
        return "follow"
    if flow >= 50:
        return "watch"
    if row.get("reduce_count", 0) > row.get("add_count", 0):
        return "avoid"
    return "watch"


def get_flow_tracked() -> Dict[str, Any]:
    ensure_seeded()
    signals = store.list_flow_signals()
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "data_mode": "heuristic",
        "disclaimer": "LEAPS/OI/IV scores are heuristic proxies — not exchange-confirmed flow.",
        "items": signals,
    }


def get_flow_ticker(ticker: str) -> Dict[str, Any]:
    ensure_seeded()
    t = ticker.upper()
    flow = store.get_flow_signal(t)
    consensus = get_consensus_ticker(t)
    return {
        "ticker": t,
        "flow": flow,
        "consensus": consensus.get("consensus"),
        "leaders": consensus.get("leaders", []),
        "confirmation_breakdown": {
            "official_disclosure": sum(
                1 for h in consensus.get("leaders", [])
                if h.get("source_quality") in ("verified", "delayed")
            ),
            "inferred_mentions": sum(
                1 for h in consensus.get("leaders", [])
                if h.get("source_quality") in ("inferred", "speculative")
            ),
            "leaps_signal": (flow or {}).get("leaps_oi_change"),
            "iv_signal": (flow or {}).get("iv_term_change"),
            "oi_proxy": (flow or {}).get("unusual_flow_score"),
            "final_score": (flow or {}).get("final_confirmation_score"),
        },
        "data_mode": (flow or {}).get("data_mode", "heuristic"),
    }


def get_dashboard_cards() -> Dict[str, Any]:
    ensure_seeded()
    leaders = list_leaders_enriched()
    moves = []
    for L in leaders[:6]:
        for h in store.get_holdings(L["id"])[:2]:
            if h["action_type"] not in ("unchanged",):
                moves.append({
                    "leader_name": L["name"],
                    "leader_id": L["id"],
                    "ticker": h["ticker"],
                    "action": ACTION_LABELS.get(h["action_type"], h["action_type"]),
                    "source_quality": h["source_quality"],
                    "source_quality_label": SOURCE_QUALITY_LABELS.get(h["source_quality"], ""),
                    "disclosure_date": h.get("disclosure_date"),
                    "size_bucket": h.get("size_bucket"),
                })
    verified_updates = [
        m for m in moves if m["source_quality"] in ("verified", "delayed")
    ]
    consensus = get_consensus_list(min_overlap=2)
    flow_items = [x for x in store.list_flow_signals() if x.get("final_confirmation_score", 0) >= 60]
    return {
        "as_of": datetime.now(timezone.utc).isoformat(),
        "top_leader_moves": moves[:12],
        "verified_holdings_updates": verified_updates[:8],
        "consensus_accumulation": consensus["summary"]["most_accumulated"][:6],
        "flow_confirmed_names": flow_items[:6],
        "alerts": store.list_alerts(unseen_only=True)[:10],
    }


def list_baskets_enriched() -> List[Dict[str, Any]]:
    ensure_seeded()
    out = []
    for b in store.list_baskets():
        full = store.get_basket(b["id"])
        if full:
            full["performance"] = {
                "total_return_pct": None,
                "benchmark_return_pct": None,
                "note": "Shadow basket performance — connect backtest engine for live metrics",
            }
            out.append(full)
    return out


def get_alerts() -> List[Dict[str, Any]]:
    ensure_seeded()
    return store.list_alerts(unseen_only=False)
