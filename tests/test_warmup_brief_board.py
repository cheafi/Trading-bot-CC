"""Warmup brief-board endpoint on instant server."""

from __future__ import annotations

import json

from _cc_instant import _brief_fallback_ranked_rows, _encode_degraded, _finalize_degraded_ranked


def test_warmup_brief_board_payload():
    rows = _brief_fallback_ranked_rows(limit=5)
    assert len(rows) >= 1
    payload = _finalize_degraded_ranked(
        {
            "count": len(rows),
            "opportunities": rows,
            "source": "brief-fallback",
        }
    )
    assert payload.get("count", 0) >= 1
