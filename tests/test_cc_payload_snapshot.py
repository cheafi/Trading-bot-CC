"""Today payload snapshot script validation."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_snapshot_module():
    spec = importlib.util.spec_from_file_location(
        "snapshot_today_payload",
        ROOT / "scripts" / "snapshot-today-payload.py",
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def test_snapshot_script_writes_valid_payload():
    mod = _load_snapshot_module()
    payload = mod._minimal_today_payload()
    errors = mod.validate_payload(payload)
    assert not errors, errors
    assert payload["decision_quality"]["may_authorize_deploy"] is False


def test_snapshot_cli():
    proc = subprocess.run(
        [sys.executable, "scripts/snapshot-today-payload.py", "--validate-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout
    assert "PASS" in proc.stdout
