"""13F CUSIP → ticker resolution."""

from __future__ import annotations

from src.services.filing_13f_cusip import resolve_ticker_from_cusip


def test_cusip_map_msft() -> None:
    assert resolve_ticker_from_cusip("594918104") == "MSFT"


def test_cusip_unknown_issuer_hint() -> None:
    assert resolve_ticker_from_cusip("", issuer="NVIDIA CORP") == "NVIDIA"
    assert resolve_ticker_from_cusip("037833100") == "AAPL"
