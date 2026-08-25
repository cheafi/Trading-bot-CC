"""Alpha Factory — spawn AlphaObject + artifact on scan/playbook candidates (Sprint 117)."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.core.alpha_object import AlphaEvidence, AlphaLifecycleStage, AlphaObject
from src.services.investment_object_factory import make_attribution_root_ref, make_decision_id

logger = logging.getLogger(__name__)

_DATA_DIR = Path(__file__).resolve().parents[2] / "data"
_ARTIFACT_ROOT = _DATA_DIR / "artifacts" / "alpha_factory"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _artifact_path(ticker: str, *, as_of: Optional[str] = None) -> Path:
    day = (as_of or _utcnow_iso())[:10]
    return _ARTIFACT_ROOT / day / f"{ticker.upper()}.json"


def write_alpha_artifact(alpha: AlphaObject) -> str:
    """Persist AlphaObject sidecar; returns artifact_id."""
    artifact_id = f"alpha-{alpha.ticker}-{uuid.uuid4().hex[:8]}"
    path = _artifact_path(alpha.ticker, as_of=alpha.as_of.isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = alpha.model_dump(mode="json")
    payload["artifact_id"] = artifact_id
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return artifact_id


def spawn_alpha_object_from_row(
    row: Dict[str, Any],
    *,
    run_id: Optional[str] = None,
) -> AlphaObject:
    """Birth AlphaObject from ranked candidate — research_only forever."""
    ticker = str(row.get("ticker") or "").upper()
    decision_id = str(row.get("decision_id") or make_decision_id(ticker, row=row))
    prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    evidence = [
        AlphaEvidence(
            source=str(prov.get("source") or row.get("source") or "scanner"),
            summary=str(row.get("why_now") or row.get("thesis") or "Scanner candidate"),
            data_ref=row.get("artifact_id"),
            weight=min(float(row.get("thesis_conf") or 0.5), 1.0),
            supports_hypothesis=True,
        )
    ]
    alpha = AlphaObject(
        ticker=ticker,
        investment_id=row.get("investment_id"),
        hypothesis=str(row.get("why_now") or row.get("edge_hypothesis") or f"{ticker} setup"),
        setup_type=str(row.get("setup_type") or row.get("ladder_bucket") or ""),
        expected_alpha_bps=row.get("expected_alpha_bps") or row.get("net_edge_bps"),
        evidence=evidence,
        confidence=min(float(row.get("thesis_conf") or row.get("confidence") or 0.5), 1.0),
        stage=AlphaLifecycleStage.HYPOTHESIS,
        attribution_root_ref=row.get("attribution_root_ref")
        or make_attribution_root_ref(decision_id),
        feature_snapshot={
            "run_id": run_id,
            "rank": row.get("rank"),
            "score": row.get("score"),
            "ev_score": row.get("ev_score"),
        },
    )
    artifact_id = write_alpha_artifact(alpha)
    row["artifact_id"] = artifact_id
    row["alpha_id"] = alpha.alpha_id
    return alpha


def attach_alpha_objects(
    rows: List[Dict[str, Any]],
    *,
    run_id: Optional[str] = None,
    top_n: int = 12,
) -> List[Dict[str, Any]]:
    """Ensure top-N rows carry alpha_id + artifact_id."""
    out: List[Dict[str, Any]] = []
    for i, row in enumerate(rows):
        r = dict(row)
        if i < top_n and r.get("ticker") and not r.get("alpha_id"):
            alpha = spawn_alpha_object_from_row(r, run_id=run_id)
            r["alpha_id"] = alpha.alpha_id
            r["artifact_id"] = r.get("artifact_id")
            r["alpha_object"] = alpha.model_dump(mode="json")
        out.append(r)
    return out
