"""
Insider Form 4 context — lagged, research-only.

Stub/mock path is explicit; live EDGAR wiring is medium-term roadmap.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.services.signal_provenance import (
    SIGNAL_INSIDER_FORM4,
    build_provenance_envelope,
)

QUALITY_SUPPORTIVE_ONLY = "supportive_only"
QUALITY_NOTABLE_ACCUMULATION = "notable_accumulation"
QUALITY_NOTABLE_DISTRIBUTION = "notable_distribution"
QUALITY_NOISE = "noise"
QUALITY_INSUFFICIENT = "insufficient_data"

QUALITY_LABELS: Dict[str, str] = {
    QUALITY_SUPPORTIVE_ONLY: "Supportive context only — not a buy signal",
    QUALITY_NOTABLE_ACCUMULATION: "Notable insider accumulation — lagged context",
    QUALITY_NOTABLE_DISTRIBUTION: "Notable insider distribution — risk context",
    QUALITY_NOISE: "Routine Form 4 — low significance",
    QUALITY_INSUFFICIENT: "Insufficient Form 4 history",
}


def score_form4_significance(
    *,
    transaction_type: str,
    shares: float,
    value_usd: float,
    role: str,
    filing_count_90d: int = 0,
) -> Dict[str, Any]:
    """Heuristic significance — conservative, never implies TRADE."""
    t = (transaction_type or "").upper()
    role_l = (role or "").lower()
    score = 0.0
    if t in ("P", "PURCHASE", "A", "ACQUISITION"):
        score += 0.35
    elif t in ("S", "SALE", "D", "DISPOSITION"):
        score -= 0.25
    if value_usd >= 500_000:
        score += 0.25
    elif value_usd >= 100_000:
        score += 0.12
    if "ceo" in role_l or "cfo" in role_l or "officer" in role_l:
        score += 0.1
    if filing_count_90d >= 3:
        score += 0.08

    if score >= 0.55 and t.startswith(("P", "A")):
        quality = QUALITY_NOTABLE_ACCUMULATION
    elif score <= -0.2:
        quality = QUALITY_NOTABLE_DISTRIBUTION
    elif abs(score) < 0.15:
        quality = QUALITY_NOISE
    elif score > 0:
        quality = QUALITY_SUPPORTIVE_ONLY
    else:
        quality = QUALITY_SUPPORTIVE_ONLY

    return {
        "significance_score": round(max(-1.0, min(1.0, score)), 3),
        "quality_label": quality,
        "quality_copy": QUALITY_LABELS.get(quality, ""),
    }


def _mock_filings(ticker: str) -> List[Dict[str, Any]]:
    """Illustrative Form 4 rows — degraded/mock honest."""
    ticker.upper()
    return [
        {
            "form": "4",
            "filed_at": "2026-02-14",
            "reporting_owner": "Officer (illustrative)",
            "transaction_type": "P",
            "shares": 12000,
            "value_usd": 1850000,
            "role": "officer",
            "significance": score_form4_significance(
                transaction_type="P",
                shares=12000,
                value_usd=1850000,
                role="officer",
                filing_count_90d=2,
            ),
        },
        {
            "form": "4",
            "filed_at": "2026-01-08",
            "reporting_owner": "Director (illustrative)",
            "transaction_type": "S",
            "shares": 2500,
            "value_usd": 420000,
            "role": "director",
            "significance": score_form4_significance(
                transaction_type="S",
                shares=2500,
                value_usd=420000,
                role="director",
                filing_count_90d=1,
            ),
        },
    ]


def build_insider_context(
    ticker: str,
    *,
    use_live: bool = False,
    degraded: bool = False,
) -> Dict[str, Any]:
    """
    Dossier insider strip payload.

    use_live: when True, caller may wire EdgarClient (medium-term); default stub.
    """
    sym = ticker.upper().strip()
    now = datetime.now(timezone.utc).isoformat()
    filings = _mock_filings(sym) if not use_live else []
    cluster_quality = QUALITY_INSUFFICIENT
    if filings:
        labels = [f["significance"]["quality_label"] for f in filings]
        if QUALITY_NOTABLE_ACCUMULATION in labels:
            cluster_quality = QUALITY_NOTABLE_ACCUMULATION
        elif QUALITY_NOTABLE_DISTRIBUTION in labels:
            cluster_quality = QUALITY_NOTABLE_DISTRIBUTION
        else:
            cluster_quality = QUALITY_SUPPORTIVE_ONLY

    body = {
        "ticker": sym,
        "filings": filings,
        "cluster_quality": cluster_quality,
        "cluster_copy": QUALITY_LABELS.get(cluster_quality, ""),
        "lag_days_typical": "2–45+",
        "data_tier": "mock" if not use_live else "live",
        "monitor_trigger_type": "insider_cluster",
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_INSIDER_FORM4,
        source="mock-form4-stub" if not use_live else "edgar-live",
        as_of=now,
        degraded=degraded or not use_live,
        extra=body,
    )
