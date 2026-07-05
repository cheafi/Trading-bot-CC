"""Strategy validity — decay and overfit flags."""

from src.services.strategy_validity import (
    FLAG_OVERFIT,
    build_strategy_validity_context,
    evaluate_validity_flags,
)


def test_overfit_flag():
    v = evaluate_validity_flags(
        in_sample_sharpe=2.0,
        oos_sharpe=0.1,
        oos_trades=30,
        param_count=12,
        n_trades=40,
    )
    assert FLAG_OVERFIT in v["flags"]
    assert v["live_edge_claim"] is False


def test_context_deploy_blocked():
    ctx = build_strategy_validity_context()
    assert ctx["validity"]["deploy_from_validity_alone"] is False
