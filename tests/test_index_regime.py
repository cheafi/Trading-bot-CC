"""Index regime intelligence — monitor-only authority boundaries."""

from src.services.index_regime import (
    POSTURE_NO_TRADE_PRESSURE,
    build_breadth_regime_block,
    build_index_regime_summary,
    build_vol_regime_block,
    resolve_index_posture,
)
from src.services.signal_provenance import (
    SIGNAL_INDEX_REGIME,
    may_authorize_deploy,
)


def test_index_regime_never_authorizes_deploy():
    summary = build_index_regime_summary(tradeability="TRADE", should_trade=True)
    assert summary["may_authorize_deploy"] is False
    assert summary["may_override_wait"] is False
    assert may_authorize_deploy(SIGNAL_INDEX_REGIME) is False
    assert summary["authority"] == "monitor_only"


def test_degraded_when_vix_missing():
    vol = build_vol_regime_block(vix=None, trend="UPTREND")
    assert vol["degraded"] is True
    summary = build_index_regime_summary(vix=None, breadth=None, cross_asset=None)
    assert summary["degraded"] is True
    assert "MOCK" in (summary.get("strip_line") or "").upper()


def test_breadth_block_participation_narrow():
    block = build_breadth_regime_block(breadth=35.0)
    assert block["participation"] == "narrow"
    assert block["degraded"] is False


def test_posture_no_trade_on_wait():
    posture = resolve_index_posture(
        should_trade=False,
        tradeability="WAIT",
        vix=18.0,
        breadth=55.0,
        trend="UPTREND",
    )
    assert posture == POSTURE_NO_TRADE_PRESSURE


def test_cross_asset_wired_when_present():
    cross = {"alignment": "confirmed", "assets": [{"symbol": "SPY", "stance": "confirm"}]}
    summary = build_index_regime_summary(
        vix=17.0,
        breadth=58.0,
        should_trade=True,
        tradeability="SELECTIVE",
        cross_asset=cross,
    )
    assert summary["cross_asset"]["alignment"] == "confirmed"
    assert summary.get("degraded") is False
