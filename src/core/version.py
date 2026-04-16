"""
CC — Single Source of Truth for Version & Product Identity.

Every surface (API, Discord, dashboard, docs, health endpoints)
MUST import from here. No inline version strings anywhere else.
"""

# ── Product Identity ──────────────────────────────────────────
PRODUCT_NAME = "CC"
PRODUCT_FULL_NAME = "CC — Regime-Aware Market Intelligence Platform"

# ── Canonical Version ─────────────────────────────────────────
# Bump here and ONLY here.  Follows semver: major.minor.patch
APP_VERSION = "6.1.0"

# ── Feature Counts (kept in sync with reality) ───────────────
STRATEGY_COUNT = 4  # swing, breakout, momentum, mean_reversion
DISCORD_COMMAND_COUNT = 64  # as per bot guide
DOCKER_SERVICE_COUNT = (
    9  # postgres redis ingestor signal auto_trader scheduler discord api jupyter
)

# ── Supported Universe ────────────────────────────────────────
UNIVERSE_SUMMARY = {
    "us_equities": 2751,
    "hk": 78,
    "japan": 60,
    "korea_tw_au_in": 51,
    "crypto": 63,
    "macro_indices": 20,
    "total_approx": 3023,
}

# ── Mode Labels ───────────────────────────────────────────────
MODES = ("LIVE", "PAPER", "BACKTEST", "SYNTHETIC")

# ── Decision Surfaces ─────────────────────────────────────────
DECISION_SURFACES = (
    "Today / Regime",
    "Signals / Scanner",
    "Symbol Dossier",
    "Portfolio Brief",
    "Options Research",
    "Track Record",
)
