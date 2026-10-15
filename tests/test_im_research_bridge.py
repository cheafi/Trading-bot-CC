"""IM research bridge — channel routing (no network)."""

from __future__ import annotations

import asyncio

from src.services.im_research_bridge import dispatch_research_to_im


def test_whatsapp_missing_config() -> None:
    out = asyncio.run(
        dispatch_research_to_im({"consensus": "WAIT"}, task="ask", channel="whatsapp")
    )
    assert out["ok"] is False
    assert out["channel"] == "whatsapp"
