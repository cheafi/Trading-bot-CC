"""CC performance cache helpers — fingerprint stability and ETag."""

from __future__ import annotations

from pathlib import Path

from src.services.cc_perf_cache import payload_etag

ROOT = Path(__file__).resolve().parents[1]
DECISION_SRC = (ROOT / "src/api/routers/decision.py").read_text(encoding="utf-8")
CC_HEADER_SRC = (ROOT / "src/api/routers/cc_header.py").read_text(encoding="utf-8")
PERF_CACHE_SRC = (ROOT / "src/services/cc_perf_cache.py").read_text(encoding="utf-8")


def test_payload_etag_changes_with_generated_at():
    a = payload_etag({"generated_at": "2026-01-01T00:00:00Z", "trust": {}})
    b = payload_etag({"generated_at": "2026-01-02T00:00:00Z", "trust": {}})
    assert a != b
    assert a.startswith('W/"')


def test_today_endpoint_uses_fingerprint_and_cache_headers():
    assert "today_cache_fingerprint" in DECISION_SRC
    assert "json_cache_response" in DECISION_SRC
    assert "_today_cache_fp" in DECISION_SRC
    assert "CC_INSTANT_TODAY_TTL" in DECISION_SRC
    assert "_instant_today_ttl" in DECISION_SRC


def test_cc_header_uses_response_cache():
    assert "cc_header_cache" in CC_HEADER_SRC
    assert "json_cache_response" in CC_HEADER_SRC


def test_scanner_hub_uses_scan_cache_ttl():
    playbook_src = (ROOT / "src/api/routers/playbook.py").read_text(encoding="utf-8")
    assert "CC_SCAN_CACHE_TTL" in playbook_src
    assert "_scanner_hub_cache" in playbook_src
    assert "_scan_rec_to_signal" in playbook_src
    assert "live_scanner" in playbook_src


def test_today_cache_fingerprint_composes_scan_brief_ibkr_engine():
    """Contract: fingerprint includes scanner, brief, broker, engine segments."""
    assert "scan_cache.get('ts'" in PERF_CACHE_SRC
    assert "_latest_brief" in PERF_CACHE_SRC
    assert "get_ibkr_service" in PERF_CACHE_SRC
    assert "get_engine" in PERF_CACHE_SRC


def test_cc_perf_cache_documents_scan_env():
    assert "CC_SCAN_CACHE_TTL" in PERF_CACHE_SRC
    assert "CC_SCAN_UNIVERSE_MODE" in PERF_CACHE_SRC
