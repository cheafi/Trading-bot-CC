"""Instant server must show brief stocks when :8001 is down."""

from __future__ import annotations

import json

from _cc_instant import (
    _brief_fallback_ranked_rows,
    _ranked_payload_has_names,
    _stale_ranked_bytes,
    _stale_today_bytes,
)


def test_brief_fallback_ranked_has_tickers():
    rows = _brief_fallback_ranked_rows(limit=10)
    assert len(rows) >= 1
    assert rows[0].get("ticker")
    assert rows[0].get("action") == "WATCH"


def test_stale_ranked_bytes_not_empty():
    body = _stale_ranked_bytes("backend importing — test")
    payload = json.loads(body)
    assert _ranked_payload_has_names(payload)
    assert payload.get("count", 0) >= 1


def test_stale_today_bytes_has_top5():
    payload = json.loads(_stale_today_bytes("backend importing — test"))
    assert len(payload.get("top_5") or []) >= 1
