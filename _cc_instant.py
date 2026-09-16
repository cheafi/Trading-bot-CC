#!/usr/bin/env python3
"""Root launcher — delegates to scripts/cc_instant.py for repo hygiene."""

from __future__ import annotations

import runpy
from pathlib import Path

if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parent / "scripts" / "cc_instant.py"),
        run_name="__main__",
    )
