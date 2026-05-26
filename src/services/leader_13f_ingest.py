"""
13F / filing sync for verified filers — MVP ingestion layer.

Fetches recent 13F-HR filing metadata via EdgarClient and records events.
Full position parsing from 13F XML is a follow-up; this pass never
promotes inferred data to verified without an explicit flag.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.services import leader_persistence as store
from src.services.leader_tracking_service import ensure_seeded, _rebuild_consensus

logger = logging.getLogger(__name__)

# Verified filers → representative CIK for filing metadata sync
FILER_REGISTRY: Dict[str, Dict[str, Any]] = {
    "berkshire-13f": {
        "cik": "0001067983",
        "watch_tickers": ["AAPL", "BAC", "OXY", "KO", "CVX"],
    },
    "ark-invest": {
        "cik": "0001649339",
        "watch_tickers": ["TSLA", "COIN", "ROKU", "SQ", "SHOP"],
    },
}


async def sync_filer_filings(leader_id: str) -> Dict[str, Any]:
    """Pull recent 13F-HR filings and append timeline events (metadata only)."""
    ensure_seeded()
    meta = FILER_REGISTRY.get(leader_id)
    if not meta:
        return {"ok": False, "error": f"No CIK registry for {leader_id}"}

    from src.ingestors.edgar import EdgarClient

    client = EdgarClient()
    # Use BRK.B or ARKK as ticker proxy for CIK lookup fallback
    proxy_ticker = "BRK.B" if "berkshire" in leader_id else "ARKK"
    filings = await client.get_recent_filings(
        proxy_ticker,
        form_types=["13F-HR", "13F-HR/A"],
        limit=5,
    )

    added = 0
    for f in filings:
        summary = f"SEC {f.form_type} filed {f.filed_date} — review holdings in filing"
        store.insert_event({
            "leader_id": leader_id,
            "ticker": None,
            "event_type": "filing",
            "event_date": f.filed_date[:10] if f.filed_date else datetime.now(timezone.utc).date().isoformat(),
            "disclosure_date": f.filed_date[:10] if f.filed_date else None,
            "summary": summary,
            "source_name": "sec_edgar",
            "source_quality": "verified",
            "context_tag": f.accession_number,
        })
        added += 1

    store.insert_alert({
        "alert_type": "filing_sync",
        "related_entity_type": "leader",
        "related_entity_id": leader_id,
        "severity": "info",
        "message": f"Synced {added} 13F filing metadata rows for {leader_id}",
    })
    _rebuild_consensus()
    return {
        "ok": True,
        "leader_id": leader_id,
        "filings_synced": added,
        "note": "Metadata-only sync. Position-level 13F XML parsing not yet applied.",
    }


async def sync_all_verified_filers() -> Dict[str, Any]:
    results = []
    for leader_id in FILER_REGISTRY:
        try:
            results.append(await sync_filer_filings(leader_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("13F sync failed for %s: %s", leader_id, exc)
            results.append({"ok": False, "leader_id": leader_id, "error": str(exc)})
    return {"results": results, "as_of": datetime.now(timezone.utc).isoformat()}
