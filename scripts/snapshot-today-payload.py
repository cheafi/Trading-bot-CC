#!/usr/bin/env python3
"""Snapshot /api/v7/today payload shape for release validation."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "data" / "release_snapshots"

REQUIRED_TOP_KEYS = {
    "system_truth",
    "decision_quality",
    "filter_funnel",
    "execution_readiness",
    "market_regime",
    "trust",
}

REQUIRED_TRUTH_KEYS = {
    "deploy_authority",
    "reason_codes",
}

REQUIRED_DQ_KEYS = {
    "state_label",
    "metrics",
    "authority_effect",
    "collapsed",
    "evidence_only",
    "may_authorize_deploy",
}


def _minimal_today_payload() -> Dict[str, Any]:
    """Deterministic minimal payload when API is unavailable."""
    from src.services.system_truth import resolve_system_truth

    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": False},
            "trust": {"stale": True, "source": "snapshot_dry_run"},
            "decision_authority": {
                "authority_level": "research",
                "gates_active": True,
                "allows_trade_labels": False,
            },
            "execution_readiness": {"broker_connected": False},
            "qualification_levels": {"deploy_qualified": 0, "setup_qualified": 0},
            "top_5": [],
        },
        cc_header={"data_tier": "STALE"},
        ops_console={"engine_running": False},
    )
    from src.services.opportunity_quality_engine import build_decision_quality_dashboard

    dq = build_decision_quality_dashboard(truth=truth)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "dry_run_minimal",
        "system_truth": truth,
        "decision_quality": dq,
        "filter_funnel": {
            "universe_scanned": 0,
            "watch_qualified_setups": 0,
            "deploy_qualified_setups": 0,
        },
        "execution_readiness": {"readiness_label": "blocked", "trade_handoff_ready": False},
        "market_regime": {"tradeability": "WAIT"},
        "trust": {"stale": True, "mode": "degraded"},
    }


def flatten_schema(obj: Any, prefix: str = "") -> Dict[str, str]:
    out: Dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else str(k)
            out[key] = type(v).__name__
            if isinstance(v, dict):
                out.update(flatten_schema(v, key))
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                out[f"{key}[]"] = "list[object]"
                out.update(flatten_schema(v[0], f"{key}[]"))
    return out


def validate_payload(payload: Dict[str, Any]) -> List[str]:
    errors: List[str] = []
    missing = REQUIRED_TOP_KEYS - set(payload.keys())
    if missing:
        errors.append(f"missing top-level keys: {sorted(missing)}")

    truth = payload.get("system_truth") or {}
    tm = REQUIRED_TRUTH_KEYS - set(truth.keys())
    if tm:
        errors.append(f"system_truth missing: {sorted(tm)}")

    dq = payload.get("decision_quality") or {}
    dm = REQUIRED_DQ_KEYS - set(dq.keys())
    if dm:
        errors.append(f"decision_quality missing: {sorted(dm)}")

    if dq.get("may_authorize_deploy"):
        errors.append("decision_quality may_authorize_deploy must be false")

    if dq.get("authority_effect") not in (None, "none"):
        errors.append(f"decision_quality authority_effect must be none, got {dq.get('authority_effect')!r}")

    aq = dq.get("alpha_quality") or {}
    if aq and aq.get("allow_green_ui") and str(aq.get("overfit_risk", "")).lower() in ("medium", "high"):
        errors.append("alpha_quality allow_green_ui true with medium/high overfit")

    tg = dq.get("threshold_governance") or {}
    if tg.get("can_auto_loosen"):
        errors.append("threshold_governance can_auto_loosen must be false")

    intel = payload.get("opportunity_intelligence") or payload.get("discovery") or {}
    if isinstance(intel, dict) and intel.get("deploy_ready"):
        errors.append("research surface deploy_ready flag must not be set")

    return errors


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot today payload schema")
    parser.add_argument("--input", help="Existing JSON payload file")
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.input:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    else:
        payload = _minimal_today_payload()

    errors = validate_payload(payload)
    if args.validate_only:
        if errors:
            for e in errors:
                print(f"FAIL: {e}", file=sys.stderr)
            return 1
        print("PASS: payload schema valid")
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    payload_path = OUT_DIR / f"today_payload_{ts}.json"
    schema_path = OUT_DIR / f"schema_{ts}.json"

    payload_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    schema = {
        "generated_at": payload.get("generated_at"),
        "source": payload.get("source", "unknown"),
        "required_top_keys": sorted(REQUIRED_TOP_KEYS),
        "fields": flatten_schema(payload),
        "validation_errors": errors,
        "valid": not errors,
    }
    schema_path.write_text(json.dumps(schema, indent=2), encoding="utf-8")

    print(f"wrote {payload_path.relative_to(ROOT)}")
    print(f"wrote {schema_path.relative_to(ROOT)}")
    if errors:
        for e in errors:
            print(f"WARN: {e}", file=sys.stderr)
        return 1
    print("PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
