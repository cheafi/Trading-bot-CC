#!/usr/bin/env python3
"""Root launcher — delegates to scripts/cc_instant.py for repo hygiene."""

from __future__ import annotations

import importlib.util
import os
import runpy
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
_IMPL_PATH = _REPO_ROOT / "scripts" / "cc_instant.py"


def _load_impl():
    name = "_cc_instant_impl"
    cached = sys.modules.get(name)
    if cached is not None:
        return cached
    os.environ.setdefault("CC_INSTANT_VENV_REEXEC", "1")
    spec = importlib.util.spec_from_file_location(name, _IMPL_PATH)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load {_IMPL_PATH}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    runpy.run_path(str(_IMPL_PATH), run_name="__main__")
else:
    _impl = _load_impl()
    globals().update(
        {name: getattr(_impl, name) for name in dir(_impl) if not name.startswith("__")}
    )
