"""Research console bootstrap cache."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.services import research_console_bootstrap as rcb


class _FakeMds:
    async def get_history(self, *args, **kwargs):
        return None


async def _run_twice(force_second: bool = False):
    req = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(market_data=_FakeMds())))
    with patch.object(
        rcb,
        "build_correlation_regime_timeline",
        new=AsyncMock(return_value={"ok": False}),
    ):
        first = await rcb.bootstrap_research_console(req)
        second = await rcb.bootstrap_research_console(req, force_refresh=force_second)
    return first, second


def test_bootstrap_cache_hit() -> None:
    first, second = asyncio.run(_run_twice())
    assert first.get("cached") is False
    assert second.get("cached") is True


def test_bootstrap_force_refresh() -> None:
    _, second = asyncio.run(_run_twice(force_second=True))
    assert second.get("cached") is False
