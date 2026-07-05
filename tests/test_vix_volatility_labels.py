"""VIX volatility buckets — never crisis below 28."""

from __future__ import annotations

import pytest

from src.services.system_truth import classify_volatility_state


@pytest.mark.parametrize(
    "vix,expected",
    [
        (10, "low"),
        (13.9, "low"),
        (14, "normal"),
        (19.9, "normal"),
        (20, "elevated"),
        (27.9, "elevated"),
        (28, "stress"),
        (34.9, "stress"),
        (35, "crisis"),
        (50, "crisis"),
    ],
)
def test_vix_volatility_labels(vix, expected):
    assert classify_volatility_state(vix) == expected


def test_vix_below_28_never_crisis():
    for v in (10, 14, 20, 27, 27.99):
        assert classify_volatility_state(v) != "crisis"
