"""478-alpha zoo manifest — pack labels + computable templates (research)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

_MANIFEST_PATH = Path("data/research/alpha_manifest.json")
_PACKS_PATH = Path("data/research/alpha_packs.json")

_TEMPLATES = (
    "mom",
    "rev",
    "vol_z",
    "rsi",
    "sma_spread",
    "range",
    "gap",
    "dollar_vol",
)


def _build_manifest_rows() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    specs = [
        ("qlib158", "qlib", 158, True),
        ("kakushadze101", "k101", 101, False),
        ("gtja191", "gtja", 191, False),
        ("academic", "acad", 20, False),
        ("pit_fundamental", "pit", 8, True),
    ]
    for pack_id, prefix, count, pit in specs:
        for i in range(1, count + 1):
            tmpl = _TEMPLATES[(i - 1) % len(_TEMPLATES)]
            window = 3 + ((i * 2) % 40)
            rows.append(
                {
                    "id": f"{prefix}_{i:03d}",
                    "pack": pack_id,
                    "label": f"{pack_id} #{i} ({tmpl})",
                    "template": tmpl,
                    "window": window,
                    "pit_safe_fundamental": pit and pack_id == "pit_fundamental",
                }
            )
    return rows


def ensure_manifest_file() -> Path:
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not _MANIFEST_PATH.exists():
        rows = _build_manifest_rows()
        payload = {
            "schema": "cc.alpha_manifest.v1",
            "total": len(rows),
            "alphas": rows,
        }
        with open(_MANIFEST_PATH, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    return _MANIFEST_PATH


def load_manifest(*, limit: int = 478) -> Dict[str, Any]:
    ensure_manifest_file()
    with open(_MANIFEST_PATH, encoding="utf-8") as f:
        data = json.load(f)
    alphas = list(data.get("alphas") or [])[: max(1, min(limit, 478))]
    packs = {}
    if _PACKS_PATH.exists():
        try:
            with open(_PACKS_PATH, encoding="utf-8") as pf:
                packs = json.load(pf)
        except Exception:
            pass
    return {
        "schema": data.get("schema") or "cc.alpha_manifest.v1",
        "total": data.get("total") or len(data.get("alphas") or []),
        "alphas": alphas,
        "packs_meta": packs.get("packs") or [],
    }


def manifest_summary() -> Dict[str, Any]:
    m = load_manifest(limit=478)
    return {
        "total_alphas": m["total"],
        "packs": m["packs_meta"],
        "manifest_path": str(_MANIFEST_PATH),
    }
