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
        {"should_trade": False},
        {"should_trade": True, "synthetic": True},
        {"should_trade": True, "verified": False},
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
