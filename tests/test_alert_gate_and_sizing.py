"""Validated-only alerts, fail-closed regime placeholder, equity-honest sizing."""

from __future__ import annotations

import asyncio

import pytest

from src.notifications import alert_gate


@pytest.fixture
def grades(monkeypatch):
    table = {}

    def fake(strategy_id, **kw):
        if strategy_id == "boom":
            raise RuntimeError("ledger unreadable")
        return {"grade": table.get(strategy_id, "NO_BACKTEST")}

    import src.services.strategy_health_service as shs

    monkeypatch.setattr(shs, "evidence_for_strategy", fake)
    return table


def test_only_validated_strategies_pass(grades):
    grades.update(good="VALIDATED", meh="PRELIMINARY", bad="FAILED_VALIDATION")
    sigs = [
        {"ticker": "A", "strategy_id": "good"},
        {"ticker": "B", "strategy_id": "meh"},
        {"ticker": "C", "strategy": "bad"},
        {"ticker": "D"},
        {"ticker": "E", "strategy_id": "boom"},
    ]
    keep, withheld = alert_gate.filter_validated(sigs)
    assert [s["ticker"] for s in keep] == ["A"]
    assert withheld == {
        "PRELIMINARY": 1,
        "FAILED_VALIDATION": 1,
        "NO_BACKTEST": 1,
        "UNAVAILABLE": 1,
    }
    assert "4 setup(s) withheld" in alert_gate.withheld_note(withheld)


def test_default_strategy_and_attribute_signals(grades):
    grades.update(discord_swing_pullback="VALIDATED")

    class Sig:
        strategy_id = None
        strategy = ""

    keep, withheld = alert_gate.filter_validated(
        [Sig(), {"t": 1}], "discord_swing_pullback"
    )
    assert len(keep) == 2 and not withheld
    assert alert_gate.filter_validated([Sig()])[0] == []


def test_multi_channel_sends_only_validated(grades, monkeypatch):
    from src.notifications.multi_channel import MultiChannelNotifier

    grades.update(good="VALIDATED")
    n = MultiChannelNotifier()
    sent = []

    class FakeChannel:
        is_configured = True

        async def send_signals_batch(self, signals):
            sent.append(list(signals))
            return len(signals)

        async def send_signal(self, signal):
            sent.append([signal])
            return True

    n.discord = FakeChannel()
    n.whatsapp = FakeChannel()
    out = asyncio.run(
        n.send_signals_batch([{"strategy_id": "good"}, {"strategy_id": "x"}])
    )
    assert out == {"discord": 1, "whatsapp": 1}
    assert all(batch == [{"strategy_id": "good"}] for batch in sent)

    sent.clear()
    assert asyncio.run(n.send_signals_batch([{"strategy_id": "x"}])) == {
        "discord": 0,
        "whatsapp": 0,
    }
    assert asyncio.run(n.send_signal({"strategy_id": "x"})) == {
        "discord": False,
        "whatsapp": False,
    }
    assert sent == []


def test_unavailable_regime_fails_closed():
    from src.core.regime_gate import regime_allows_trading
    from src.engines.regime_router import RegimeState, unavailable_regime

    st = unavailable_regime()
    assert st.should_trade is False and st.synthetic is True
    assert st.size_scalar == 0.0 and st.no_trade_reason == "REGIME_UNAVAILABLE"
    assert regime_allows_trading(st) is False
    assert RegimeState().synthetic is False


def test_core_model_regime_defaults_to_no_trade():
    from src.core.models import RegimeState

    assert RegimeState().should_trade is False


def test_size_requires_known_equity_and_real_stop():
    from src.services.stock_intel import _compute_size_shares

    dossier = {"price": 305, "technicals": {"atr": 4}}
    unified = {"entry_zone": [300, 310], "stop": 295}

    unknown = _compute_size_shares(dossier, unified)
    assert unknown["shares"] == 0 and unknown["equity_source"] is None
    assert unknown["risk_per_share"] == 10.0 and unknown["shares_per_1k_risk"] == 100
    assert "equity unknown" in unknown["size_explanation"]

    known = _compute_size_shares(dossier, unified, equity=50_000)
    assert known["shares"] == 50 and known["equity_source"] == "broker_account"

    no_stop = _compute_size_shares(dossier, {"entry_zone": [300, 310]}, equity=50_000)
    assert no_stop["shares"] == 0 and no_stop["risk_per_share"] is None


def test_every_scheduled_discord_scan_push_is_gated():
    """Any @tasks.loop that runs a signal scanner must pass it through the gate."""
    import ast
    import pathlib

    src = pathlib.Path("src/notifications/discord_bot.py").read_text()
    loops = [
        n
        for n in ast.walk(ast.parse(src))
        if isinstance(n, ast.AsyncFunctionDef)
        and any("loop" in ast.unparse(d) for d in n.decorator_list)
    ]
    assert loops
    scanners = ("_async_signal_scan", "_sync_swing_scan", "_sync_breakout_scan",
                "_sync_momentum_scan", "_sync_signal_scan")
    ungated = []
    for fn in loops:
        names = {x.id for x in ast.walk(fn) if isinstance(x, ast.Name)}
        if names & set(scanners) and "filter_validated" not in names:
            ungated.append(fn.name)
    assert ungated == []
