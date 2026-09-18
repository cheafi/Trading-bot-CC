"""Live trading gate — paper default, live requires exact env triple + account."""

from __future__ import annotations

import pytest

from src.core.live_trading_gate import (
    LIVE_IB_API_PORT,
    LiveTradingAuthorisation,
    assert_live_gate_or_paper,
    authorize_live_order,
    evaluate_live_trading_gate,
)


@pytest.mark.parametrize(
    ("env", "expect_live", "expect_paper"),
    [
        ({}, False, True),
        ({"LIVE_TRADING": "1"}, False, True),
        ({"LIVE_TRADING": "1", "IB_MODE": "live"}, False, True),
        (
            {
                "LIVE_TRADING": "1",
                "IB_MODE": "live",
                "IB_API_PORT": LIVE_IB_API_PORT,
            },
            False,
            True,
        ),
        (
            {
                "LIVE_TRADING": "1",
                "IB_MODE": "live",
                "IB_API_PORT": LIVE_IB_API_PORT,
                "LIVE_TRADING_ACCOUNT": "DU123",
            },
            False,
            True,
        ),
        (
            {
                "LIVE_TRADING": "1",
                "IB_MODE": "live",
                "IB_PORT": LIVE_IB_API_PORT,
                "LIVE_TRADING_ACCOUNT": "DU123",
            },
            False,
            True,
        ),
        (
            {
                "LIVE_TRADING": "1",
                "IB_MODE": "live",
                "IB_API_PORT": "4002",
            },
            False,
            True,
        ),
        (
            {
                "LIVE_TRADING": "true",
                "IB_MODE": "live",
                "IB_API_PORT": LIVE_IB_API_PORT,
                "LIVE_TRADING_ACCOUNT": "DU123",
            },
            False,
            True,
        ),
        (
            {
                "LIVE_TRADING": "1",
                "IB_MODE": "LIVE",
                "IB_API_PORT": LIVE_IB_API_PORT,
                "LIVE_TRADING_ACCOUNT": "DU123",
            },
            False,
            True,
        ),
    ],
)
def test_evaluate_live_trading_gate_truth_table(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    expect_live: bool,
    expect_paper: bool,
) -> None:
    for key in ("LIVE_TRADING", "IB_MODE", "IB_API_PORT", "LIVE_TRADING_ACCOUNT"):
        monkeypatch.delenv(key, raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, value)

    result = evaluate_live_trading_gate()
    assert isinstance(result, LiveTradingAuthorisation)
    assert result.live_allowed is expect_live
    assert result.paper_by_construction is expect_paper


def test_authorize_live_order_requires_allow_list_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIVE_TRADING", "1")
    monkeypatch.setenv("IB_MODE", "live")
    monkeypatch.setenv("IB_API_PORT", LIVE_IB_API_PORT)
    monkeypatch.setenv("LIVE_TRADING_ACCOUNT", "DU123,DU456")

    denied = authorize_live_order("DU999")
    assert denied.live_allowed is False

    allowed = authorize_live_order("du123")
    assert allowed.live_allowed is True
    assert allowed.account_allowed is True


def test_assert_live_gate_exits_when_live_requested_but_incomplete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("LIVE_TRADING", "IB_MODE", "IB_API_PORT", "LIVE_TRADING_ACCOUNT"):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(SystemExit):
        assert_live_gate_or_paper(live_requested=True)


def test_evaluate_live_gate_denies_blank_or_whitespace_account(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LIVE_TRADING", "1")
    monkeypatch.setenv("IB_MODE", "live")
    monkeypatch.setenv("IB_API_PORT", LIVE_IB_API_PORT)
    monkeypatch.setenv("LIVE_TRADING_ACCOUNT", "DU123")

    for acct in ("", "   ", "\t"):
        result = authorize_live_order(acct)
        assert result.live_allowed is False
        assert result.paper_by_construction is True


def test_assert_live_gate_allows_paper_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("LIVE_TRADING", "IB_MODE", "IB_API_PORT", "LIVE_TRADING_ACCOUNT"):
        monkeypatch.delenv(key, raising=False)

    assert assert_live_gate_or_paper(live_requested=False) is True
