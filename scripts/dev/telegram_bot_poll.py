#!/usr/bin/env python3
"""Dev alias for scripts/run_telegram_bot.py — see docs/TELEGRAM_SETUP.md."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

_SCRIPT = ROOT / "scripts" / "run_telegram_bot.py"
_spec = importlib.util.spec_from_file_location("run_telegram_bot", _SCRIPT)
assert _spec and _spec.loader
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

if __name__ == "__main__":
    _mod.main()
