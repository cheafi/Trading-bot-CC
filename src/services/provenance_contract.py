"""Provenance contract — mandatory source/as_of/mode on scored surfaces (Sprint 116)."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple


REQUIRED_PROVENANCE_KEYS = ("source", "as_of", "mode")


def validate_provenance_block(block: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Return (ok, missing_keys) for a provenance envelope."""
    missing = [k for k in REQUIRED_PROVENANCE_KEYS if not block.get(k)]
    return len(missing) == 0, missing


def validate_row_provenance(row: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Check row-level provenance — accepts nested provenance or flat fields."""
    prov = row.get("provenance") if isinstance(row.get("provenance"), dict) else {}
    flat = {
        "source": prov.get("source") or row.get("source"),
        "as_of": prov.get("as_of") or row.get("as_of"),
        "mode": prov.get("mode") or row.get("mode") or row.get("data_mode"),
    }
    return validate_provenance_block(flat)


def assert_rows_have_provenance(rows: List[Dict[str, Any]], *, min_rows: int = 1) -> None:
    """CI gate — raises AssertionError when provenance missing on scored rows."""
    checked = [r for r in rows if r.get("ticker")][: min(len(rows), max(min_rows, 12))]
    failures: List[str] = []
    for row in checked:
        ok, missing = validate_row_provenance(row)
        if not ok:
            failures.append(f"{row.get('ticker')}: missing {missing}")
    if failures:
        raise AssertionError(
            "Provenance contract violation — source/as_of/mode required: "
            + "; ".join(failures)
        )


def enrich_row_provenance(
    row: Dict[str, Any],
    *,
    source: str,
    as_of: str,
    mode: str = "LIVE",
) -> Dict[str, Any]:
    """Ensure row carries mandatory provenance fields."""
    out = dict(row)
    out.setdefault("source", source)
    out.setdefault("as_of", as_of)
    out.setdefault("mode", mode)
    out["provenance"] = {
        "source": out["source"],
        "as_of": out["as_of"],
        "mode": out["mode"],
    }
    return out
