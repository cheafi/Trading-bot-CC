"""
Index-relative leadership — per-name vs SPY/QQQ/sector labels (confirm-only).

Research / dossier context — never standalone deploy trigger.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

LEADER_OUTPERFORM = "outperform"
LEADER_INLINE = "inline"
LEADER_LAG = "lag"
LEADER_UNKNOWN = "unknown"

LEADER_LABELS: Dict[str, str] = {
    LEADER_OUTPERFORM: "Outperforming benchmark (confirm-only)",
    LEADER_INLINE: "Inline with benchmark",
    LEADER_LAG: "Lagging benchmark — downgrade filter hint",
    LEADER_UNKNOWN: "Relative data unavailable — MOCK/DEGRADED",
}


def _relative_label(delta_pct: Optional[float], *, threshold: float = 1.5) -> str:
    if delta_pct is None:
        return LEADER_UNKNOWN
    d = float(delta_pct)
    if d >= threshold:
        return LEADER_OUTPERFORM
    if d <= -threshold:
        return LEADER_LAG
    return LEADER_INLINE


def resolve_index_leadership(
    *,
    ticker: str,
    sector: str = "",
    change_20d_pct: Optional[float] = None,
    spy_20d_pct: Optional[float] = None,
    qqq_20d_pct: Optional[float] = None,
    sector_20d_pct: Optional[float] = None,
    degraded: bool = False,
) -> Dict[str, Any]:
    sym = (ticker or "").upper().strip()
    vs_spy = (
        change_20d_pct - spy_20d_pct
        if change_20d_pct is not None and spy_20d_pct is not None
        else None
    )
    vs_qqq = (
        change_20d_pct - qqq_20d_pct
        if change_20d_pct is not None and qqq_20d_pct is not None
        else None
    )
    vs_sector = (
        change_20d_pct - sector_20d_pct
        if change_20d_pct is not None and sector_20d_pct is not None
        else None
    )

    spy_tag = _relative_label(vs_spy)
    qqq_tag = _relative_label(vs_qqq)
    sector_tag = _relative_label(vs_sector)

    scores = {
        LEADER_OUTPERFORM: 2,
        LEADER_INLINE: 1,
        LEADER_LAG: 0,
        LEADER_UNKNOWN: -1,
    }
    composite_score = sum(scores.get(t, -1) for t in (spy_tag, qqq_tag, sector_tag))
    if composite_score >= 4:
        composite = LEADER_OUTPERFORM
    elif composite_score <= 0:
        composite = LEADER_LAG
    elif composite_score >= 2:
        composite = LEADER_INLINE
    else:
        composite = LEADER_UNKNOWN

    any_missing = LEADER_UNKNOWN in (spy_tag, qqq_tag, sector_tag)
    return {
        "ticker": sym,
        "sector": sector,
        "authority": "confirmation_only",
        "monitor_only": True,
        "degraded": degraded or any_missing,
        "vs_spy": {
            "tag": spy_tag,
            "label": LEADER_LABELS[spy_tag],
            "delta_20d_pct": round(vs_spy, 2) if vs_spy is not None else None,
        },
        "vs_qqq": {
            "tag": qqq_tag,
            "label": LEADER_LABELS[qqq_tag],
            "delta_20d_pct": round(vs_qqq, 2) if vs_qqq is not None else None,
        },
        "vs_sector": {
            "tag": sector_tag,
            "label": LEADER_LABELS[sector_tag],
            "delta_20d_pct": round(vs_sector, 2) if vs_sector is not None else None,
        },
        "composite": composite,
        "composite_label": LEADER_LABELS[composite],
        "index_leadership": composite,
        "summary": (
            f"{sym}: SPY {spy_tag} · QQQ {qqq_tag} · sector {sector_tag}"
            + (" — MOCK/DEGRADED" if degraded or any_missing else " — confirm-only")
        ),
    }


def leadership_from_row(
    row: Dict[str, Any],
    *,
    index_regime: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Derive leadership tags from playbook / scanner row fields."""
    cross = (index_regime or {}).get("cross_asset") or {}
    spy_20d = None
    qqq_20d = None
    for asset in cross.get("assets") or []:
        sym = asset.get("symbol")
        ch = asset.get("change_20d_pct")
        if sym == "SPY":
            spy_20d = ch
        elif sym == "QQQ":
            qqq_20d = ch
    return resolve_index_leadership(
        ticker=str(row.get("ticker") or ""),
        sector=str(row.get("sector_bucket") or row.get("sector") or ""),
        change_20d_pct=row.get("change_20d_pct") or row.get("return_20d_pct"),
        spy_20d_pct=spy_20d,
        qqq_20d_pct=qqq_20d,
        sector_20d_pct=row.get("sector_return_20d_pct"),
        degraded=bool((index_regime or {}).get("degraded")),
    )
