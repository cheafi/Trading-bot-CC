"""
Expression Engine.

Decides *how* to express a trade idea: stock, single-leg option,
debit spread, credit spread, or no-trade.

This converts a directional view into a concrete instrument choice
based on IV environment, options liquidity, hold period,
and account constraints.
"""
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class ExpressionEngine:
    """
    Given a trade idea (ticker + direction + view), select the
    optimal instrument for execution.

    Decision grid:
    ┌──────────────────────┬────────────────────────────┐
    │ Condition            │ Expression                 │
    ├──────────────────────┼────────────────────────────┤
    │ Longer hold / illiq  │ Stock                      │
    │ Directional + low IV │ Long CALL / PUT            │
    │ Directional + hi IV  │ Debit spread               │
    │ Range + IV rich      │ Credit spread              │
    │ IV too expensive     │ Stock or no-trade           │
    │ No liquid options    │ Stock                      │
    │ Spreads too wide     │ Stock or no-trade           │
    └──────────────────────┴────────────────────────────┘
    """

    # Thresholds
    MIN_OPTION_OI = 500          # open interest floor
    MAX_BID_ASK_SPREAD = 0.05    # 5% of mid price
    IV_PERCENTILE_LOW = 30       # below this = cheap IV
    IV_PERCENTILE_HIGH = 70      # above this = rich IV
    MIN_DTE = 14                 # minimum days to expiry
    DEFAULT_DTE_TARGET = 45      # ideal DTE for options

    def __init__(
        self,
        options_enabled: bool = None,
        max_option_allocation: float = None,
    ):
        """
        Args:
            options_enabled: master switch for options
            max_option_allocation: max portfolio % in options
        """
        # Read from config with fallback
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            self.options_enabled = (
                options_enabled if options_enabled is not None
                else tc.options_enabled
            )
            self.max_option_allocation = (
                max_option_allocation or tc.max_option_allocation
            )
            self.MIN_OPTION_OI = tc.min_option_oi
        except Exception:
            self.options_enabled = options_enabled or False
            self.max_option_allocation = (
                max_option_allocation or 0.20
            )

    def select_expression(
        self,
        ticker: str,
        direction: str,
        signal_data: Dict[str, Any],
        options_data: Optional[Dict[str, Any]] = None,
        portfolio_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Determine how to express a trade idea.

        Args:
            ticker: symbol
            direction: LONG or SHORT
            signal_data: must have hold_period, expected_return,
                         confidence, risk_reward_ratio
            options_data: chain info with iv_percentile,
                         avg_spread, avg_oi, available_strikes
            portfolio_state: current portfolio for allocation
                           checks

        Returns:
            ExpressionPlan-compatible dict
        """
        hold_days = signal_data.get("hold_period_days", 5)
        confidence = signal_data.get("confidence", 0.5)
        exp_return = signal_data.get("expected_return", 0.02)
        rr_ratio = signal_data.get("risk_reward_ratio", 1.5)

        # Default: stock
        plan = {
            "instrument": "stock",
            "ticker": ticker,
            "direction": direction,
            "reason": "default_stock",
            "option_legs": [],
            "leverage_ratio": 1.0,
            "max_risk_pct": 0.01,
        }

        # Short-circuit: options disabled
        if not self.options_enabled:
            plan["reason"] = "options_disabled"
            return plan

        # Short-circuit: no options data
        if not options_data:
            plan["reason"] = "no_options_data"
            return plan

        # Evaluate options suitability
        iv_pct = options_data.get("iv_percentile", 50)
        avg_oi = options_data.get("avg_open_interest", 0)
        avg_spread = options_data.get("avg_bid_ask_spread", 1.0)

        # Gate 1: liquidity
        if avg_oi < self.MIN_OPTION_OI:
            plan["reason"] = "illiquid_options"
            return plan

        # Gate 2: spread too wide
        if avg_spread > self.MAX_BID_ASK_SPREAD:
            plan["reason"] = "wide_spreads"
            return plan

        # Gate 3: hold period too long for options
        if hold_days > 30:
            plan["reason"] = "hold_too_long_for_options"
            return plan

        # Gate 4: portfolio options allocation
        if portfolio_state:
            current_opt_alloc = portfolio_state.get(
                "options_allocation_pct", 0
            )
            if current_opt_alloc >= self.max_option_allocation:
                plan["reason"] = "max_options_allocation"
                return plan

        # ── Decision logic ────────────────────────────────
        if iv_pct <= self.IV_PERCENTILE_LOW and confidence >= 0.6:
            # Cheap IV + high confidence → long option
            plan = self._long_option_plan(
                ticker, direction, iv_pct, hold_days
            )
        elif iv_pct >= self.IV_PERCENTILE_HIGH:
            if confidence >= 0.65 and rr_ratio >= 2.0:
                # Rich IV + strong view → debit spread
                plan = self._debit_spread_plan(
                    ticker, direction, iv_pct, hold_days
                )
            elif confidence < 0.5:
                # Rich IV + weak view → credit spread
                plan = self._credit_spread_plan(
                    ticker, direction, iv_pct, hold_days
                )
            else:
                # Rich IV + moderate view → stock
                plan["reason"] = "iv_rich_moderate_view"
        else:
            # Mid IV → depends on conviction
            if confidence >= 0.7 and rr_ratio >= 2.5:
                plan = self._long_option_plan(
                    ticker, direction, iv_pct, hold_days
                )
            else:
                plan["reason"] = "mid_iv_stock_preferred"

        return plan

    def _long_option_plan(
        self,
        ticker: str,
        direction: str,
        iv_pct: float,
        hold_days: int,
    ) -> Dict[str, Any]:
        """Single long CALL or PUT."""
        option_type = "CALL" if direction == "LONG" else "PUT"
        dte = max(
            self.MIN_DTE, min(hold_days * 3, self.DEFAULT_DTE_TARGET)
        )
        return {
            "instrument": option_type,
            "ticker": ticker,
            "direction": direction,
            "reason": f"cheap_iv_{option_type.lower()}",
            "option_legs": [{
                "type": option_type,
                "side": "BUY",
                "dte_target": dte,
                "strike_method": "ATM",
            }],
            "leverage_ratio": 3.0,
            "max_risk_pct": 0.005,
            "iv_percentile": iv_pct,
        }

    def _debit_spread_plan(
        self,
        ticker: str,
        direction: str,
        iv_pct: float,
        hold_days: int,
    ) -> Dict[str, Any]:
        """Debit spread to cap vega risk in high IV."""
        opt_type = "CALL" if direction == "LONG" else "PUT"
        dte = max(
            self.MIN_DTE, min(hold_days * 3, self.DEFAULT_DTE_TARGET)
        )
        return {
            "instrument": "debit_spread",
            "ticker": ticker,
            "direction": direction,
            "reason": "high_iv_debit_spread",
            "option_legs": [
                {
                    "type": opt_type,
                    "side": "BUY",
                    "dte_target": dte,
                    "strike_method": "ATM",
                },
                {
                    "type": opt_type,
                    "side": "SELL",
                    "dte_target": dte,
                    "strike_method": "OTM_5PCT",
                },
            ],
            "leverage_ratio": 2.0,
            "max_risk_pct": 0.005,
            "iv_percentile": iv_pct,
        }

    def _credit_spread_plan(
        self,
        ticker: str,
        direction: str,
        iv_pct: float,
        hold_days: int,
    ) -> Dict[str, Any]:
        """Credit spread to sell rich IV."""
        # Sell opposite direction
        if direction == "LONG":
            sell_type, buy_type = "PUT", "PUT"
        else:
            sell_type, buy_type = "CALL", "CALL"
        dte = max(
            self.MIN_DTE, min(hold_days * 2, self.DEFAULT_DTE_TARGET)
        )
        return {
            "instrument": "credit_spread",
            "ticker": ticker,
            "direction": direction,
            "reason": "rich_iv_credit_spread",
            "option_legs": [
                {
                    "type": sell_type,
                    "side": "SELL",
                    "dte_target": dte,
                    "strike_method": "OTM_10PCT",
                },
                {
                    "type": buy_type,
                    "side": "BUY",
                    "dte_target": dte,
                    "strike_method": "OTM_15PCT",
                },
            ],
            "leverage_ratio": 1.5,
            "max_risk_pct": 0.008,
            "iv_percentile": iv_pct,
        }
