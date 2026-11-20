"""Fail-closed regime permission + synthetic regime handling."""

from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from src.core.regime_gate import regime_allows_trading
from src.services.regime_service import RegimeService


@pytest.mark.parametrize(
    "regime",
    [
        None,
        {},
        {"should_trade": None},
        {"should_trade": "true"},
        {"should_trade": float("nan")},
        {"should_trade": 1},
        {"should_trade": 1.0},
        {"should_trade": [True]},
        {"should_trade": False},
        {"should_trade": True, "synthetic": True},
        {"should_trade": True, "verified": False},
        {"should_trade": True, "stale": True},
        SimpleNamespace(),
        SimpleNamespace(should_trade=True, synthetic=True),
    ],
)
def test_denies_missing_synthetic_or_unverified(regime):
    assert regime_allows_trading(regime) is False


@pytest.mark.parametrize(
    "regime",
    [
        {"should_trade": True},
        {"should_trade": True, "synthetic": False, "verified": True},
        {"should_trade": np.bool_(True)},
        SimpleNamespace(should_trade=True),
    ],
)
def test_allows_only_explicit_real_permission(regime):
    assert regime_allows_trading(regime) is True


def test_default_regime_never_permits_trading():
    d = RegimeService._default_regime()
    assert d["should_trade"] is False
    assert d["synthetic"] is True and d["verified"] is False
    assert regime_allows_trading(d) is False


def test_synthetic_closes_never_permit_trading(monkeypatch):
    monkeypatch.setattr(RegimeService, "_is_synthetic", True, raising=False)
    monkeypatch.setattr(
        RegimeService, "_fetch_closes", classmethod(lambda cls: cls._synthetic_closes())
    )
    regime = RegimeService._fetch_and_compute()
    assert regime["synthetic"] is True
    assert regime["should_trade"] is False
    assert regime_allows_trading(regime) is False


def test_synthetic_result_is_not_cached_for_four_hours(monkeypatch):
    monkeypatch.setattr(RegimeService, "_cache", {})
    monkeypatch.setattr(RegimeService, "_cache_time", 0)
    monkeypatch.setattr(
        RegimeService,
        "_fetch_and_compute",
        classmethod(lambda cls: {"should_trade": False, "synthetic": True}),
    )
    RegimeService.get()
    import time

    remaining = RegimeService.CACHE_TTL - (time.time() - RegimeService._cache_time)
    assert remaining <= RegimeService.SYNTHETIC_RETRY_S + 1


def test_stale_cache_on_refresh_failure_never_permits_trading(monkeypatch):
    cached = {"should_trade": True, "synthetic": False, "verified": True, "vix": 14.0}
    monkeypatch.setattr(RegimeService, "_cache", cached)
    monkeypatch.setattr(RegimeService, "_cache_time", 0)  # expired

    def boom(cls):
        raise RuntimeError("feed down")

    monkeypatch.setattr(RegimeService, "_fetch_and_compute", classmethod(boom))
    regime = RegimeService.get()
    assert regime["stale"] is True
    assert regime["vix"] == 14.0
    assert regime_allows_trading(regime) is False
    assert cached["should_trade"] is True  # cache itself not mutated


def _real_closes(n_spy=60, vix=True):
    rising = [100.0 + i * 0.1 for i in range(n_spy)]
    closes = {"SPY": rising, "QQQ": rising, "IWM": rising, "HYG": rising}
    if vix:
        closes["^VIX"] = [13.0] * 60
    return closes


def _compute_with(monkeypatch, closes):
    def fetch(cls):
        cls._is_synthetic = False
        return closes

    monkeypatch.setattr(RegimeService, "_fetch_closes", classmethod(fetch))
    return RegimeService._fetch_and_compute()


def test_complete_real_inputs_can_permit_trading(monkeypatch):
    regime = _compute_with(monkeypatch, _real_closes())
    assert regime["verified"] is True and "missing_inputs" not in regime
    assert regime["should_trade"] is (regime["risk_score"] < 75)


@pytest.mark.parametrize(
    "closes,missing",
    [
        (_real_closes(vix=False), ["^VIX"]),
        (_real_closes(n_spy=10), ["SPY"]),
    ],
)
def test_partial_inputs_never_permit_trading(monkeypatch, closes, missing):
    regime = _compute_with(monkeypatch, closes)
    assert regime["missing_inputs"] == missing
    assert regime["verified"] is False
    assert regime["should_trade"] is False
    assert regime_allows_trading(regime) is False
    if "^VIX" in missing:
        assert regime["vix"] is None


def test_portfolio_brief_prompt_does_not_invent_vix(monkeypatch):
    import asyncio

    from src.services.ai_service import AIService

    prompts = []

    async def capture(self, system, user_prompt, *a, **k):
        prompts.append(user_prompt)
        return ""

    monkeypatch.setattr(AIService, "_call_llm", capture)
    asyncio.run(AIService.__new__(AIService).generate_brief([], {"vix": None}))
    assert "VIX n/a" in prompts[0]


def test_playbook_does_not_default_to_trade():
    from src.notifications.daily_playbook import DailyPlaybookBuilder

    card = DailyPlaybookBuilder().build(regime_state={"regime": "x"})
    assert card.should_trade is False


def test_llm_prompts_do_not_default_to_trade_or_invent_vix(monkeypatch):
    import asyncio

    from src.services.ai_service import AIService

    prompts = []

    async def capture(self, system, user_prompt, *a, **k):
        prompts.append(user_prompt)
        return ""

    monkeypatch.setattr(AIService, "_call_llm", capture)
    svc = AIService.__new__(AIService)
    regime = {"label": "x", "vix": None}  # no should_trade, no VIX
    asyncio.run(svc.generate_narrative(regime, [], {}, {}))
    asyncio.run(svc.generate_brief([], regime))
    joined = "\n".join(prompts)
    assert "Trade: True" not in joined and "Trade: False" in joined
    assert "VIX n/a" in joined and "VIX 18" not in joined
