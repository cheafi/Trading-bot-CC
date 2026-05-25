import asyncio

from src.api.routers.ai_advisor import router as ai_router
from src.services.ai_service import get_ai_service
from src.services.fund_ai_service import get_fund_ai_service
from src.services.trade_memory_service import get_trade_memory_service
from src.services.trade_review_ai_service import get_trade_review_ai_service


async def main() -> None:
    fund_card = {
        "id": "LEADER_MOMENTUM",
        "display_name": "Leader Momentum",
        "mandate": "Momentum leaders with strict regime gating.",
        "gate_status": "ACTIVE",
        "fund_return_pct": 12.4,
        "excess_return_pct": 3.1,
        "sharpe": 1.4,
        "max_drawdown_pct": -6.2,
        "regime_fit": 92,
        "risk_level": "HIGH",
        "min_r_r": 3.0,
        "holdings": [
            {"ticker": "NVDA", "weight": 0.18, "score": 9.4},
            {"ticker": "META", "weight": 0.14, "score": 8.7},
        ],
        "adds": ["NVDA"],
        "reduces": [],
        "exits": [],
    }
    fund_ai = get_fund_ai_service()
    memo = await fund_ai.build_pm_memo(fund_card, "BULL", "SPY")
    expert = await fund_ai.build_expert_view(fund_card, "BULL")

    memory = get_trade_memory_service()
    trade = await memory.find_trade()
    review = None
    if trade:
        review = await get_trade_review_ai_service().review_trade(
            trade, similar_limit=2
        )

    print(
        {
            "memo_keys": sorted(memo.keys()),
            "expert_keys": sorted(expert.keys()),
            "found_trade": bool(trade),
            "review_keys": sorted(review.keys()) if review else [],
            "similar_count": len(review.get("similar_cases", [])) if review else 0,
            "advisor_routes": sorted(route.path for route in ai_router.routes),
        }
    )
    await get_ai_service().close()


if __name__ == "__main__":
    asyncio.run(main())
