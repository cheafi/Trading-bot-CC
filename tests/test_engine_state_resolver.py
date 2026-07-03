"""Engine state resolver — never ON+OFF together."""

from __future__ import annotations

from src.services.authority_engine import resolve_engine_state
from src.services.system_truth import resolve_system_truth


def test_system_truth_engine_unknown_on_conflict():
    truth = resolve_system_truth(
        {
            "market_regime": {"tradeability": "WAIT", "should_trade": True},
            "execution_readiness": {"engine_running": True},
        },
        cc_header={},
        ops_console={"engine_running": False},
    )
    assert truth["engine_state"] == "unknown"
    assert truth["engine_state_display"] == "Unknown"


def test_resolve_engine_state_no_dual_on_off_labels():
    labels = set()
    for er, ops in (
        (True, True),
        (False, False),
        (True, False),
        (False, True),
        (None, None),
    ):
        state = resolve_engine_state(
            {"execution_readiness": {"engine_running": er}} if er is not None else {},
            {"engine_running": ops} if ops is not None else {},
        )
        labels.add(state)
    assert "on" in labels
    assert "off" in labels
    assert "unknown" in labels
    assert not ("on" in labels and "off" in labels and len(labels) == 2)
