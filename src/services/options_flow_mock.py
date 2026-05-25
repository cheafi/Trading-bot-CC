from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from src.services.options_flow_provider import (
    OptionsFlowEvent,
    OptionsFlowProvider,
    OptionsFlowTrust,
    OptionsProviderStatus,
)


class MockOptionsFlowProvider(OptionsFlowProvider):
    """Deterministic mock provider for tests and local demos.

    Output is explicitly synthetic/mock via trust metadata. Production routes can
    still use it for fallback, but the dashboard must show the mock/synthetic flag.
    """

    name = "mock"

    async def fetch_recent_events(
        self,
        universe: Optional[List[str]] = None,
        *,
        limit: int = 500,
    ) -> List[OptionsFlowEvent]:
        allowed = {ticker.upper() for ticker in universe or []}
        now = datetime.now(timezone.utc)
        events = [
            OptionsFlowEvent(
                underlying="SOUN",
                contract_symbol="SOUN260515C00008000",
                side_bias="CALL_BUYING",
                call_put="C",
                strike=8.0,
                expiry=(now + timedelta(days=3)).date(),
                dte=3,
                trade_timestamp=now - timedelta(seconds=45),
                premium=420_000,
                price=1.40,
                size=3000,
                bid=1.38,
                ask=1.42,
                volume=8200,
                open_interest=2100,
                volume_vs_avg_ratio=5.4,
                sweep_flag=True,
                block_flag=True,
                repeated_directional_prints=7,
                iv=0.94,
                iv_change=0.18,
                stock_price=7.65,
                stock_move_pct=1.2,
                underlying_avg_volume=19_000_000,
                underlying_dollar_volume=145_000_000,
                market_cap=1_900_000_000,
                regime_alignment=0.72,
                relative_strength=0.66,
                trust=OptionsFlowTrust(
                    source="mock", mode="mock", delay_seconds=45, synthetic=True
                ),
            ),
            OptionsFlowEvent(
                underlying="AAPL",
                contract_symbol="AAPL260515C00250000",
                side_bias="CALL_BUYING",
                call_put="C",
                strike=250.0,
                expiry=(now + timedelta(days=10)).date(),
                dte=10,
                trade_timestamp=now - timedelta(seconds=90),
                premium=980_000,
                price=2.45,
                size=4000,
                bid=2.40,
                ask=2.50,
                volume=30_000,
                open_interest=85_000,
                volume_vs_avg_ratio=1.4,
                repeated_directional_prints=2,
                iv=0.31,
                iv_change=0.03,
                stock_price=238.0,
                stock_move_pct=0.5,
                underlying_avg_volume=52_000_000,
                underlying_dollar_volume=12_400_000_000,
                market_cap=3_500_000_000_000,
                regime_alignment=0.58,
                relative_strength=0.55,
                trust=OptionsFlowTrust(
                    source="mock", mode="mock", delay_seconds=90, synthetic=True
                ),
            ),
            OptionsFlowEvent(
                underlying="RILY",
                contract_symbol="RILY260515P00005000",
                side_bias="PUT_BUYING",
                call_put="P",
                strike=5.0,
                expiry=(now + timedelta(days=2)).date(),
                dte=2,
                trade_timestamp=now - timedelta(seconds=120),
                premium=8_000,
                price=0.08,
                size=1000,
                bid=0.01,
                ask=0.15,
                volume=1100,
                open_interest=80,
                volume_vs_avg_ratio=7.0,
                iv=2.2,
                iv_change=0.35,
                stock_price=7.1,
                stock_move_pct=-8.5,
                underlying_avg_volume=780_000,
                underlying_dollar_volume=5_500_000,
                market_cap=210_000_000,
                regime_alignment=0.20,
                relative_strength=0.10,
                trust=OptionsFlowTrust(
                    source="mock", mode="mock", delay_seconds=120, synthetic=True
                ),
            ),
        ]
        if allowed:
            events = [event for event in events if event.underlying in allowed]
        return events[:limit]

    async def health(self) -> OptionsProviderStatus:
        return OptionsProviderStatus(
            provider=self.name,
            enabled=True,
            mode="mock",
            status="ok",
            message="Deterministic mock options-flow provider; data is synthetic.",
            delay_seconds=0,
            last_update=datetime.now(timezone.utc).isoformat(),
        )
