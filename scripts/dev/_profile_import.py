#!/usr/bin/env python3
"""Profile import times to find the startup bottleneck."""

import time, sys, traceback

t0 = time.time()


def ts():
    return f"{time.time()-t0:.1f}s"


steps = [
    ("fastapi", "import fastapi"),
    ("uvicorn", "import uvicorn"),
    ("pandas", "import pandas"),
    ("numpy", "import numpy"),
    ("yfinance", "import yfinance"),
    ("scipy", "import scipy"),
    ("sklearn", "import sklearn"),
    ("ta", "import ta"),
    ("src.core.config", "import src.core.config"),
    ("src.core.risk_limits", "import src.core.risk_limits"),
    ("src.engines.regime_router", "from src.engines import regime_router"),
    ("src.engines.calibration_engine", "from src.engines import calibration_engine"),
    ("src.engines.auto_trading_engine", "from src.engines import auto_trading_engine"),
    ("src.engines.expert_council", "from src.engines import expert_council"),
    ("src.engines.strategy_optimizer", "from src.engines import strategy_optimizer"),
    ("src.services.regime_service", "from src.services import regime_service"),
    ("src.services.fund_lab_service", "from src.services import fund_lab_service"),
    ("src.services.fund_persistence", "from src.services import fund_persistence"),
    ("src.api.main", "import src.api.main"),
]

for name, stmt in steps:
    t1 = time.time()
    try:
        exec(stmt)
        dt = time.time() - t1
        flag = " ⚠️ SLOW" if dt > 2.0 else ""
        print(f"[{ts()}] ✅ {name} ({dt:.1f}s){flag}", flush=True)
    except Exception as e:
        dt = time.time() - t1
        print(f"[{ts()}] ❌ {name} ({dt:.1f}s): {e}", flush=True)

print(f"\n[{ts()}] Total import time: {time.time()-t0:.1f}s", flush=True)
