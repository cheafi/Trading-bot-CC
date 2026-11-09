"""Root pytest configuration.

Two responsibilities:

1. **Duplicate-file exclusion.** iCloud Drive resolves sync conflicts by
   writing a sibling copy with a numeric suffix (``foo 2.py``, ``bar 3.py``).
   ~170 such files exist in this working tree. They are untracked by Git, so
   they do not exist in CI or in a clean clone — but pytest collects them
   locally, producing failures that are pure artefacts of the local
   filesystem. We exclude them from collection; we do **not** delete them.

2. **State isolation.** Several suites read and write shared on-disk state
   under ``data/`` (alert ledgers, SQLite trackers, caches). Tests that mutate
   that state leak into later tests and make results order-dependent. The
   ``isolated_state_dir`` fixture gives a test its own temporary directory.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

# Matches the iCloud conflict-copy convention: "<stem> <n>.<ext>".
_ICLOUD_DUPLICATE_RE = re.compile(r".+ \d+\.[A-Za-z0-9]+$")

ROOT = Path(__file__).parent


def _is_icloud_duplicate(path: Path) -> bool:
    return bool(_ICLOUD_DUPLICATE_RE.match(path.name))


def pytest_ignore_collect(collection_path: Path, config) -> bool | None:
    """Skip iCloud conflict copies so local runs match CI."""
    if _is_icloud_duplicate(Path(collection_path)):
        return True
    return None


def pytest_collection_modifyitems(config, items) -> None:
    """Mark network-dependent tests so they can be deselected.

    These tests reach out to live market-data providers. They are not
    deterministic, they fail without connectivity, and they must never gate a
    correctness decision. We mark rather than delete: the coverage is real,
    it just belongs in a separate, explicitly-requested run.
    """
    for item in items:
        name = item.nodeid.lower()
        if any(
            token in name
            for token in ("yfinance", "live_", "_live", "network", "realtime")
        ):
            item.add_marker(pytest.mark.network)


@pytest.fixture
def isolated_state_dir(tmp_path, monkeypatch):
    """Redirect on-disk application state to a per-test temp directory.

    Prevents suites from contaminating each other through shared ledgers and
    caches under ``data/``, which is the root cause of several order-dependent
    failures.
    """
    for var in ("CC_DATA_DIR", "CC_STATE_DIR", "DATA_DIR"):
        monkeypatch.setenv(var, str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    return tmp_path


@pytest.fixture
def frozen_env(monkeypatch):
    """Neutralise ambient configuration that varies between machines."""
    for var in list(os.environ):
        if var.startswith(("RISK_", "UNIVERSE_", "VIX_", "BACKTEST_")):
            monkeypatch.delenv(var, raising=False)
    return monkeypatch
