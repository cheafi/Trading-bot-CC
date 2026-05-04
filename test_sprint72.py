"""Sprint 72 — Watchlist Decision Board + Symbol Dossier + Command-K search."""

from __future__ import annotations

import pytest


class TestWatchlistRoutes:
    def test_router_importable(self):
        from src.api.routers.watchlist import router
        paths = [r.path for r in router.routes]
        assert "/api/watchlist" in paths
        assert "/api/watchlist/search" in paths
        assert "/api/watchlist/{ticker}" in paths

    def test_search_empty_returns_popular(self):
        import asyncio
        from src.api.routers.watchlist import watchlist_search
        result = asyncio.run(watchlist_search(q="", limit=10))
        assert result["popular_fallback"] is True
        assert result["count"] > 0
        assert "results" in result

    def test_search_with_query(self):
        import asyncio
        from src.api.routers.watchlist import watchlist_search
        result = asyncio.run(watchlist_search(q="NVDA", limit=5))
        assert "results" in result
        assert result["query"] == "NVDA"

    def test_ticker_card_structure(self):
        import asyncio
        from src.api.routers.watchlist import watchlist_ticker
        card = asyncio.run(watchlist_ticker("AAPL"))
        assert "ticker" in card
        assert card["ticker"] == "AAPL"
        assert "action" in card
        assert card["action"] in ("TRADE", "LEADER", "WATCH", "WAIT", "NO_TRADE")
        assert "regime" in card
        assert "gate" in card["regime"]

    def test_board_returns_list(self):
        import asyncio
        from src.api.routers.watchlist import watchlist_board
        result = asyncio.run(watchlist_board(limit=20, action=None))
        assert "board" in result
        assert "regime" in result
        assert isinstance(result["board"], list)


class TestDossierRoutes:
    def test_router_importable(self):
        from src.api.routers.dossier import router
        paths = [r.path for r in router.routes]
        assert "/api/dossier/{ticker}" in paths

    def test_dossier_structure(self):
        import asyncio
        from src.api.routers.dossier import symbol_dossier
        dossier = asyncio.run(symbol_dossier("AAPL"))
        assert dossier["ticker"] == "AAPL"
        assert "decision" in dossier
        assert "confidence" in dossier
        assert "regime" in dossier
        assert "risk" in dossier
        assert "benchmark" in dossier
        assert "similar_cases" in dossier
        assert "disclaimer" in dossier

    def test_decision_fields(self):
        import asyncio
        from src.api.routers.dossier import symbol_dossier
        d = asyncio.run(symbol_dossier("MSFT"))
        decision = d["decision"]
        assert "action" in decision
        assert decision["action"] in ("TRADE", "LEADER", "WATCH", "WAIT", "NO_TRADE")
        assert "conviction_tier" in decision
        assert "regime_gate" in decision
        assert decision["regime_gate"] in ("ALLOWED", "BLOCKED")

    def test_confidence_breakdown(self):
        import asyncio
        from src.api.routers.dossier import symbol_dossier
        d = asyncio.run(symbol_dossier("NVDA"))
        conf = d["confidence"]
        for key in ("thesis", "timing", "execution", "data", "overall"):
            assert key in conf
            assert 0 <= conf[key] <= 100

    def test_dossier_cache(self):
        import asyncio
        from src.api.routers.dossier import symbol_dossier, _DOSSIER_CACHE
        asyncio.run(symbol_dossier("TSLA"))
        assert "TSLA" in _DOSSIER_CACHE

    def test_invalid_ticker_returns_wait(self):
        import asyncio
        from src.api.routers.dossier import symbol_dossier
        d = asyncio.run(symbol_dossier("XYZXYZXYZ"))
        # Unknown ticker should return WAIT action (no match in brief)
        assert d["decision"]["action"] in ("WAIT", "NO_TRADE")


class TestMainRouterRegistration:
    def test_watchlist_registered(self):
        from src.api.routers.watchlist import router
        assert any("/api/watchlist" in r.path for r in router.routes)

    def test_dossier_registered(self):
        from src.api.routers.dossier import router
        assert any("/api/dossier" in r.path for r in router.routes)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
