"""Trading mode resolution — paper default, dual-gate live."""

from __future__ import annotations

import pytest

from src.core.trading_mode import resolve_dry_run, resolve_execution_mode
from src.engines.auto_trading_engine import AutoTradingEngine


@pytest.mark.parametrize(
    ("env", "live_cli", "expect_dry_run", "expect_ambiguous"),
    [
        ({}, False, True, False),
        ({"LIVE_TRADING": "1"}, False, True, True),
        ({}, True, True, True),
        ({"LIVE_TRADING": "1"}, True, False, False),
        ({"TRADING_ENV": "live"}, True, False, False),
        ({"DRY_RUN": "false"}, False, True, True),
    ],
)
def test_resolve_execution_mode_dual_gate(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    live_cli: bool,
    expect_dry_run: bool,
    expect_ambiguous: bool,
) -> None:
    for key in ("LIVE_TRADING", "TRADING_ENV", "DRY_RUN"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    resolution = resolve_execution_mode(live_cli=live_cli)
    assert resolution.dry_run is expect_dry_run
    assert resolution.ambiguous is expect_ambiguous


def test_resolve_dry_run_exits_on_ambiguous(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LIVE_TRADING", raising=False)
    monkeypatch.delenv("TRADING_ENV", raising=False)
    monkeypatch.delenv("DRY_RUN", raising=False)
    monkeypatch.setenv("DRY_RUN", "false")

    with pytest.raises(SystemExit):
        resolve_dry_run(live_cli=False)


def test_auto_trading_engine_defaults_to_paper() -> None:
    engine = AutoTradingEngine()
    assert engine.dry_run is True
