"""Dashboard export allow-list — sentinel secrets must not appear."""

from __future__ import annotations

from src.services.dashboard_export import (
    build_dashboard_export_view,
    export_contains_secret,
)

_SENTINEL_API_KEY = "SENTINEL_DO_NOT_EXPORT_api_key_9f3c"
_SENTINEL_TOKEN = "SENTINEL_DO_NOT_EXPORT_bearer_token_abc"


def test_export_allowlist_strips_secrets() -> None:
    source = {
        "as_of": "2026-09-16T00:00:00Z",
        "api_key": _SENTINEL_API_KEY,
        "discord_bot_token": _SENTINEL_TOKEN,
        "system_state": {
            "regime": "SELECTIVE",
            "tradeability": "SELECTIVE",
            "deploy_open": False,
            "secret_credential": "hidden",
        },
        "records": [
            {
                "ticker": "AAPL",
                "action": "WATCH",
                "api_key": _SENTINEL_API_KEY,
            }
        ],
        "unlisted_noise": {"password": "must-not-export"},
    }

    exported = build_dashboard_export_view(source)
    blob = str(exported)

    assert _SENTINEL_API_KEY not in blob
    assert _SENTINEL_TOKEN not in blob
    assert "password" not in blob
    assert exported["system_state"]["regime"] == "SELECTIVE"
    assert exported["records"][0]["ticker"] == "AAPL"
    assert export_contains_secret(exported) is None
