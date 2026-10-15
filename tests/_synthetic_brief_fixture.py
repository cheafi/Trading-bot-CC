"""Isolated brief dependency for tests; no checkout trading data or disk cache."""

import pytest

from src.services import brief_data_service


@pytest.fixture
def isolated_brief_dir(tmp_path, monkeypatch):
    """Use the real loader against a temporary directory with clean caches."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.setattr(brief_data_service, "_brief_dir", lambda: str(data_dir))
    monkeypatch.setattr(brief_data_service, "_BRIEF_CACHE", None)
    monkeypatch.setattr(brief_data_service, "_BRIEF_CACHE_TS", 0)
    monkeypatch.setattr(brief_data_service, "_BRIEF_CACHE_FAILED", False)
    monkeypatch.setattr(brief_data_service, "_BRIEF_LAST_WARNING_TS", 0)
    return data_dir
