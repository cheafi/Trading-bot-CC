"""Runtime state paths — persisted under STATE_DATA_DIR (Docker volume), not /tmp."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

_DEFAULT_STATE_DIR = Path("data/state")
_DATA_DIR = Path("data")


def runtime_state_dir() -> Path:
    """Directory for engine heartbeat, position snapshots, and risk state."""
    raw = os.environ.get("STATE_DATA_DIR", "").strip()
    base = Path(raw) if raw else _DEFAULT_STATE_DIR
    base.mkdir(parents=True, exist_ok=True)
    return base


def engine_heartbeat_path() -> Path:
    return runtime_state_dir() / "engine_heartbeat"


def yfinance_cache_dir() -> Path:
    """yfinance cache under data/ — never /tmp for authoritative paths."""
    raw = os.environ.get("YFINANCE_CACHE_DIR", "").strip()
    base = Path(raw) if raw else (_DATA_DIR / "cache" / "yfinance")
    base.mkdir(parents=True, exist_ok=True)
    return base


def simulation_ledger_path() -> Path:
    path = _DATA_DIR / "simulation_ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def deployment_manifest_path() -> Path:
    path = runtime_state_dir() / "deployment_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def atomic_write_text(path: Path, content: str) -> None:
    """Atomic replace write for small state files."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def atomic_write_jsonl_append(path: Path, row: Dict[str, Any]) -> None:
    """Append one JSON line (append-only ledger)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, separators=(",", ":")) + "\n")
