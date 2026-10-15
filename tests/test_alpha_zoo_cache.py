"""Alpha zoo disk cache."""

from __future__ import annotations

from src.services.alpha_zoo_cache import (
    cached_zoo_fresh,
    load_cached_zoo,
    save_cached_zoo,
)


def test_alpha_zoo_cache_roundtrip(tmp_path, monkeypatch) -> None:
    from src.services import alpha_zoo_cache as azc

    path = tmp_path / "zoo.json"
    monkeypatch.setattr(azc, "_CACHE", path)
    assert load_cached_zoo() is None
    save_cached_zoo({"ok": True, "computed_count": 10, "zoo_total": 478, "summary": {}})
    row = load_cached_zoo()
    assert row is not None
    assert row.get("computed_count") == 10
    assert row.get("cached_at")
    assert cached_zoo_fresh(max_age_sec=3600)


def test_cached_zoo_fresh_legacy_double_suffix(tmp_path, monkeypatch) -> None:
    """Older builds appended Z to an already offset-aware iso string."""
    import json
    from datetime import datetime, timezone

    from src.services import alpha_zoo_cache as azc

    path = tmp_path / "legacy.json"
    monkeypatch.setattr(azc, "_CACHE", path)
    legacy_ts = datetime.now(timezone.utc).isoformat() + "Z"
    path.write_text(
        json.dumps({"ok": True, "computed_count": 1, "cached_at": legacy_ts}),
        encoding="utf-8",
    )
    assert cached_zoo_fresh(max_age_sec=3600)
