"""generate-alpha-review.py script smoke test."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_generate_alpha_review_dry_run_json():
    proc = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "generate-alpha-review.py"),
            "--dry-run",
            "--json",
            "--window",
            "20d",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "alpha_review" not in proc.stdout  # json uses report fields
    assert '"status"' in proc.stdout
    assert '"authority_effect": "none"' in proc.stdout
    assert '"may_authorize_deploy": false' in proc.stdout
