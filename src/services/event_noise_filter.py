"""
Event / news noise filter — narrative and risk framing, downgrade-only.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.services.signal_provenance import (
    SIGNAL_EVENT_NARRATIVE,
    build_provenance_envelope,
)

TIER_A_PRIMARY = "tier_a_primary"  # SEC, company PR
TIER_B_SECONDARY = "tier_b_secondary"  # major wire
TIER_C_SPECULATIVE = "tier_c_speculative"
TIER_D_RUMOR = "tier_d_rumor"

TAXONOMY_EARNINGS = "earnings"
TAXONOMY_MNA = "mna"
TAXONOMY_REGULATORY = "regulatory"
TAXONOMY_PRODUCT = "product"
TAXONOMY_MACRO = "macro_headline"
TAXONOMY_SOCIAL = "social_noise"

IMPACT_FRAMING_RISK = "risk_downgrade"
IMPACT_FRAMING_CONTEXT = "context_only"
IMPACT_FRAMING_NOISE = "filtered_noise"


def _event_fingerprint(title: str, source: str) -> str:
    raw = f"{title.strip().lower()}|{source.strip().lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def cluster_events(events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Dedup by fingerprint; keep highest credibility per cluster."""
    by_fp: Dict[str, Dict[str, Any]] = {}
    for ev in events:
        fp = ev.get("fingerprint") or _event_fingerprint(
            ev.get("title", ""), ev.get("source", "")
        )
        ev = {**ev, "fingerprint": fp}
        prev = by_fp.get(fp)
        if not prev or _tier_rank(ev.get("credibility_tier")) > _tier_rank(
            prev.get("credibility_tier")
        ):
            by_fp[fp] = ev
    return list(by_fp.values())


def _tier_rank(tier: Optional[str]) -> int:
    order = {
        TIER_A_PRIMARY: 4,
        TIER_B_SECONDARY: 3,
        TIER_C_SPECULATIVE: 2,
        TIER_D_RUMOR: 1,
    }
    return order.get(tier or "", 0)


def frame_impact(
    *,
    taxonomy: str,
    credibility_tier: str,
    sentiment: str = "neutral",
) -> Tuple[str, str]:
    """Returns (impact_framing, copy). Never returns deploy upgrade."""
    if credibility_tier == TIER_D_RUMOR or taxonomy == TAXONOMY_SOCIAL:
        return (
            IMPACT_FRAMING_NOISE,
            "Filtered — rumor/social noise does not change board gate",
        )
    if taxonomy in (TAXONOMY_REGULATORY, TAXONOMY_EARNINGS) and credibility_tier in (
        TIER_A_PRIMARY,
        TIER_B_SECONDARY,
    ):
        if sentiment == "negative":
            return (
                IMPACT_FRAMING_RISK,
                "Credible negative catalyst — may downgrade sizing context only",
            )
        return (
            IMPACT_FRAMING_CONTEXT,
            "Credible event — narrative context; confirm on Playbook",
        )
    return (
        IMPACT_FRAMING_CONTEXT,
        "Secondary headline — monitor only",
    )


def _mock_events(ticker: str) -> List[Dict[str, Any]]:
    sym = ticker.upper()
    raw = [
        {
            "title": f"{sym} Q1 guidance cited in illustrative wire",
            "source": "Illustrative Wire",
            "taxonomy": TAXONOMY_EARNINGS,
            "credibility_tier": TIER_B_SECONDARY,
            "sentiment": "neutral",
            "published_at": "2026-03-01T14:00:00Z",
        },
        {
            "title": f"Social chatter spike on {sym} (illustrative)",
            "source": "Social aggregator",
            "taxonomy": TAXONOMY_SOCIAL,
            "credibility_tier": TIER_D_RUMOR,
            "sentiment": "neutral",
            "published_at": "2026-03-02T09:00:00Z",
        },
    ]
    out = []
    for ev in raw:
        framing, copy = frame_impact(
            taxonomy=ev["taxonomy"],
            credibility_tier=ev["credibility_tier"],
            sentiment=ev.get("sentiment", "neutral"),
        )
        out.append(
            {
                **ev,
                "fingerprint": _event_fingerprint(ev["title"], ev["source"]),
                "impact_framing": framing,
                "impact_copy": copy,
                "may_upgrade_trade": False,
            }
        )
    return cluster_events(out)


def build_event_risk_context(
    ticker: str,
    *,
    degraded: bool = False,
) -> Dict[str, Any]:
    sym = ticker.upper().strip()
    now = datetime.now(timezone.utc).isoformat()
    events = _mock_events(sym)
    body = {
        "ticker": sym,
        "events": events,
        "event_count": len(events),
        "downgrade_only": True,
        "monitor_trigger_type": "event_clear",
        "data_tier": "mock",
    }
    return build_provenance_envelope(
        signal_type=SIGNAL_EVENT_NARRATIVE,
        source="mock-event-stub",
        as_of=now,
        degraded=degraded or True,
        data_mode="research_only",
        extra=body,
    )
