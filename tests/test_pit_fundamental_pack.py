"""PIT fundamental research context."""

from __future__ import annotations

from src.services.pit_fundamental_pack import build_pit_fundamental_context


def test_pit_fundamental_requires_as_of() -> None:
    row = build_pit_fundamental_context(["SPY"], as_of=None)
    assert row.get("applied") is False


def test_pit_fundamental_with_as_of(monkeypatch) -> None:
    def _fake_snapshot(symbol: str, _as_of_dt):
        return {"source": "test", "trailing_pe": 20.0, "symbol": symbol}

    monkeypatch.setattr(
        "src.services.pit_fundamental_pack._yf_fundamental_snapshot",
        _fake_snapshot,
    )
    row = build_pit_fundamental_context(["SPY", "QQQ"], as_of="2024-06-01")
    assert row.get("applied") is True
    assert row.get("as_of") == "2024-06-01"
    assert len(row.get("rows") or []) == 2
    assert row["rows"][0].get("fundamentals", {}).get("source") == "test"
