"""Dossier fetch-failed UX — research-specific copy and template wiring."""

from __future__ import annotations

from pathlib import Path

from src.services.fetch_surface_state import (
    DOSSIER_SERVICE_DEFAULT,
    STATE_FAILED_FETCH,
    STATE_LOADING,
    STATE_PARTIAL,
    STATE_STALE,
    describe_dossier_fetch_state,
)
from src.services.surface_authority import build_header_summary

ROOT = Path(__file__).resolve().parents[1]
INDEX_HTML = ROOT / "src" / "api" / "templates" / "index.html"


def test_describe_dossier_fetch_failed_copy():
    copy = describe_dossier_fetch_state(STATE_FAILED_FETCH)
    assert copy["title"] == "Research unavailable"
    assert DOSSIER_SERVICE_DEFAULT in copy["explanation"]
    assert "Live dossier fetch failed" in copy["explanation"]
    assert copy["next_action"] == "This page is not decision-grade until research loads"
    assert copy["badge"] == "RESEARCH UNAVAILABLE"


def test_describe_dossier_fetch_failed_includes_service_and_detail():
    copy = describe_dossier_fetch_state(
        STATE_FAILED_FETCH,
        detail="HTTP 503",
        service="market_data_service",
    )
    assert "market_data_service" in copy["explanation"]
    assert "HTTP 503" in copy["explanation"]


def test_describe_dossier_loading_and_stale_copy():
    loading = describe_dossier_fetch_state(STATE_LOADING)
    assert loading["badge"] == "LOADING"
    assert "market_data_service" in loading["explanation"]

    stale = describe_dossier_fetch_state(STATE_STALE, service="cached_intel")
    assert stale["badge"] == "STALE"
    assert "cached_intel" in stale["explanation"]


def test_build_header_summary_dossier_failed_fetch():
    summary = build_header_summary(
        "dossier_research",
        {
            "error": "upstream timeout",
            "fetch_detail": "HTTP 503",
            "ticker": "JPM",
        },
    )
    assert summary["fetch_state"] == STATE_FAILED_FETCH
    assert summary["badge"] == "RESEARCH UNAVAILABLE"
    assert "Live dossier fetch failed" in summary["explanation"]
    assert summary["next_action"] == "This page is not decision-grade until research loads"
    assert any(chip["label"] == "JPM" for chip in summary["chips"])


def test_index_html_dossier_fetch_helpers_and_copy():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "dosFetchErrorHeadline" in text
    assert "dosFetchErrorDetail" in text
    assert "dosFetchErrorGrade" in text
    assert "dossierFetchStateCopy" in text
    assert "_syncDossierFetchHints" in text
    assert "Research unavailable" in text
    assert "This page is not decision-grade until research loads" in text
    assert "Load core only — quote, basic technicals, and cached structure" in text
    assert "skips extended research panels" in text


def test_index_html_error_banner_does_not_repeat_ticker():
    text = INDEX_HTML.read_text(encoding="utf-8")
    start = text.index('x-show="dosShowsFetchBanner()"')
    end = text.index("</main>", start)
    banner = text[start:end]
    assert "x-text=\"dos.ticker\"" not in banner
    assert "dosFetchBannerHeadline()" in banner
    assert "dosFetchBannerDetail()" in banner


def test_describe_dossier_partial_instant_degraded_copy():
    copy = describe_dossier_fetch_state(
        STATE_PARTIAL,
        detail="brief-backed core",
        service="instant-degraded",
    )
    assert copy["badge"] == "RESEARCH ONLY"
    assert "instant-degraded" in copy["explanation"]
    assert "fetch failed" not in copy["explanation"].lower()
    assert "IBKR" in copy["next_action"]


def test_index_html_dossier_partial_banner_helpers():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "dosShowsFetchBanner" in text
    assert "dosFetchBannerKind" in text
    assert "partialNotice" in text
    assert "_dossierIntelDegraded" in text
    assert "dosFetchBannerHeadline" in text


def test_index_html_surface_fetch_error_line_handles_dossier():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "mode==='dossier_research'" in text
    assert "Live dossier fetch failed from" in text
    assert "levels not live-confirmed" in text
    assert "Live evidence" in text
    assert "board-ranked score" in text


def test_index_html_dossier_sizing_gated_when_research_only():
    text = INDEX_HTML.read_text(encoding="utf-8")
    assert "dossierSizingBlocked()" in text
    assert "dosSizeDisplay()" in text
    assert "dossierSizingBlockedReason()" in text
    assert "No sizing guidance in confirm-only mode" in text
    assert "dosSizeExplanationVisible()" in text
    assert "dosPriceDisplay()" in text
    assert "Sizing blocked until live dossier loads" in text
    # Trade plan table must not render raw share counts unconditionally
    trade_plan = text[text.find("Trade plan") : text.find("Trade plan") + 2500]
    assert "dosSizeDisplay()" in trade_plan
    assert "dosSizeShares()+' sh'" not in trade_plan
