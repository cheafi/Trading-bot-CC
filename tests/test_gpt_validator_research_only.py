"""GPT validator is research-only — must not affect execution eligibility."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.core.models import Direction, Signal
from src.engines.gpt_validator import GPTSignalValidator


@pytest.mark.asyncio
async def test_validate_batch_marks_research_only() -> None:
    signal = Signal(
        ticker="AAPL",
        direction=Direction.LONG,
        entry_price=100.0,
        confidence=70.0,
        strategy_id="SWING",
    )
    validator = GPTSignalValidator()
    with patch.object(
        validator,
        "validate_signal",
        new=AsyncMock(
            return_value={
                "validation_result": "FAIL",
                "approval_status": "rejected",
            }
        ),
    ):
        results = await validator.validate_batch(
            signals=[signal],
            news_by_ticker={"AAPL": []},
            sentiment_by_ticker={"AAPL": "neutral"},
            research_only=True,
        )

    assert results[0]["authority"] == "research_only"
    assert results[0]["affects_execution"] is False
    assert results[0]["broker_eligible"] is False
