"""
Sprint 42 — System Architecture: discord module decomposition,
engine interfaces, CI/CD pipeline, Render deployment.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))


class TestDiscordModuleStructure:
    def test_constants_import(self):
        from src.notifications._constants import (
            COLOR_GREEN, SERVER_LAYOUT, DEFAULT_WATCHLIST,
            SECTOR_ETFS, MACRO_TICKERS, ACTION_EMOJI,
        )
        assert COLOR_GREEN == 0x00FF88
        assert len(DEFAULT_WATCHLIST) == 30
        assert "Technology" in SECTOR_ETFS
        assert "S&P 500" in MACRO_TICKERS
        assert "STRONG_BUY" in ACTION_EMOJI

    def test_embeds_import(self):
        from src.notifications._embeds import (
            DiscordEmbed, EmbedPaginator,
        )
        e = DiscordEmbed(title="Test", color=0xFF0000)
        e.add_field("key", "value", inline=True)
        e.set_footer("footer")
        d = e.to_dict()
        assert d["title"] == "Test"
        assert len(d["fields"]) == 1

    def test_paginator(self):
        from src.notifications._embeds import EmbedPaginator
        p = EmbedPaginator("Test")
        for i in range(100):
            p.add_line(f"Line {i}: " + "x" * 50)
        pages = p.build()
        assert len(pages) >= 1
        assert all(
            len(pg.description) <= 4001 for pg in pages
        )

    def test_helpers_import(self):
        from src.notifications._helpers import (
            format_price, format_change, format_volume,
            format_market_cap, truncate, regime_emoji,
            confidence_bar, utcnow_iso,
        )
        assert format_price(150.5) == "$150.50"
        assert format_price(0.0045) == "$0.0045"
        assert "%" in format_change(2.5)
        assert "M" in format_volume(1_500_000)
        assert "B" in format_market_cap(5e9)
        assert truncate("x" * 2000, 100) == "x" * 97 + "..."
        assert regime_emoji("bull") == "\U0001f7e2"
        assert "%" in confidence_bar(75)
        assert "T" in utcnow_iso()

    def test_cogs_package(self):
        import src.notifications.cogs
        assert src.notifications.cogs is not None

    def test_tasks_package(self):
        import src.notifications.tasks
        assert src.notifications.tasks is not None


class TestEngineInterfaces:
    def test_import_all(self):
        from src.engines.interfaces import (
            AlphaEngine, AlphaSignal,
            PortfolioEngine, PortfolioTarget,
            RiskEngine, RiskVerdict,
            ExecutionEngine, OrderRequest, OrderResult,
            CalibrationInterface,
            MetaLabelInterface,
        )
        assert AlphaEngine is not None
        assert PortfolioEngine is not None
        assert RiskEngine is not None
        assert ExecutionEngine is not None

    def test_alpha_signal_dataclass(self):
        from src.engines.interfaces import AlphaSignal
        sig = AlphaSignal(
            ticker="AAPL", direction="LONG",
            score=85, confidence=0.8,
            strategy="momentum", regime="bull",
            evidence_for=["trend up"],
            evidence_against=["overbought"],
        )
        assert sig.ticker == "AAPL"
        assert sig.score == 85

    def test_risk_verdict_defaults(self):
        from src.engines.interfaces import RiskVerdict
        v = RiskVerdict(approved=True)
        assert v.vetoes == []
        assert v.warnings == []
        assert v.size_multiplier == 1.0

    def test_order_request(self):
        from src.engines.interfaces import OrderRequest
        o = OrderRequest(
            ticker="AAPL", direction="BUY",
            quantity=100,
        )
        assert o.order_type == "market"
        assert o.time_in_force == "day"


class TestCIConfig:
    def test_ci_yml_exists(self):
        path = ".github/workflows/ci.yml"
        assert os.path.exists(path)

    def test_ci_has_lint_test_docker(self):
        with open(".github/workflows/ci.yml") as f:
            content = f.read()
        assert "lint:" in content
        assert "test:" in content
        assert "docker:" in content
        assert "black" in content.lower()
        assert "ruff" in content.lower()
        assert "pytest" in content.lower()


class TestRenderConfig:
    def test_render_yaml_exists(self):
        assert os.path.exists("render.yaml")

    def test_render_has_services(self):
        with open("render.yaml") as f:
            content = f.read()
        assert "cc-dashboard" in content
        assert "cc-discord-bot" in content
        assert "healthCheckPath" in content
        assert "API_SECRET" in content
        assert "CORS_ORIGINS" in content
        assert "cc-db" in content
        assert "cc-redis" in content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
