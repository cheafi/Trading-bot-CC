"""Dashboard export — allow-listed view model only (no secrets)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping, Optional

# Allow-listed top-level export keys only.
_EXPORT_ROOT_ALLOWLIST = frozenset(
    {
        "as_of",
        "version",
        "system_state",
        "page_capability",
        "operator_sentence",
        "tradeability",
        "deploy_open",
        "authority",
        "records",
    }
)

_SYSTEM_STATE_ALLOWLIST = frozenset(
    {
        "regime",
        "tradeability",
        "data_freshness",
        "engine_state",
        "broker_state",
        "board_mode",
        "authority",
        "fallback_mode",
        "deploy_open",
        "blocker_compact",
        "repair_priority",
        "operator_sentence",
    }
)

_RECORD_ALLOWLIST = frozenset(
    {
        "ticker",
        "action",
        "effective_action",
        "tradeability",
        "thesis_conf",
        "timing_conf",
        "exec_conf",
        "data_conf",
        "final_conf",
        "risk_reward",
        "decision_id",
        "attribution_root_ref",
        "authority",
        "deploy_open",
    }
)

_SECRET_KEY_FRAGMENTS = (
    "api_key",
    "apikey",
    "token",
    "password",
    "secret",
    "credential",
    "private_key",
    "authorization",
    "bearer",
)


def _is_secret_key(key: str) -> bool:
    lowered = str(key or "").lower()
    return any(fragment in lowered for fragment in _SECRET_KEY_FRAGMENTS)


def _filter_mapping(
    data: Mapping[str, Any],
    allowlist: Iterable[str],
) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for key in allowlist:
        if key not in data or _is_secret_key(key):
            continue
        value = data[key]
        if isinstance(value, dict):
            out[key] = {
                k: v
                for k, v in value.items()
                if not _is_secret_key(k) and k in allowlist
            }
        else:
            out[key] = value
    return out


def build_dashboard_export_view(
    source: Mapping[str, Any],
    *,
    version: str = "cc-x",
) -> Dict[str, Any]:
    """Return an allow-listed dashboard export payload — strips secrets by construction."""
    root = _filter_mapping(source, _EXPORT_ROOT_ALLOWLIST)
    if "system_state" in source and isinstance(source["system_state"], dict):
        root["system_state"] = _filter_mapping(
            source["system_state"],
            _SYSTEM_STATE_ALLOWLIST,
        )
    records = source.get("records")
    if isinstance(records, list):
        root["records"] = [
            _filter_mapping(row, _RECORD_ALLOWLIST)
            for row in records
            if isinstance(row, dict)
        ]
    root.setdefault(
        "as_of",
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )
    root["version"] = version
    root.setdefault("authority", "research_only")
    return root


def export_contains_secret(payload: Mapping[str, Any]) -> Optional[str]:
    """Return the first secret-like key found anywhere in payload (test helper)."""

    def _walk(obj: Any, prefix: str = "") -> Optional[str]:
        if isinstance(obj, Mapping):
            for key, value in obj.items():
                key_s = f"{prefix}.{key}" if prefix else str(key)
                if _is_secret_key(str(key)):
                    return key_s
                found = _walk(value, key_s)
                if found:
                    return found
        elif isinstance(obj, list):
            for idx, item in enumerate(obj):
                found = _walk(item, f"{prefix}[{idx}]")
                if found:
                    return found
        return None

    return _walk(payload)
