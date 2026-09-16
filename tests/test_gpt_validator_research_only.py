"""GPT validator is research-only — must not affect execution eligibility."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.models import Direction, Horizon, Invalidation, Signal, StopType, Target
from src.engines.gpt_validator import GPTSignalValidator


def _sample_signal(**overrides) -> Signal:
    payload = {
        "ticker": "AAPL",
        "direction": Direction.LONG,
        "horizon": Horizon.SWING_1_5D,
        "entry_price": 100.0,
        "invalidation": Invalidation(stop_price=95.0, stop_type=StopType.HARD),
        "targets": [Target(price=110.0, pct_position=100)],
        "entry_logic": "test setup",
        "catalyst": "test catalyst",
        "key_risks": ["test risk"],
        "confidence": 70,
        "rationale": "test rationale",
        "strategy_id": "SWING",
    }
    payload.update(overrides)
    return Signal(**payload)


@pytest.mark.asyncio
async def test_validate_batch_marks_research_only() -> None:
    signal = _sample_signal()
    with patch(
        "src.engines.gpt_validator.get_openai_client",
        return_value=MagicMock(),
    ):
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


def test_validate_signals_entry_path_returns_all_signals() -> None:
    """LLM annotations must not filter signals before ranking (one-way architecture)."""
    from pathlib import Path

    source = Path("src/engines/auto_trading_engine.py").read_text(encoding="utf-8")
    start = source.index("async def _validate_signals")
    end = source.index("async def _execute_recommendation", start)
    block = source[start:end]

    assert "research_only=True" in block
    assert '"affects_execution": False' in block
    assert "return signals" in block
    assert "filter(" not in block
    assert "remove(" not in block
