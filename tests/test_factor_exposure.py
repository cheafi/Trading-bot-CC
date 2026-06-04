"""Factor exposure — crowding labels."""

from src.services.factor_exposure import (
    CROWDING_HIGH,
    build_factor_exposure,
    evaluate_crowding,
)


def test_high_crowding():
    assert evaluate_crowding(overlap_pct=60, sector_concentration_pct=20) == CROWDING_HIGH


def test_payload_no_deploy():
    p = build_factor_exposure("NVDA")
    assert p["may_authorize_deploy"] is False
    assert "crowding_label" in p
