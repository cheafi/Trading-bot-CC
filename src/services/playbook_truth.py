"""
Playbook truth — mutually exclusive buckets, qualification copy, operator view.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

_AVOID = frozenset({"AVOID", "NO_TRADE", "PASS", "EXIT", "REDUCE", "BLOCKED"})
_TRADE = frozenset({"TRADE", "BUY", "BUY_ON_DIP", "STRONG_TRADE", "TRADE_NOW"})
_PILOT = frozenset({"PILOT"})
_WATCH = frozenset({"WATCH", "WAIT", "WATCH_TRIGGER"})

_BUCKET_ORDER = ("Deploy", "Pilot", "Watch", "Near-miss", "Rejected")
_BUCKET_PRIORITY = {name: idx for idx, name in enumerate(_BUCKET_ORDER)}

_BUCKET_API_KEYS = {
    "Deploy": "deploy",
    "Pilot": "pilot",
    "Watch": "watch",
    "Near-miss": "near_miss",
    "Rejected": "rejected",
}


def assign_primary_bucket(
    row: Dict[str, Any],
    *,
    deploy_authority: bool = False,
    near_miss: bool = False,
    regime_state: str = "WAIT",
    daily_mode: Optional[bool] = None,
) -> str:
    """One primary bucket per candidate — Deploy|Pilot|Watch|Near-miss|Rejected."""
    act = str(row.get("effective_action") or row.get("action") or "WATCH").upper()
    if act in _AVOID:
        return "Rejected"
    if deploy_authority and bool(row.get("execution_ready")) and act in _TRADE:
        return "Deploy"
    if daily_mode is None:
        try:
            from src.services.cc_daily_trading import is_daily_trading_mode

            daily_mode = is_daily_trading_mode()
        except Exception:
            daily_mode = False
    if act in _PILOT:
        return "Pilot"
    if daily_mode:
        try:
            from src.services.cc_daily_trading import is_daily_pilot_row

            if is_daily_pilot_row(row, regime_state=regime_state):
                return "Pilot"
        except Exception:
            pass
    if near_miss or bool(row.get("near_miss")) or bool(row.get("whats_missing")):
        return "Near-miss"
    if act in _WATCH or act in _TRADE:
        return "Watch"
    try:
        score = float(row.get("score") or 0)
    except (TypeError, ValueError):
        score = 0.0
    if score >= 6.0:
        return "Near-miss"
    return "Rejected"


def secondary_tags_from_row(row: Dict[str, Any], *, deploy_authority: bool = False) -> List[str]:
    """Secondary attributes — tags on cards, not separate queue sections."""
    tags: List[str] = []
    explicit = row.get("playbook_tags") or row.get("secondary_tags") or []
    if isinstance(explicit, (list, tuple)):
        tags.extend(str(t) for t in explicit if t)

    if row.get("fastest_improving") or row.get("improvement_rank") == 1:
        tags.append("fastest_improving")
    if row.get("rr_improving") or row.get("risk_reward_improving"):
        tags.append("rr_improving")
    if row.get("sector_leader") or str(row.get("leader") or "").upper() in ("LEADER", "SECTOR_LEADER"):
        tags.append("sector_leader")
    act = str(row.get("effective_action") or row.get("action") or "").upper()
    if not deploy_authority and act in _TRADE and float(row.get("score") or 0) >= 7:
        tags.append("high_conviction_blocked")

    seen: set[str] = set()
    out: List[str] = []
    for tag in tags:
        key = str(tag).strip().lower()
        if key and key not in seen:
            seen.add(key)
            out.append(key)
    return out


def _row_with_bucket_tags(
    row: Dict[str, Any],
    bucket: str,
    *,
    deploy_authority: bool,
) -> Dict[str, Any]:
    tags = secondary_tags_from_row(row, deploy_authority=deploy_authority)
    return {
        **row,
        "primary_bucket": bucket,
        "playbook_tags": tags,
    }


def enforce_single_primary_bucket(
    buckets: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, List[Dict[str, Any]]]:
    """One ticker — one primary bucket (highest priority wins; merge secondary tags)."""
    winner: Dict[str, tuple[int, Dict[str, Any]]] = {}
    tag_accum: Dict[str, set[str]] = {}
    for bucket in _BUCKET_ORDER:
        prio = _BUCKET_PRIORITY[bucket]
        for row in buckets.get(bucket) or []:
            ticker = str(row.get("ticker") or "").upper()
            if not ticker:
                continue
            tags = secondary_tags_from_row(row)
            tag_accum.setdefault(ticker, set()).update(tags)
            prev = winner.get(ticker)
            if prev is None or prio < prev[0]:
                winner[ticker] = (prio, {**row, "primary_bucket": bucket})

    out: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _BUCKET_ORDER}
    for ticker, (_prio, row) in winner.items():
        bucket = str(row.get("primary_bucket") or "Rejected")
        merged_tags = sorted(tag_accum.get(ticker) or set())
        out.setdefault(bucket, []).append({**row, "playbook_tags": merged_tags})
    return out


def bucket_rows(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_authority: bool = False,
    near_miss_tickers: Optional[set[str]] = None,
    regime_state: str = "WAIT",
    daily_mode: Optional[bool] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Partition rows into mutually exclusive primary buckets."""
    nm = {str(t).upper() for t in (near_miss_tickers or set())}
    raw: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _BUCKET_ORDER}
    for row in rows or []:
        ticker = str(row.get("ticker") or "").upper()
        bucket = assign_primary_bucket(
            row,
            deploy_authority=deploy_authority,
            near_miss=ticker in nm,
            regime_state=regime_state,
            daily_mode=daily_mode,
        )
        raw[bucket].append(
            _row_with_bucket_tags(row, bucket, deploy_authority=deploy_authority)
        )
    return enforce_single_primary_bucket(raw)


def bucket_counts(
    rows: Optional[List[Dict[str, Any]]],
    *,
    deploy_authority: bool = False,
    near_miss_tickers: Optional[set[str]] = None,
) -> Dict[str, int]:
    buckets = bucket_rows(
        rows,
        deploy_authority=deploy_authority,
        near_miss_tickers=near_miss_tickers,
    )
    return {k: len(buckets.get(k) or []) for k in _BUCKET_ORDER}


def is_no_edge_mode(counts: Dict[str, int]) -> bool:
    """True when only rejected names remain — hide upgrade/monitor panels."""
    deploy = int(counts.get("Deploy") or 0)
    pilot = int(counts.get("Pilot") or 0)
    watch = int(counts.get("Watch") or 0)
    near = int(counts.get("Near-miss") or 0)
    rejected = int(counts.get("Rejected") or 0)
    actionable = deploy + pilot + watch + near
    return actionable == 0 and rejected > 0


def no_valid_monitors(counts: Dict[str, int]) -> bool:
    """True when watch and near-miss are both empty."""
    watch = int(counts.get("Watch") or counts.get("watch") or 0)
    near = int(counts.get("Near-miss") or counts.get("near_miss") or 0)
    return watch == 0 and near == 0


def no_edge_copy(counts: Dict[str, int]) -> str:
    """Canonical no-edge hero line."""
    return (
        "NO EDGE TODAY · "
        f"{int(counts.get('Deploy') or 0)} Deploy · "
        f"{int(counts.get('Pilot') or 0)} Pilot · "
        f"{int(counts.get('Watch') or 0)} Watch · "
        f"{int(counts.get('Near-miss') or 0)} Near-miss · "
        "Rejected hidden · Best action: do nothing"
    )


def format_playbook_qualification_line(
    *,
    setup_qualified: int = 0,
    trade_qualified: int = 0,
    execution_qualified: int = 0,
    deploy_qualified: int = 0,
    deploy_authority: bool = False,
    regime_state: str = "WAIT",
    board_gate: str = "",
) -> str:
    """Playbook strip — never 'Deploy gate open' when authority blocked."""
    if not deploy_authority or str(board_gate or "").lower() in ("wait", "closed"):
        deploy_qualified = 0
    parts: List[str] = []
    if setup_qualified:
        parts.append(f"{setup_qualified} setup-qualified")
    if trade_qualified and regime_state not in ("NO_TRADE",) and deploy_authority:
        parts.append(f"{trade_qualified} trade-qualified")
    if execution_qualified and deploy_authority and execution_qualified != deploy_qualified:
        parts.append(f"{execution_qualified} execution-qualified")
    parts.append(f"{deploy_qualified} deploy-qualified")
    line = " · ".join(parts)
    lower = line.lower()
    assert "deploy gate open" not in lower
    assert "gates open" not in lower
    return line


def playbook_qualification_for_truth(
    qualification_levels: Optional[Dict[str, Any]],
    *,
    deploy_authority: bool,
    regime_state: str,
    board_gate: str = "",
) -> str:
    lv = qualification_levels or {}
    return format_playbook_qualification_line(
        setup_qualified=int(lv.get("setup_qualified") or 0),
        trade_qualified=int(lv.get("trade_qualified") or 0),
        execution_qualified=int(lv.get("execution_qualified") or 0),
        deploy_qualified=int(lv.get("deploy_qualified") or 0),
        deploy_authority=deploy_authority,
        regime_state=regime_state,
        board_gate=board_gate,
    )


def _authority_label(truth: Dict[str, Any]) -> str:
    tier = str(truth.get("deploy_authority_tier") or truth.get("deployAuthority") or "").lower()
    if tier == "allowed" and truth.get("deploy_authority"):
        return "ALLOWED"
    if tier == "paper_only":
        return "PAPER_ONLY"
    return "BLOCKED"


def _scoped_qualification(truth: Dict[str, Any]) -> Dict[str, int]:
    """Qualification counts — zero execution/deploy when broker offline or board WAIT."""
    deploy_auth = bool(truth.get("deploy_authority"))
    broker = str(truth.get("broker_freshness") or "").lower()
    board_gate = str(truth.get("board_gate") or "").lower()
    setup_n = int(truth.get("setup_qualified_count") or truth.get("watch_qualified_count") or 0)
    trade_n = int(truth.get("trade_qualified_count") or 0)
    exec_n = int(truth.get("execution_qualified_count") or 0)
    deploy_n = int(truth.get("deploy_qualified_count") or 0)
    if broker in ("offline", "blocked", "stale"):
        exec_n = 0
        deploy_n = 0
    if board_gate in ("wait", "closed") or not deploy_auth:
        deploy_n = 0
    if not deploy_auth:
        deploy_n = 0
    return {
        "setup": setup_n,
        "trade": trade_n if deploy_auth else min(trade_n, setup_n),
        "execution": exec_n if deploy_auth and broker not in ("offline", "blocked", "stale") else 0,
        "deploy": deploy_n,
    }


def _playbook_truth_strip(truth: Dict[str, Any]) -> str:
    """Scoped Market/Board/Brief/Broker/Engine/Deploy gate — brief expired not fallback."""
    from src.services.system_truth import format_global_truth_strip

    strip = truth.get("truth_strip") or format_global_truth_strip(truth)
    brief = str(truth.get("brief_freshness") or "").lower()
    if brief == "expired":
        strip = strip.replace("Fallback", "Expired").replace("fallback", "expired")
    return strip


def _playbook_best_action(
    truth: Dict[str, Any],
    buckets: Dict[str, List[Dict[str, Any]]],
    *,
    best_action: Optional[Dict[str, Any]] = None,
) -> str:
    authority = _authority_label(truth)
    if authority == "BLOCKED":
        if is_no_edge_mode({k: len(v) for k, v in buckets.items()}):
            return "do nothing — preserve capital"
        return "monitor only — patience is the active decision"
    if authority == "PAPER_ONLY":
        return "review Simulation Drafts — no live handoff"
    deploy = buckets.get("Deploy") or []
    if deploy:
        top = deploy[0]
        return f"review deploy-qualified — {top.get('ticker') or 'top name'}"
    if best_action and isinstance(best_action, dict):
        headline = best_action.get("headline") or best_action.get("summary")
        if headline:
            return str(headline)
    return "review Playbook buckets"


def _playbook_next_steps(truth: Dict[str, Any], *, no_monitors: bool) -> List[str]:
    from src.services.authority_engine import next_action

    steps: List[str] = []
    primary = next_action(truth)
    if primary:
        steps.append(primary)
    if no_monitors:
        steps.append("No valid monitor candidates — refresh board or wait for setup")
    repair = truth.get("repair_priority") or []
    for code in repair[:2]:
        label = str(code).replace("_", " ").title()
        if label and label not in steps:
            steps.append(label)
    return steps[:4]


def build_playbook_operator_view(
    truth: Dict[str, Any],
    rows: Optional[List[Dict[str, Any]]] = None,
    *,
    near_miss_rows: Optional[List[Dict[str, Any]]] = None,
    best_action: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Single Playbook resolver — wire from resolve_system_truth() + ranked rows.

    Playbook page reads ONLY this object for authority, buckets, and copy.
    """
    t = dict(truth or {})
    deploy_auth = bool(t.get("deploy_authority"))
    regime = str(t.get("regime_state") or "WAIT").upper()
    nm_tickers = {
        str(r.get("ticker") or "").upper()
        for r in (near_miss_rows or [])
        if r.get("ticker")
    }
    merged_rows: List[Dict[str, Any]] = list(rows or [])
    seen = {str(r.get("ticker") or "").upper() for r in merged_rows}
    for row in near_miss_rows or []:
        ticker = str(row.get("ticker") or "").upper()
        if ticker and ticker not in seen:
            merged_rows.append({**row, "near_miss": True})
            seen.add(ticker)

    buckets = bucket_rows(
        merged_rows,
        deploy_authority=deploy_auth,
        near_miss_tickers=nm_tickers,
        regime_state=regime,
    )
    counts = {k: len(buckets.get(k) or []) for k in _BUCKET_ORDER}
    qual = _scoped_qualification(t)
    authority = _authority_label(t)
    no_monitors = no_valid_monitors(counts)
    simulation_hidden = authority == "BLOCKED"

    api_buckets: Dict[str, Any] = {
        "deploy": buckets.get("Deploy") or [],
        "pilot": buckets.get("Pilot") or [],
        "watch": buckets.get("Watch") or [],
        "near_miss": buckets.get("Near-miss") or [],
        "rejected_count": counts.get("Rejected") or 0,
    }

    return {
        "authority": authority,
        "truth_strip": _playbook_truth_strip(t),
        "qualification": qual,
        "qualification_line": format_playbook_qualification_line(
            setup_qualified=qual["setup"],
            trade_qualified=qual["trade"],
            execution_qualified=qual["execution"],
            deploy_qualified=qual["deploy"],
            deploy_authority=deploy_auth,
            regime_state=regime,
            board_gate=str(t.get("board_gate") or ""),
        ),
        "buckets": api_buckets,
        "best_action": _playbook_best_action(t, buckets, best_action=best_action),
        "next": _playbook_next_steps(t, no_monitors=no_monitors),
        "no_valid_monitors": no_monitors,
        "simulation_drafts_collapsed": simulation_hidden,
        "no_edge": is_no_edge_mode(counts),
        "counts": counts,
    }
