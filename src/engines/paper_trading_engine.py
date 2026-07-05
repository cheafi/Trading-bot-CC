import asyncio
import logging
from typing import Dict, Any

from src.services.pm_arena_service import get_pm_arena_service
from src.services.ibkr_service import get_ibkr_service
from src.services.brief_data_service import BriefDataService
from src.services.market_data import get_market_data_service

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    def __init__(self):
        self.ibkr = get_ibkr_service()
        self.arena = get_pm_arena_service()
        self.brief_svc = BriefDataService()
        self.market_data = get_market_data_service()
        self.total_paper_capital = 100000.0
        self.max_position_size_pct = 0.20  # Max 20% per position (Kelly ceiling)

    async def execute_top_strategy(self):
        logger.info(
            "[PAPER TRADER] Booting up institutional paper trading execution sync..."
        )
        # Ensure connected in paper mode
        if not self.ibkr.is_connected:
            logger.info("[PAPER TRADER] Ensuring IBKR paper connection...")
            res = await self.ibkr.connect(mode="paper")
            if not res.get("ok"):
                logger.error(f"[PAPER TRADER] Failed to connect to IBKR: {res}")
                return

        summary = await self.ibkr.get_account_summary()
        if summary:
            self.total_paper_capital = summary.net_liquidation
            logger.info(
                f"[PAPER TRADER] Account value: ${self.total_paper_capital:,.2f}"
            )

        # 1. Retrieve the optimal portfolio state from the PM Arena
        brief = await self.brief_svc.get_cached_brief()
        if not brief:
            logger.warning(
                "[PAPER TRADER] No brief available. Try building signals first."
            )
            return

        # 2. Get PM arena overview based on playbook
        overview = self.arena.build_overview(brief)
        funds = overview.get("funds", [])
        if not funds:
            logger.warning("[PAPER TRADER] No funds found in PM arena.")
            return

        # Top strategy is index 0 since they are sorted by pm_score
        top_fund = funds[0]
        logger.info(
            f"[PAPER TRADER] Top Fund Selected: {top_fund['display_name']} (Score: {top_fund['scoreboard']['pm_score']})"
        )

        # Guard: Check Trust Label
        if "Training" in top_fund.get("trust_label", ""):
            logger.info(
                f"[PAPER TRADER] Top fund '{top_fund['display_name']}' is marked as Simulation/Training. Proceeding with paper execution as requested."
            )

        holdings = top_fund.get("holdings") or []
        if not holdings:
            logger.info(
                f"[PAPER TRADER] Action book is empty for {top_fund['display_name']}."
            )
            return

        # 3. Synchronize with IBKR
        positions = await self.ibkr.get_positions()
        current_symbols = {p.symbol for p in positions if float(p.position) > 0}

        for item in holdings:
            symbol = item["ticker"]
            action = item.get("action", "HOLD")
            target_weight = min(
                float(item.get("weight", 0.0)), self.max_position_size_pct
            )

            logger.info(
                f"[PAPER TRADER] Evaluating {symbol} - Action: {action}, Target Weight: {target_weight:.2%}"
            )

            if action in ("BUY", "ADD") and symbol not in current_symbols:
                # Institutional execution: Fetch live quote for precision sizing & limit pegging
                quote = await self.market_data.get_quote(symbol)
                current_price = quote.get("price") if quote else None

                if current_price and current_price > 0:
                    capital_to_deploy = self.total_paper_capital * target_weight
                    target_shares = int(capital_to_deploy // current_price)

                    if target_shares > 0:
                        # Smart Execution: Send Limit order at last price instead of naive MKT
                        logger.info(
                            f"[PAPER TRADER] Routing execution format for {symbol} | Target: {target_weight:.1%} | Shares: {target_shares} | LMT: {current_price}"
                        )
                        res = await self.ibkr.place_order(
                            symbol=symbol,
                            sec_type="STK",
                            action="BUY",
                            quantity=target_shares,
                            order_type="LMT",
                            limit_price=current_price,
                        )
                        logger.info(
                            f"[PAPER TRADER] IBKR Yield: {res.status} | ID: {res.order_id}"
                        )
                else:
                    logger.warning(
                        f"[PAPER TRADER] Could not resolve live price for {symbol}, deferring execution."
                    )

            elif action in ("SELL", "REDUCE") and symbol in current_symbols:
                pos_obj = next((p for p in positions if p.symbol == symbol), None)
                if pos_obj and pos_obj.position > 0:
                    logger.info(
                        f"[PAPER TRADER] Routing unload execution for {symbol} | Shares: {pos_obj.position}"
                    )
                    res = await self.ibkr.place_order(
                        symbol=symbol,
                        sec_type="STK",
                        action="SELL",
                        quantity=pos_obj.position,
                        order_type="MKT",  # Market order on exits to guarantee execution of risk stops
                    )
                    logger.info(
                        f"[PAPER TRADER] IBKR Yield: {res.status} | ID: {res.order_id}"
                    )

        logger.info("[PAPER TRADER] Institutional sync module cycle complete.")
