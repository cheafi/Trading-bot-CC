"""Compute, persist and load walk-forward evidence artifacts.

Artifacts live under ``data/evidence/walk_forward/<strategy_id>.json``. Only
strategy ids registered in ``walk_forward.RULES`` are ever turned into paths.
A missing, unreadable or stale artifact loads as ``None`` — callers fall back
to ledger evidence, never to an assumed grade.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from src.engines.walk_forward import RULES, CostModel, walk_forward_report

logger = logging.getLogger(__name__)

ARTIFACT_DIR = (
    Path(__file__).resolve().parents[2] / "data" / "evidence" / "walk_forward"
)
MAX_ARTIFACT_AGE_S = 8 * 86400
HISTORY_PERIOD = "5y"
BENCHMARK = "SPY"
SCHEMA_VERSION = 1


def _artifact_path(strategy_id: str, directory: Path) -> Optional[Path]:
    if strategy_id not in RULES:
        return None
    return directory / f"{strategy_id}.json"


async def compute(
    strategy_id: str,
    tickers: Iterable[str],
    *,
    mds: Any = None,
    costs: CostModel = CostModel(),
) -> Dict[str, Any]:
    """Fetch history and run the walk-forward report. Never places orders."""
    rule = RULES.get(strategy_id)
    if rule is None:
        raise KeyError(f"unknown strategy_id: {strategy_id}")
    if mds is None:
        from src.services.market_data import get_market_data_service

        mds = get_market_data_service()

    symbols = sorted({str(t).strip().upper() for t in tickers if str(t).strip()})
    symbols = [s for s in symbols if s != BENCHMARK]
    frames = await asyncio.gather(
        *[mds.get_history(s, period=HISTORY_PERIOD, interval="1d") for s in symbols],
        return_exceptions=True,
    )
    data = {}
    missing = []
    for sym, df in zip(symbols, frames):
        if isinstance(df, Exception) or df is None or len(df) == 0:
            missing.append(sym)
        else:
            data[sym] = df
    bench = None
    if rule.needs_benchmark:
        spy = await mds.get_history(BENCHMARK, period=HISTORY_PERIOD, interval="1d")
        if spy is not None and len(spy) > 0:
            bench = spy["Close"] if "Close" in spy else spy["close"]

    report = walk_forward_report(data, rule, benchmark=bench, costs=costs)
    report["missing_tickers"] = missing
    report["computed_at"] = time.time()
    report["schema_version"] = SCHEMA_VERSION
    return report


def save(report: Dict[str, Any], directory: Path = ARTIFACT_DIR) -> Path:
    """Atomically write an artifact (temp file + rename)."""
    path = _artifact_path(str(report.get("strategy_id") or ""), directory)
    if path is None:
        raise KeyError("report has an unknown strategy_id")
    directory.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=".wf-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as fh:
            json.dump(report, fh, default=str, allow_nan=False)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise
    return path


def load(
    strategy_id: Optional[str],
    *,
    directory: Path = ARTIFACT_DIR,
    max_age_s: float = MAX_ARTIFACT_AGE_S,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Return a fresh, well-formed artifact or ``None``."""
    path = _artifact_path(str(strategy_id or ""), directory)
    if path is None or not path.is_file():
        return None
    try:
        report = json.loads(path.read_text())
    except (OSError, ValueError):
        logger.warning("walk-forward artifact unreadable: %s", path.name)
        return None
    if not isinstance(report, dict) or report.get("strategy_id") != strategy_id:
        return None
    if report.get("schema_version") != SCHEMA_VERSION:
        return None
    computed_at = report.get("computed_at")
    if not isinstance(computed_at, (int, float)):
        return None
    age = (time.time() if now is None else now) - computed_at
    if age < 0 or age > max_age_s:
        return None
    evidence = report.get("evidence")
    if not isinstance(evidence, dict) or not evidence.get("grade"):
        return None
    report["age_s"] = round(age, 1)
    return report
