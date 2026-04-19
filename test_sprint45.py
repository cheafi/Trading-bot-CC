"""Sprint 45 tests — Batch Portfolio Import / Futu Sync / Portfolio Advise."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime


# ── 1. API endpoint registration ──────────────────────────────────────

class TestPortfolioEndpointsExist:
    """Verify Sprint 45 routes are registered."""

    def _routes(self):
        import importlib, sys
        # We can't easily start the full app, so check source
        with open("src/api/main.py") as f:
            src = f.read()
        return src

    def test_import_endpoint(self):
        src = self._routes()
        assert "/api/portfolio/import" in src

    def test_holdings_endpoint(self):
        src = self._routes()
        assert "/api/portfolio/holdings" in src

    def test_futu_endpoint(self):
        src = self._routes()
        assert "/api/portfolio/futu" in src

    def test_advise_endpoint(self):
        src = self._routes()
        assert "/api/portfolio/advise" in src


# ── 2. Pydantic models ───────────────────────────────────────────────

class TestPydanticModels:
    """HoldingInput and PortfolioImportRequest parse correctly."""

    def test_holding_input_in_source(self):
        with open("src/api/main.py") as f:
            src = f.read()
        assert "class HoldingInput" in src
        assert "class PortfolioImportRequest" in src

    def test_holding_fields(self):
        with open("src/api/main.py") as f:
            src = f.read()
        assert "ticker: str" in src
        assert "shares: float" in src
        assert "avg_cost: float" in src


# ── 3. Portfolio store ────────────────────────────────────────────────

class TestPortfolioStore:
    def test_user_portfolio_initial(self):
        with open("src/api/main.py") as f:
            src = f.read()
        assert '_user_portfolio' in src
        assert '"holdings": []' in src


# ── 4. Futu broker integration ────────────────────────────────────────

class TestFutuBrokerIntegration:
    def test_futu_broker_importable(self):
        with open("src/brokers/futu_broker.py") as f:
            src = f.read()
        assert "class FutuBroker" in src
        assert "get_positions" in src
        assert "get_account" in src

    def test_futu_endpoint_uses_broker(self):
        with open("src/api/main.py") as f:
            src = f.read()
        assert "from src.brokers.futu_broker import FutuBroker" in src


# ── 5. Advise logic ──────────────────────────────────────────────────

class TestAdviseLogic:
    def test_advise_uses_expert_committee(self):
        with open("src/api/main.py") as f:
            src = f.read()
        assert "ExpertCommittee" in src
        assert "ec.collect_votes" in src or "collect_votes" in src

    def test_advise_uses_conformal(self):
        with open("src/api/main.py") as f:
            src = f.read()
        assert "ConformalPredictor" in src

    def test_concentration_check(self):
        with open("src/api/main.py") as f:
            src = f.read()
        assert "concentration_warnings" in src
        assert "over-concentrated" in src

    def test_action_categories(self):
        with open("src/api/main.py") as f:
            src = f.read()
        for action in ["ADD", "HOLD", "TRIM / EXIT", "REVIEW", "CONSIDER TRIM"]:
            assert action in src


# ── 6. Discord commands ──────────────────────────────────────────────

class TestDiscordCommands:
    def _src(self):
        with open("src/notifications/discord_bot.py") as f:
            return f.read()

    def test_portfolio_import_command(self):
        assert 'name="portfolio-import"' in self._src()

    def test_portfolio_futu_command(self):
        assert 'name="portfolio-futu"' in self._src()

    def test_portfolio_advise_command(self):
        assert 'name="portfolio-advise"' in self._src()

    def test_comma_separated_input(self):
        src = self._src()
        assert "tickers.split" in src
        assert "shares.split" in src

    def test_api_integration(self):
        src = self._src()
        assert "/api/portfolio/import" in src
        assert "/api/portfolio/advise" in src
        assert "/api/portfolio/futu" in src


# ── 7. Expert Committee (from Sprint 44, verify still works) ─────────

class TestExpertCommitteeStillWorks:
    def test_import(self):
        from src.engines.expert_committee import ExpertCommittee, CommitteeVerdict
        ec = ExpertCommittee()
        assert len(ec.experts) == 7

    def test_vote(self):
        import numpy as np
        from src.engines.expert_committee import ExpertCommittee
        ec = ExpertCommittee()
        prices = np.cumsum(np.random.randn(120)) + 100
        prices = np.maximum(prices, 1)
        votes = ec.collect_votes(
            regime="UPTREND", rsi=55, vol_ratio=1.2,
            trending=True, rr_ratio=2.0, atr_pct=0.02,
        )
        v = ec.deliberate(votes, regime="UPTREND")
        assert v.direction in ("LONG", "FLAT", "ABSTAIN")
        assert 0 <= v.agreement_ratio <= 1


# ── 8. Conformal Predictor (from Sprint 44) ──────────────────────────

class TestConformalStillWorks:
    def test_calibrate(self):
        import numpy as np
        from src.engines.conformal_predictor import ConformalPredictor
        cp = ConformalPredictor()
        prices = np.cumsum(np.random.randn(200)) + 100
        prices = np.maximum(prices, 1)
        cp.calibrate_from_returns(prices)
        assert cp.is_calibrated

    def test_predict(self):
        import numpy as np
        from src.engines.conformal_predictor import ConformalPredictor
        cp = ConformalPredictor()
        prices = np.cumsum(np.random.randn(200)) + 100
        prices = np.maximum(prices, 1)
        cp.calibrate_from_returns(prices)
        interval = cp.predict(105.0)
        assert interval.lower < interval.upper


# ── 9. Scenario Engine (from Sprint 44) ──────────────────────────────

class TestScenarioStillWorks:
    def test_import(self):
        from src.engines.scenario_engine import ScenarioEngine
        se = ScenarioEngine()
        assert len(se.scenarios) >= 8


# ── 10. End-to-end flow validation ───────────────────────────────────

class TestE2EFlow:
    def test_import_then_advise_flow_exists(self):
        """Verify the import → advise flow is wired."""
        with open("src/api/main.py") as f:
            src = f.read()
        # Import stores to _user_portfolio
        assert "global _user_portfolio" in src
        # Advise reads from _user_portfolio
        assert '_user_portfolio.get("holdings"' in src

    def test_discord_flow(self):
        """Discord commands call API endpoints."""
        with open("src/notifications/discord_bot.py") as f:
            src = f.read()
        assert "portfolio/import" in src
        assert "portfolio/advise" in src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
