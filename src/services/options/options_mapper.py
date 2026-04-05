"""
Options Chain Mapper
=====================

Maps raw OptionsDataProvider chains into ranked, scored contract
tables for the Options Screen surface.

Integrates:
  - OptionsDataProvider (real chain or synthetic fallback)
  - ExpressionEngine (instrument selection rationale)
  - MarketDataService (spot price, historical vol)

Produces:
  - Ranked contract list with liquidity score
  - IV term structure
  - Earnings / ex-div / IV-crush warnings
  - expression_rationale + rejection_reasons
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OptionsScreenResult:
    """Full options screen output."""

    ticker: str
    spot_price: float
    expression_decision: str
    expression_rationale: Dict[str, Any]
    rejection_reasons: List[str]
    market_context: Dict[str, Any]
    contracts: List[Dict[str, Any]]
    iv_term_structure: List[Dict[str, Any]]
    warnings: List[str]
    data_source: str  # LIVE / SYNTHETIC
    trust: Dict[str, Any]


class OptionsMapper:
    """Map raw chain data into scored, ranked contract table."""

    # Liquidity thresholds
    MIN_OI = 100
    GOOD_OI = 1000
    MIN_VOLUME = 50
    MAX_SPREAD_PCT = 5.0

    def __init__(
        self,
        options_provider: Any = None,
        expression_engine: Any = None,
    ):
        self._provider = options_provider
        self._ee = expression_engine

    async def build_screen(
        self,
        ticker: str,
        spot: float,
        rsi: float = 50,
        strategy: str = "auto",
        regime: str = "NEUTRAL",
        hist_vol: Optional[float] = None,
    ) -> OptionsScreenResult:
        """Build full options screen for a ticker.

        Parameters
        ----------
        ticker : str
        spot : float
            Current spot price.
        rsi : float
            Current RSI for directional bias.
        strategy : str
            "auto" | "long_call" | "long_put" | "debit_spread" | "credit_spread"
        regime : str
            Current market regime label.
        hist_vol : float, optional
            20-day historical volatility.
        """
        chain = None
        data_source = "SYNTHETIC"
        warnings: List[str] = []

        # ── 1. Fetch chain from provider ──
        if self._provider:
            try:
                chain = await self._provider.fetch_chain(ticker)
                if chain and chain.ticker:
                    data_source = "LIVE" if chain.expiry != "synthetic" else "SYNTHETIC"
            except Exception as exc:
                logger.warning("options provider error: %s", exc)

        # ── 2. Build market context from chain ──
        if chain:
            iv_rank = chain.iv_rank
            iv_pct = chain.iv_percentile
            skew = chain.skew_25d
            atm_iv = chain.atm_iv
            hv = chain.hv_20d or (hist_vol or 0.25)
        else:
            iv_rank = 35.0
            iv_pct = 35.0
            skew = -0.01
            atm_iv = 0.28
            hv = hist_vol or 0.25

        # Estimate earnings/ex-div proximity (synthetic)
        import hashlib

        import numpy as np

        # Use hashlib for deterministic seed across Python restarts
        # (hash() is randomized per-process via PYTHONHASHSEED)
        _stable_seed = int(hashlib.md5(ticker.encode()).hexdigest(), 16) % 2**31
        np.random.seed(_stable_seed)
        days_to_earnings = int(np.random.randint(10, 90))
        ex_div_days = int(np.random.randint(30, 120))

        context = {
            "iv_rank": round(iv_rank, 1),
            "iv_percentile": round(iv_pct, 1),
            "atm_iv": round(atm_iv, 4),
            "hv_20d": round(hv, 4),
            "iv_hv_ratio": (round(atm_iv / hv, 2) if hv > 0 else 1.0),
            "skew_25d": round(skew, 4),
            "days_to_earnings": days_to_earnings,
            "ex_dividend_days": ex_div_days,
        }

        # ── 3. Warnings ──
        if days_to_earnings < 14:
            warnings.append(
                f"⚠️ Earnings in {days_to_earnings} days — "
                "IV crush risk after announcement"
            )
        if iv_rank > 60:
            warnings.append(
                f"⚠️ IV rank {iv_rank:.0f}% — options are " "expensive (rich IV)"
            )
        if iv_pct > 70 and atm_iv / hv > 1.3:
            warnings.append(
                "⚠️ IV significantly above HV — consider " "spreads over single-leg"
            )
        if ex_div_days < 14:
            warnings.append(
                f"⚠️ Ex-dividend in {ex_div_days} days — "
                "early assignment risk for short calls"
            )

        # ── 4. Expression engine decision ──
        expression_decision = "stock"
        expression_rationale: Dict[str, Any] = {}
        rejection_reasons: List[str] = []

        if self._ee:
            try:
                options_data = {
                    "iv_percentile": iv_pct,
                    "avg_open_interest": (chain.total_oi // 10 if chain else 0),
                    "avg_bid_ask_spread": 0.03,
                }
                plan = self._ee.select_expression(
                    ticker=ticker,
                    direction="LONG" if rsi > 45 else "SHORT",
                    signal_data={
                        "confidence": min(0.9, rsi / 100 + 0.2),
                        "rsi": rsi,
                        "hold_period_days": 14,
                        "expected_return": 0.05,
                        "risk_reward_ratio": 2.0,
                    },
                    options_data=options_data,
                )
                expression_decision = plan.get(
                    "instrument",
                    "stock",
                )
                expression_rationale = {
                    "chosen_instrument": expression_decision,
                    "reason": plan.get("reason", ""),
                    "legs": plan.get("option_legs", []),
                    "leverage_ratio": plan.get(
                        "leverage_ratio",
                        1.0,
                    ),
                    "max_risk_pct": plan.get("max_risk_pct", 0.01),
                }

                # Collect rejection reasons
                reason = plan.get("reason", "")
                if reason == "options_disabled":
                    rejection_reasons.append("Options trading is disabled in config")
                elif reason == "no_options_data":
                    rejection_reasons.append("No options chain data available")
                elif reason == "illiquid_options":
                    rejection_reasons.append(
                        f"OI below {self._ee.MIN_OPTION_OI} " "threshold"
                    )
                elif reason == "wide_spreads":
                    rejection_reasons.append("Bid-ask spreads too wide")
                elif reason == "hold_too_long_for_options":
                    rejection_reasons.append("Hold period > 30 days — stock preferred")

            except Exception as exc:
                logger.warning("expression engine error: %s", exc)
                expression_rationale = {"error": str(exc)}

        # Override from user strategy param
        if strategy != "auto":
            expression_decision = strategy

        # ── 5. Build contract table ──
        contracts = self._build_contracts(
            ticker,
            spot,
            iv_pct,
            atm_iv,
            expression_decision,
            chain,
            data_source,
        )

        # ── 6. IV term structure ──
        iv_term = self._build_iv_term(atm_iv, skew)

        trust = {
            "mode": "LIVE" if data_source == "LIVE" else "SYNTHETIC",
            "source": (
                "options_provider" if data_source == "LIVE" else "synthetic_estimates"
            ),
            "chain_available": chain is not None,
            "expression_engine_used": self._ee is not None,
            "data_warning": (
                "SYNTHETIC OPTIONS DATA — simulated contracts. "
                "Not from live options chain feed."
                if data_source == "SYNTHETIC"
                else None
            ),
        }

        return OptionsScreenResult(
            ticker=ticker,
            spot_price=round(spot, 2),
            expression_decision=expression_decision,
            expression_rationale=expression_rationale,
            rejection_reasons=rejection_reasons,
            market_context=context,
            contracts=contracts[:10],
            iv_term_structure=iv_term,
            warnings=warnings,
            data_source=data_source,
            trust=trust,
        )

    # ------------------------------------------------------------------
    # Contract builder
    # ------------------------------------------------------------------

    def _build_contracts(
        self,
        ticker: str,
        spot: float,
        iv_pct: float,
        atm_iv: float,
        expression: str,
        chain: Any,
        source: str,
    ) -> List[Dict[str, Any]]:
        """Build ranked contract list."""
        import numpy as np

        contracts = []
        is_call = "call" in expression.lower() or "put" not in expression.lower()

        # Use real strikes if chain has them
        if chain and chain.strikes:
            for strike_data in chain.strikes[:15]:
                c = self._score_contract(
                    strike_data,
                    spot,
                    is_call,
                )
                if c:
                    contracts.append(c)
        else:
            # Generate synthetic contracts
            base_strike = int(spot / 5) * 5
            for i in range(12):
                strike = base_strike + (i - 4) * 5 * (1 if is_call else -1)
                dte_choices = [
                    30,
                    45,
                    60,
                    90,
                    120,
                    180,
                    365,
                ]
                dte = int(np.random.choice(dte_choices))
                moneyness = abs(strike - spot) / spot

                # Black-Scholes-ish mid price
                d = max(
                    0.05,
                    0.5 - moneyness * 2,
                )
                mid = max(
                    0.3,
                    spot * d * atm_iv * math.sqrt(dte / 365),
                )
                oi = int(np.random.randint(100, 5000))
                spread_pct = round(
                    np.random.uniform(0.5, 4.0),
                    1,
                )

                # Liquidity score (0-100)
                liq_score = min(
                    100,
                    int(
                        (min(oi, 3000) / 3000 * 50) + (max(0, 5 - spread_pct) / 5 * 50)
                    ),
                )

                breakeven = (
                    round(strike + mid, 2) if is_call else round(strike - mid, 2)
                )

                # EV estimate
                ev = round(
                    max(
                        0,
                        d * 2 - spread_pct * 0.1 + (50 - iv_pct) / 100,
                    ),
                    2,
                )

                contracts.append(
                    {
                        "strike": strike,
                        "dte": dte,
                        "type": "CALL" if is_call else "PUT",
                        "delta": round(d, 3),
                        "mid": round(mid, 2),
                        "oi": oi,
                        "spread_pct": spread_pct,
                        "liquidity_score": liq_score,
                        "ev": ev,
                        "breakeven": breakeven,
                        "breakeven_pct": round(
                            (breakeven / spot - 1) * 100,
                            1,
                        ),
                        "max_loss": int(mid * 100),
                        "source": source,
                    }
                )

        # Rank by EV
        contracts.sort(
            key=lambda c: c.get("ev", 0),
            reverse=True,
        )
        for i, c in enumerate(contracts):
            c["rank"] = i + 1

        return contracts

    @staticmethod
    def _score_contract(
        strike_data: Dict,
        spot: float,
        is_call: bool,
    ) -> Optional[Dict[str, Any]]:
        """Score a single real contract from chain data."""
        try:
            strike = strike_data.get("strike", 0)
            if strike <= 0:
                return None

            dte = strike_data.get("dte", 30)
            delta = strike_data.get("delta", 0.5)
            mid = strike_data.get("mid", 0)
            oi = strike_data.get("oi", 0)
            volume = strike_data.get("volume", 0)
            bid = strike_data.get("bid", 0)
            ask = strike_data.get("ask", 0)
            iv = strike_data.get("iv", 0.3)

            spread_pct = round((ask - bid) / mid * 100, 1) if mid > 0 else 99.0

            liq_score = min(
                100,
                int(
                    (min(oi, 3000) / 3000 * 40)
                    + (min(volume, 500) / 500 * 30)
                    + (max(0, 5 - spread_pct) / 5 * 30)
                ),
            )

            breakeven = round(strike + mid, 2) if is_call else round(strike - mid, 2)

            ev = round(max(0, abs(delta) * 2 - spread_pct * 0.1), 2)

            return {
                "strike": strike,
                "dte": dte,
                "type": "CALL" if is_call else "PUT",
                "delta": round(abs(delta), 3),
                "iv": round(iv, 4),
                "mid": round(mid, 2),
                "bid": round(bid, 2),
                "ask": round(ask, 2),
                "oi": oi,
                "volume": volume,
                "spread_pct": spread_pct,
                "liquidity_score": liq_score,
                "ev": ev,
                "breakeven": breakeven,
                "breakeven_pct": round(
                    (breakeven / spot - 1) * 100,
                    1,
                ),
                "max_loss": int(mid * 100),
                "source": "LIVE",
            }
        except Exception:
            return None

    # ------------------------------------------------------------------
    # IV term structure
    # ------------------------------------------------------------------

    @staticmethod
    def _build_iv_term(
        atm_iv: float,
        skew: float,
    ) -> List[Dict[str, Any]]:
        """Build IV term structure across DTEs."""
        import numpy as np

        term = []
        for dte in [7, 14, 30, 45, 60, 90, 120, 180, 365]:
            # Term structure slope + noise
            iv = (
                atm_iv
                + math.log(max(dte, 1) / 30) * 0.03
                + skew * (dte / 365)
                + np.random.uniform(-0.005, 0.005)
            )
            term.append(
                {
                    "dte": dte,
                    "iv": round(max(0.05, iv), 4),
                }
            )
        return term
