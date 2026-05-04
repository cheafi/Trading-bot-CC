"""Extraction script — run once then delete."""
import re

main = open("src/api/main.py").read()
lines = main.splitlines(keepends=True)

# ── 1. confidence.py ──────────────────────────────────────────────────────────
start = next(i for i, l in enumerate(lines) if "def _compute_4layer_confidence(" in l)
end = start + 1
while end < len(lines):
    l = lines[end]
    if (l.startswith("def ") or l.startswith("class ") or l.startswith("@app.")) and not l.startswith("    "):
        break
    end += 1

body = "".join(lines[start:end])
body = body.replace("def _compute_4layer_confidence(", "def compute_4layer_confidence(")
hdr = '"""CC — 4-Layer Confidence Engine (extracted from src/api/main.py)."""\n'
hdr += "from src.core.risk_limits import RISK, SIGNAL_THRESHOLDS  # noqa\n\n"
open("src/services/confidence.py", "w").write(hdr + body)
print(f"confidence.py: lines {start+1}–{end}, {len(hdr+body)} chars")

# ── 2. scanner.py helpers + scan logic ──────────────────────────────────────
# Find helper function block start (_honest_confidence_label) and end (_scan_live_signals returns)
h_start = next(i for i, l in enumerate(lines) if "def _honest_confidence_label(" in l)
# Find end of _scan_live_signals
scan_start = next(i for i, l in enumerate(lines) if "async def _scan_live_signals(" in l)
scan_end = scan_start + 1
depth = 0
for i in range(scan_start, len(lines)):
    l = lines[i]
    if i == scan_start:
        depth = 1
        continue
    if (l.startswith("def ") or l.startswith("async def ") or l.startswith("@app.") or l.startswith("class ")) and not l.startswith("    "):
        scan_end = i
        break

helpers = "".join(lines[h_start:scan_start])
scan_body = "".join(lines[scan_start:scan_end])
print(f"helpers: lines {h_start+1}–{scan_start}")
print(f"scan_body: lines {scan_start+1}–{scan_end}")
print("helpers chars:", len(helpers), "scan chars:", len(scan_body))

# Write scanner.py
scanner_code = f"""\"\"\"CC — Scanner Service (extracted from src/api/main.py P4).

ScannerService holds the watchlist-scan caches and the full async scan logic.
Wire once in app startup via _init_shared_services(), access everywhere via
request.app.state.scanner_service.scan(limit).
\"\"\"
import asyncio
import logging
import time as _time

import numpy as np

from src.core.risk_limits import RISK, SIGNAL_THRESHOLDS
from src.services.confidence import compute_4layer_confidence
from src.services.indicators import (
    compute_indicators as _compute_indicators,
    compute_rs_vs_benchmark as _compute_rs_vs_benchmark,
)

logger = logging.getLogger(__name__)

# ── Phase 9 engine imports (graceful fallback) ───────────────────────────────
try:
    from src.engines.breakout_monitor import BreakoutMonitor
    from src.engines.decision_persistence import get_journal
    from src.engines.earnings_calendar import get_earnings_info
    from src.engines.entry_quality import EntryQualityEngine
    from src.engines.fundamental_data import get_fundamentals
    from src.engines.portfolio_gate import PortfolioGate
    from src.engines.structure_detector import StructureDetector
    _P9_ENGINES = True
except ImportError:
    _P9_ENGINES = False

try:
    from src.engines.conformal_predictor import reliability_bucket, reliability_note
except ImportError:
    def reliability_bucket(n): return "low"  # noqa
    def reliability_note(n): return "Insufficient data"  # noqa

# ── Watchlist + sector map ───────────────────────────────────────────────────
"""

# Extract the watchlist and sector clusters from main.py
wl_start = next(i for i, l in enumerate(lines) if l.strip().startswith("_SCAN_WATCHLIST = ["))
# Find the dedup line
wl_end = next(i for i, l in enumerate(lines) if "_SCAN_WATCHLIST = list(dict.fromkeys" in l)
wl_end += 1  # include the dedup line

sector_start = next(i for i, l in enumerate(lines) if "_TICKER_SECTOR: dict[str, str] = {}" in l)
sector_end = next(i for i, l in enumerate(lines) if "_MAX_SIGNALS_PER_SECTOR" in l)
sector_end += 1

watchlist_block = "".join(lines[wl_start:wl_end])
sector_block = "".join(lines[sector_start:sector_end])
print(f"watchlist: {wl_start+1}–{wl_end}")
print(f"sector: {sector_start+1}–{sector_end}")

# Rename
watchlist_block = watchlist_block.replace("_SCAN_WATCHLIST", "SCAN_WATCHLIST")
sector_block = (sector_block
    .replace("_TICKER_SECTOR", "TICKER_SECTOR")
    .replace("_SECTOR_CLUSTERS", "SECTOR_CLUSTERS")
    .replace("_MAX_SIGNALS_PER_SECTOR", "MAX_SIGNALS_PER_SECTOR"))

# Remove RISK import (we import it at top)
scanner_code += watchlist_block + "\n" + sector_block + "\n"

# Add the ScannerService class wrapping the scan logic
scanner_code += """
_SPY_CACHE: dict = {"close": None, "ts": 0.0}


class ScannerService:
    \"\"\"Holds scan caches and exposes .scan(limit) coroutine.\"\"\"

    CACHE_TTL = 300      # 5 minutes
    NEG_TTL   = 3600     # 1 hour
    BATCH     = 25

    def __init__(self, mds):
        self._mds = mds
        self._cache: dict = {"recs": [], "scores": {}, "ts": 0.0}
        self._neg: dict[str, float] = {}

    async def _spy_close(self) -> "np.ndarray | None":
        now = _time.time()
        if _SPY_CACHE["close"] is not None and now - _SPY_CACHE["ts"] < 3600:
            return _SPY_CACHE["close"]
        try:
            hist = await self._mds.get_history("SPY", period="1y", interval="1d")
            if hist is not None and not hist.empty:
                c = "Close" if "Close" in hist.columns else "close"
                spy = hist[c].values.astype(float)
                _SPY_CACHE["close"] = spy
                _SPY_CACHE["ts"] = now
                return spy
        except Exception:
            pass
        return None

"""

# Now embed helpers (converted to methods — actually keep as module functions)
helpers_renamed = (helpers
    .replace("def _honest_confidence_label(", "def honest_confidence_label(")
    .replace("def _enrich_calibration(", "def enrich_calibration(")
    .replace("def _compute_action_state(", "def compute_action_state(")
    .replace("def _build_reasons_for(", "def build_reasons_for(")
    .replace("def _build_reasons_against(", "def build_reasons_against(")
    .replace("def _build_pre_mortem(", "def build_pre_mortem(")
    .replace("def _build_why_wait(", "def build_why_wait(")
    .replace("async def _days_to_earnings(", "async def days_to_earnings(")
)
scanner_code += helpers_renamed

# Now write the scan method as a method of ScannerService
scan_method = scan_body
# Rename references
scan_method = scan_method.replace("async def _scan_live_signals(limit: int = 10)", "    async def scan(self, limit: int = 10)")
scan_method = scan_method.replace("    mds = app.state.market_data\n", "        mds = self._mds\n")
scan_method = scan_method.replace("app.state.market_data", "self._mds")
scan_method = scan_method.replace("_scan_cache", "self._cache")
scan_method = scan_method.replace("_neg_cache", "self._neg")
scan_method = scan_method.replace("_SCAN_CACHE_TTL", "self.CACHE_TTL")
scan_method = scan_method.replace("_NEG_CACHE_TTL", "self.NEG_TTL")
scan_method = scan_method.replace("_SCAN_BATCH_SIZE", "self.BATCH")
scan_method = scan_method.replace("_SCAN_WATCHLIST", "SCAN_WATCHLIST")
scan_method = scan_method.replace("_TICKER_SECTOR", "TICKER_SECTOR")
scan_method = scan_method.replace("_MAX_SIGNALS_PER_SECTOR", "MAX_SIGNALS_PER_SECTOR")
scan_method = scan_method.replace("_get_spy_close()", "self._spy_close()")
scan_method = scan_method.replace("_compute_indicators", "_compute_indicators")  # already renamed at top
scan_method = scan_method.replace("_compute_rs_vs_benchmark", "_compute_rs_vs_benchmark")
scan_method = scan_method.replace("_compute_4layer_confidence", "compute_4layer_confidence")
scan_method = scan_method.replace("_honest_confidence_label(", "honest_confidence_label(")
scan_method = scan_method.replace("_enrich_calibration(", "enrich_calibration(")
scan_method = scan_method.replace("_compute_action_state(", "compute_action_state(")
scan_method = scan_method.replace("_build_reasons_for(", "build_reasons_for(")
scan_method = scan_method.replace("_build_reasons_against(", "build_reasons_against(")
scan_method = scan_method.replace("_build_pre_mortem(", "build_pre_mortem(")
scan_method = scan_method.replace("_build_why_wait(", "build_why_wait(")
scan_method = scan_method.replace("reliability_bucket(", "reliability_bucket(")
scan_method = scan_method.replace("reliability_note(", "reliability_note(")
# Fix indentation: the scan method is now a class method (needs 4 more spaces indent)
# The function body is indented 4 spaces; method body needs 8 spaces
scan_lines = scan_method.splitlines(keepends=True)
indented = []
for i, l in enumerate(scan_lines):
    if i == 0:
        indented.append(l)  # "    async def scan(self, ..." already has 4 spaces
    else:
        if l.strip() == "":
            indented.append(l)
        else:
            indented.append("    " + l)  # add 4 more spaces to body
scan_method_indented = "".join(indented)

scanner_code += "\n\n" + scan_method_indented + "\n"

open("src/services/scanner.py", "w").write(scanner_code)
print(f"scanner.py written, {len(scanner_code)} chars, {scanner_code.count(chr(10))} lines")
