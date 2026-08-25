"""
《指数基金投资指南》Index Fund Investment Guide mode — valuation & allocation OS.

Ordinary-investor posture: broad index core, PE-percentile valuation zones,
定投 / hold / pause — honest proxy labels only. Orthogonal to stock-trading playbook.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

INDEX_FUND_LABELS: Dict[str, str] = {
    "broad_core": "broad market index — core book candidate (proxy)",
    "narrow_satellite": "narrow/sector index — satellite only (proxy)",
    "not_index": "not a passive index sleeve — index rules do not apply",
    "cheap_zone": "valuation cheap zone — favor steady 定投 (PE percentile proxy)",
    "fair_zone": "valuation fair zone — continue 定投, no urgency",
    "expensive_zone": "valuation expensive zone — hold or pause new 定投 (proxy)",
    "continue_dca": "continue 定投 — valuation supports steady accumulation",
    "hold_core": "hold core — no urgent action required",
    "pause_dca": "pause new 定投 — expensive zone proxy; hold existing",
    "lump_sum_ok": "lump-sum add OK in cheap zone — still size calmly (proxy)",
    "highly_suitable": "highly suitable for ordinary index investor",
    "caution_narrow": "sector/narrow index — size as satellite only",
    "not_primary": "tactical sleeve — not primary index-fund path",
    "no_urgent_action": "no urgent action — index investing rewards patience",
    "core_priority": "core index priority over stock picking today",
}

_BROAD_INDEX_TICKERS = frozenset(
    {
        "SPY",
        "IVV",
        "VOO",
        "VTI",
        "SCHB",
        "RSP",
        "DIA",
        "IWM",
        "QQQ",
        "VT",
        "VXUS",
        "VEA",
        "VWO",
        "BND",
        "AGG",
        "510300",
        "510500",
        "159915",
        "000300",
    }
)
_NARROW_HINTS = frozenset(
    {
        "sector",
        "semiconductor",
        "semi",
        "tech",
        "health",
        "energy",
        "financial",
        "biotech",
        "gold",
        "commodity",
        "leveraged",
        "inverse",
        "theme",
        "thematic",
        "growth",
        "value",
        "small-cap",
        "small cap",
    }
)
_INDEX_NAME_HINTS = frozenset(
    {
        "index",
        "etf",
        "tracker",
        "passive",
        "broad",
        "total market",
        "500",
        "沪深300",
        "中证",
    }
)


def _f(row: Dict[str, Any], key: str, default: float = 0.0) -> float:
    try:
        return float(row.get(key) if row.get(key) is not None else default)
    except (TypeError, ValueError):
        return default


def _pe_percentile_proxy(row: Dict[str, Any]) -> Optional[float]:
    """PE percentile proxy from row metadata — honest proxy label."""
    for key in (
        "pe_percentile",
        "pe_pct",
        "valuation_pe_percentile",
        "index_pe_percentile",
    ):
        v = row.get(key)
        if v is not None:
            try:
                pct = float(v)
                if pct > 1.0:
                    return min(100.0, max(0.0, pct))
                return min(100.0, max(0.0, pct * 100.0))
            except (TypeError, ValueError):
                continue
    pe = row.get("pe") or row.get("valuation_pe") or row.get("trailing_pe")
    if pe is not None:
        try:
            pe_f = float(pe)
            if pe_f <= 0:
                return None
            # Rough market-history proxy when only raw PE available
            if pe_f < 14:
                return 22.0
            if pe_f < 18:
                return 38.0
            if pe_f < 22:
                return 55.0
            if pe_f < 28:
                return 72.0
            return 88.0
        except (TypeError, ValueError):
            pass
    return None


def is_index_etf_symbol(ticker: str, row: Optional[Dict[str, Any]] = None) -> bool:
    """True when ticker/row looks like an index ETF (playbook tag gate)."""
    t = (ticker or "").upper().strip()
    if t in _BROAD_INDEX_TICKERS:
        return True
    r = row or {}
    asset = str(r.get("asset_class") or "").lower()
    if asset in ("etf", "index", "passive"):
        return True
    name = str(r.get("name") or r.get("display_name") or "").lower()
    return any(h in name for h in _INDEX_NAME_HINTS)


def classify_index_fund(row: Dict[str, Any]) -> Dict[str, Any]:
    """Broad vs narrow index classification from ticker/name/sector tags."""
    ticker = str(row.get("ticker") or "").upper()
    name = str(
        row.get("name") or row.get("display_name") or row.get("fund_name") or ""
    ).lower()
    sector_tags = " ".join(
        str(x).lower() for x in (row.get("sector_tags") or row.get("tags") or [])
    )
    sleeve = str(row.get("sleeve") or row.get("sleeve_type") or "").lower()
    combined = f"{name} {sector_tags} {sleeve}"

    if not is_index_etf_symbol(ticker, row) and not any(
        h in combined for h in _INDEX_NAME_HINTS
    ):
        return {
            "classification": "not_index",
            "classification_label": INDEX_FUND_LABELS["not_index"],
            "is_index": False,
            "scope": "none",
        }

    if ticker in _BROAD_INDEX_TICKERS or any(
        k in combined
        for k in ("total market", "broad", "500", "沪深300", "全市场", "标普")
    ):
        scope = "broad"
        label = INDEX_FUND_LABELS["broad_core"]
    elif any(h in combined for h in _NARROW_HINTS) or sleeve in (
        "sector",
        "thematic",
        "tactical",
    ):
        scope = "narrow"
        label = INDEX_FUND_LABELS["narrow_satellite"]
    elif ticker:
        scope = "broad" if len(ticker) <= 5 else "narrow"
        label = (
            INDEX_FUND_LABELS["broad_core"]
            if scope == "broad"
            else INDEX_FUND_LABELS["narrow_satellite"]
        )
    else:
        scope = "unknown"
        label = INDEX_FUND_LABELS["not_index"]

    return {
        "classification": scope if scope != "unknown" else "not_index",
        "classification_label": label,
        "is_index": scope in ("broad", "narrow"),
        "scope": scope,
    }


def evaluate_valuation_zone(row: Dict[str, Any]) -> Dict[str, Any]:
    """Cheap / fair / expensive zones from PE percentile proxy."""
    pct = _pe_percentile_proxy(row)
    if pct is None:
        return {
            "valuation_zone": "unknown",
            "valuation_label": "valuation data unavailable — use external index PE history (proxy)",
            "pe_percentile_proxy": None,
            "proxy": True,
        }
    if pct < 30:
        zone = "cheap"
        label = INDEX_FUND_LABELS["cheap_zone"]
    elif pct <= 70:
        zone = "fair"
        label = INDEX_FUND_LABELS["fair_zone"]
    else:
        zone = "expensive"
        label = INDEX_FUND_LABELS["expensive_zone"]
    return {
        "valuation_zone": zone,
        "valuation_label": label,
        "pe_percentile_proxy": round(pct, 1),
        "proxy": True,
    }


def evaluate_investment_mode(
    row: Dict[str, Any],
    *,
    valuation: Optional[Dict[str, Any]] = None,
    classification: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """定投 / lump-sum / hold / pause — index-fund investor modes."""
    val = valuation or evaluate_valuation_zone(row)
    cls = classification or classify_index_fund(row)
    zone = val.get("valuation_zone") or "unknown"

    if not cls.get("is_index"):
        return {
            "investment_mode": "not_applicable",
            "action": "not_applicable",
            "action_label": INDEX_FUND_LABELS["not_primary"],
            "mode_note": "Index-fund rules apply to passive index sleeves only",
        }

    if zone == "cheap":
        mode = "dca_and_lump_sum"
        action = "continue_dca"
        label = INDEX_FUND_LABELS["continue_dca"]
        note = INDEX_FUND_LABELS["lump_sum_ok"]
    elif zone == "fair":
        mode = "dca"
        action = "continue_dca"
        label = INDEX_FUND_LABELS["continue_dca"]
        note = INDEX_FUND_LABELS["fair_zone"]
    elif zone == "expensive":
        mode = "hold"
        action = "pause_dca"
        label = INDEX_FUND_LABELS["pause_dca"]
        note = INDEX_FUND_LABELS["expensive_zone"]
    else:
        mode = "hold"
        action = "hold_core"
        label = INDEX_FUND_LABELS["hold_core"]
        note = INDEX_FUND_LABELS["no_urgent_action"]

    return {
        "investment_mode": mode,
        "action": action,
        "action_label": label,
        "mode_note": note,
    }


def evaluate_core_satellite_role(row: Dict[str, Any]) -> Dict[str, Any]:
    """Core vs satellite role for index sleeves."""
    cls = classify_index_fund(row)
    scope = cls.get("scope") or cls.get("classification")
    if not cls.get("is_index"):
        return {
            "core_satellite_role": "none",
            "role_label": INDEX_FUND_LABELS["not_primary"],
        }
    if scope == "broad":
        return {
            "core_satellite_role": "core",
            "role_label": INDEX_FUND_LABELS["broad_core"],
        }
    if scope == "narrow":
        return {
            "core_satellite_role": "satellite",
            "role_label": INDEX_FUND_LABELS["narrow_satellite"],
        }
    return {
        "core_satellite_role": "unknown",
        "role_label": INDEX_FUND_LABELS["not_index"],
    }


def evaluate_ordinary_investor_suitability(row: Dict[str, Any]) -> Dict[str, Any]:
    """Ordinary-investor suitability — broad index first."""
    cls = classify_index_fund(row)
    sleeve = str(row.get("sleeve") or row.get("id") or "").upper()
    tactical = any(
        k in sleeve for k in ("LEADER", "TACTICAL", "MOMENTUM", "DEF")
    ) or str(row.get("gate_status") or "").upper() in ("ACTIVE", "REDUCED", "PAUSED")

    if tactical and not cls.get("is_index"):
        return {
            "suitability": "not_primary",
            "suitability_label": INDEX_FUND_LABELS["not_primary"],
        }
    if cls.get("scope") == "broad":
        return {
            "suitability": "highly_suitable",
            "suitability_label": INDEX_FUND_LABELS["highly_suitable"],
        }
    if cls.get("scope") == "narrow":
        return {
            "suitability": "caution",
            "suitability_label": INDEX_FUND_LABELS["caution_narrow"],
        }
    return {
        "suitability": "unknown",
        "suitability_label": INDEX_FUND_LABELS["not_index"],
    }


def evaluate_allocation_decision(row: Dict[str, Any]) -> Dict[str, Any]:
    """Full index-fund allocation decision bundle."""
    cls = classify_index_fund(row)
    val = evaluate_valuation_zone(row)
    mode = evaluate_investment_mode(row, valuation=val, classification=cls)
    role = evaluate_core_satellite_role(row)
    suit = evaluate_ordinary_investor_suitability(row)
    headline = (
        f"{mode['action'].replace('_', ' ')} · {val['valuation_zone']} zone · "
        f"{role['core_satellite_role']} role (proxy)"
    )
    return {
        "mode": "index_fund_guide",
        "classification": cls,
        "valuation": val,
        "investment_mode": mode,
        "core_satellite_role": role,
        "suitability": suit,
        "headline": headline,
        "authority": "research_only",
        "model_note": "PE percentile and scope are proxies — not live fund factsheet data",
    }


def evaluate_index_fund_judgment(row: Dict[str, Any]) -> Dict[str, Any]:
    """Alias for tests and dossier hooks."""
    return evaluate_allocation_decision(row)


def _benchmark_rows(
    benchmark: str = "SPY",
    *,
    market_pe_percentile: Optional[float] = None,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for sym in (benchmark.upper(), "QQQ", "VTI"):
        r: Dict[str, Any] = {"ticker": sym, "name": f"{sym} index proxy"}
        if market_pe_percentile is not None and sym == benchmark.upper():
            r["pe_percentile"] = market_pe_percentile
        rows.append(r)
    return rows


def index_fund_posture_strip_for_today(
    market_regime: Dict[str, Any],
    decision_model: Optional[Dict[str, Any]] = None,
    *,
    benchmark: str = "SPY",
    market_pe_percentile: Optional[float] = None,
) -> Dict[str, Any]:
    """Dashboard index_fund_posture strip — calm, no-urgency copy."""
    dm = decision_model or {}
    pe_pct = market_pe_percentile
    if pe_pct is None:
        pe_pct = dm.get("market_pe_percentile") or market_regime.get("pe_percentile")
    bench_row = {"ticker": benchmark.upper(), "pe_percentile": pe_pct}
    val = evaluate_valuation_zone(bench_row)
    mode = evaluate_investment_mode(bench_row, valuation=val)
    zone = val.get("valuation_zone") or "unknown"

    valuation_summary = f"{benchmark.upper()} · {zone} zone" + (
        f" · PE pct proxy {val['pe_percentile_proxy']:.0f}%"
        if val.get("pe_percentile_proxy") is not None
        else " · PE proxy unavailable"
    )

    return {
        "mode": "index_fund_guide",
        "headline": INDEX_FUND_LABELS["no_urgent_action"],
        "banner": INDEX_FUND_LABELS["core_priority"],
        "core_priority": True,
        "valuation_summary": valuation_summary,
        "valuation_zone": zone,
        "valuation_label": val.get("valuation_label"),
        "pe_percentile_proxy": val.get("pe_percentile_proxy"),
        "recommended_action": mode.get("action"),
        "action_label": mode.get("action_label"),
        "urgent_action_required": False,
        "proxy": True,
        "model_note": "Index posture uses PE percentile proxy — not a buy/sell signal",
    }


def enrich_fund_card_index_layer(
    card: Dict[str, Any], *, benchmark: str = "SPY"
) -> Dict[str, Any]:
    """Attach index-fund judgment to a fund sleeve card (holdings + benchmark)."""
    out = dict(card)
    holdings = card.get("holdings") or []
    index_holdings: List[Dict[str, Any]] = []
    for h in holdings[:8]:
        ticker = str(h.get("ticker") or "")
        row = {**h, "name": h.get("name") or ticker}
        if is_index_etf_symbol(ticker, row):
            j = evaluate_allocation_decision(row)
            index_holdings.append(
                {
                    "ticker": ticker,
                    "classification": j["classification"]["classification"],
                    "valuation_zone": j["valuation"]["valuation_zone"],
                    "action": j["investment_mode"]["action"],
                    "action_label": j["investment_mode"]["action_label"],
                    "core_satellite_role": j["core_satellite_role"][
                        "core_satellite_role"
                    ],
                }
            )

    bench = evaluate_allocation_decision(
        {"ticker": benchmark.upper(), "name": f"{benchmark} broad index"}
    )
    out["index_fund_layer"] = {
        "benchmark": benchmark.upper(),
        "benchmark_judgment": {
            "valuation_zone": bench["valuation"]["valuation_zone"],
            "action": bench["investment_mode"]["action"],
            "action_label": bench["investment_mode"]["action_label"],
            "valuation_summary": bench["valuation"].get("valuation_label"),
        },
        "index_holdings": index_holdings,
        "investor_note": (
            "Index posture (定投/hold/pause) takes priority over tactical sleeve signals — "
            "research sleeves below are secondary context."
        ),
        "proxy": True,
    }
    return out


def enrich_funds_console_index_layer(
    console: Dict[str, Any],
    *,
    benchmark: str = "SPY",
    market_pe_percentile: Optional[float] = None,
) -> Dict[str, Any]:
    """Merge index-fund layer into fund console payload."""
    out = dict(console)
    cards = out.get("cards") or []
    enriched_cards = [
        enrich_fund_card_index_layer(c, benchmark=benchmark) for c in cards
    ]
    out["cards"] = enriched_cards

    posture = index_fund_posture_strip_for_today(
        {
            "tradeability": out.get("tradeability") or "",
            "vix": out.get("vix"),
        },
        benchmark=benchmark,
        market_pe_percentile=market_pe_percentile,
    )
    out["index_fund_posture"] = posture
    out["index_fund_mode_note"] = (
        "Funds tab: index valuation & 定投 posture first; tactical sleeve research demoted."
    )
    return out


def index_fund_alignment_for_core_satellite(
    positions: List[Dict[str, Any]],
    *,
    benchmark: str = "SPY",
) -> Dict[str, Any]:
    """Link core_passive band to index-fund core logic."""
    core_tickers: List[str] = []
    for p in positions:
        ticker = str(p.get("ticker") or "").upper()
        role = str(p.get("sleeve_role") or "").lower()
        if (
            role == "core_passive"
            or ticker in _BROAD_INDEX_TICKERS
            or is_index_etf_symbol(ticker, p)
        ):
            j = evaluate_allocation_decision({**p, "ticker": ticker})
            if j["classification"].get("is_index") or ticker in _BROAD_INDEX_TICKERS:
                core_tickers.append(ticker)

    bench = evaluate_allocation_decision({"ticker": benchmark.upper()})
    actions = {
        t: evaluate_allocation_decision({"ticker": t}).get("investment_mode", {})
        for t in core_tickers[:5]
    }

    return {
        "benchmark": benchmark.upper(),
        "core_index_tickers": core_tickers[:6],
        "benchmark_valuation_zone": bench["valuation"]["valuation_zone"],
        "benchmark_action": bench["investment_mode"]["action"],
        "benchmark_action_label": bench["investment_mode"]["action_label"],
        "holdings_actions": {
            t: a.get("action_label") or a.get("action") for t, a in actions.items()
        },
        "alignment_note": (
            "Core passive sleeve aligns with index-fund guide: broad index, "
            "valuation-zone 定投/hold/pause — not stock-trading urgency."
        ),
        "proxy": True,
    }


def tags_for_playbook_row(
    row: Dict[str, Any], *, tradeability: str = ""
) -> Dict[str, Any]:
    """Optional playbook tags — only when row maps to ETF/index symbol."""
    ticker = str(row.get("ticker") or "")
    if not is_index_etf_symbol(ticker, row):
        return {}
    j = evaluate_allocation_decision(row)
    return {
        "index_fund_scope": j["classification"]["classification"],
        "index_fund_valuation_zone": j["valuation"]["valuation_zone"],
        "index_fund_action": j["investment_mode"]["action"],
        "index_fund_action_label": j["investment_mode"]["action_label"],
        "index_fund_core_role": j["core_satellite_role"]["core_satellite_role"],
        "index_fund_suitability": j["suitability"]["suitability"],
    }
