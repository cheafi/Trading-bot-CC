"""Deploy gate and trade gate Discord alert handlers."""

from __future__ import annotations

from unittest import mock

from src.services import alert_service as alerts


def test_on_deploy_gate_change_unlocked():
    with mock.patch.object(alerts, "_push_discord", return_value=True) as push:
        with mock.patch.object(alerts, "_append_log"):
            with mock.patch(
                "src.services.system_telegram_alerts.push_deploy_gate_change",
                return_value=True,
            ) as tg_push:
                ok = alerts.on_deploy_gate_change(
                    unlocked=True,
                    summary="All four conditions met.",
                    tradeability="SELECTIVE",
                )
    assert ok is True
    push.assert_called_once()
    tg_push.assert_called_once()
    kwargs = push.call_args.kwargs
    assert "UNLOCKED" in push.call_args.args[0]
    assert kwargs.get("zh_summary")


def test_on_deploy_gate_change_locked_lists_remaining():
    with mock.patch.object(alerts, "_push_discord", return_value=True) as push:
        with mock.patch.object(alerts, "_append_log"):
            alerts.on_deploy_gate_change(
                unlocked=False,
                summary="Gate not cleared.",
                remaining=["Broker handoff is live"],
            )
    assert "LOCKED" in push.call_args.args[0]
    assert "Broker" in push.call_args.args[1]


def test_on_bdr_decision_change_skips_same_code():
    with mock.patch.object(alerts, "_push_discord") as push:
        assert alerts.on_bdr_decision_change("NO_TRADE", "NO_TRADE") is False
        push.assert_not_called()


def test_on_trade_gate_blocked():
    with mock.patch.object(alerts, "_push_discord", return_value=True) as push:
        with mock.patch.object(alerts, "_append_log"):
            with mock.patch(
                "src.services.system_telegram_alerts.push_trade_gate_blocked",
                return_value=True,
            ) as tg_push:
                ok = alerts.on_trade_gate_blocked(["VIX at 50 — hard block"])
    assert ok is True
    assert "Trade Gate BLOCKED" in push.call_args.args[0]
    tg_push.assert_called_once()
