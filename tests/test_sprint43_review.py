"""
Sprint 43 — Institutional Review Implementation

Tests: truth sync, security hardening, calibrated confidence,
action ladder, portfolio heat, shadow tracking, contradiction,
trust strip, feature staging.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ──────────────────────────────────────────────────────────────
# 1. Truth Sync — version, counts, naming
# ──────────────────────────────────────────────────────────────

class TestTruthSync:
    def test_version_source_of_truth(self):
        from src.core.version import (
            APP_VERSION,
            DISCORD_COMMAND_COUNT,
            DOCKER_SERVICE_COUNT,
            PRODUCT_NAME,
            STRATEGY_COUNT,
        )

        assert APP_VERSION == "9.0.0"
        assert PRODUCT_NAME == "CC"
        assert STRATEGY_COUNT == 4
        assert DISCORD_COMMAND_COUNT == 64
        assert DOCKER_SERVICE_COUNT == 9

    def test_readme_no_old_service_count(self):
        with open("README.md") as f:
            content = f.read()
        assert "11 services" not in content
        assert "9 services" in content

    def test_methodology_4_strategies(self):
        with open("docs/METHODOLOGY.md") as f:
            content = f.read()
        assert "4 registered strategies" in content
        assert "8 registered strategies" not in content

    def test_setup_guide_correct_repo(self):
        with open("docs/SETUP_GUIDE.md") as f:
            content = f.read()
        assert "cd Trading-bot-CC" in content
        assert "cd TradingAI_Bot-main" not in content

    def test_setup_guide_no_old_bot_name(self):
        with open("docs/SETUP_GUIDE.md") as f:
            content = f.read()
        assert "TradingAI Bot#8419" not in content

    def test_makefile_cc_name(self):
        with open("Makefile") as f:
            content = f.read()
        assert "CC" in content
        assert "TradingAI Bot v6" not in content


# ──────────────────────────────────────────────────────────────
# 2. Security Hardening
# ──────────────────────────────────────────────────────────────

class TestSecurityHardening:
    def test_docker_compose_no_admin_defaults(self):
        with open("docker-compose.yml") as f:
            content = f.read()
        # Grafana should not have admin fallback
        assert "GRAFANA_USER:-admin" not in content
        assert "GRAFANA_PASSWORD:-admin" not in content
        # pgAdmin should not have admin fallback
        assert "PGADMIN_EMAIL:-admin@tradingai.local" not in content
        assert "PGADMIN_PASSWORD:-admin" not in content
        # Jupyter should not have guessable token
        assert "JUPYTER_TOKEN:-tradingai" not in content

    def test_docker_compose_requires_env_vars(self):
        with open("docker-compose.yml") as f:
            content = f.read()
        assert "GRAFANA_USER:?" in content
        assert "GRAFANA_PASSWORD:?" in content
        assert "PGADMIN_EMAIL:?" in content
        assert "PGADMIN_PASSWORD:?" in content
        assert "JUPYTER_TOKEN:?" in content

    def test_cors_no_wildcard(self):
        with open("src/api/main.py") as f:
            content = f.read()
        # The old wildcard CORS pattern should be gone
        assert 'allow_origins=["*"]' not in content.replace(" ", "")
        assert "explicit origins only" in content


# ──────────────────────────────────────────────────────────────
# 3. Enrichment Helpers — calibration, action state, etc.
# ──────────────────────────────────────────────────────────────

class TestEnrichmentHelpers:
    @pytest.fixture(autouse=True)
    def setup_path(self):
        """Ensure we can import from src.api.main."""
        pass

    def _import_helpers(self):
        """Import the enrichment helpers from main.py."""
        from src.api.main import (
            _build_pre_mortem,
            _build_reasons_against,
            _build_reasons_for,
            _build_why_wait,
            _compute_action_state,
            _enrich_calibration,
        )

        return (
            _enrich_calibration, _compute_action_state,
            _build_reasons_for, _build_reasons_against,
            _build_pre_mortem, _build_why_wait,
        )

    def test_enrich_calibration_shape(self):
        _enrich_calibration, *_ = self._import_helpers()
        conf = {
            "composite": 72,
            "calibration": {
                "predicted_prob": 0.72,
                "confidence_bucket": "high",
            },
            "data": {"score": 80},
            "execution": {"score": 75},
        }
        result = _enrich_calibration(conf, "momentum")
        assert "forecast_probability" in result
        assert "uncertainty_band" in result
        assert "display_recommendation" in result
        assert result["historical_reliability_bucket"] == "high"
        assert result["uncertainty_band"]["low"] == 60
        assert result["uncertainty_band"]["high"] == 84

    def test_compute_action_state(self):
        _, _compute_action_state, *_ = self._import_helpers()
        conf = {
            "decision_tier": "STRONG_BUY",
            "sizing": "Full position (5% of portfolio)",
            "should_trade": True,
            "abstain_reason": None,
        }
        result = _compute_action_state(conf, 3.0, True)
        assert result["action"] == "STRONG_BUY"
        assert result["should_trade"] is True
        assert "✅" in result["display"]

    def test_action_state_no_trade(self):
        _, _compute_action_state, *_ = self._import_helpers()
        conf = {
            "decision_tier": "NO_TRADE",
            "sizing": "Abstain",
            "should_trade": False,
            "abstain_reason": "Confidence too low",
        }
        result = _compute_action_state(conf, 1.2, False)
        assert result["action"] == "NO_TRADE"
        assert result["should_trade"] is False
        assert "⏸️" in result["display"]

    def test_build_pre_mortem(self):
        *_, _build_pre_mortem, _ = self._import_helpers()
        result = _build_pre_mortem("momentum", True)
        assert len(result) > 10
        assert "stall" in result.lower() or "reverse" in result.lower()

    def test_build_why_wait_low_confidence(self):
        *_, _build_why_wait = self._import_helpers()
        conf = {"composite": 45, "timing": {"score": 40}}
        result = _build_why_wait(conf, 1.5)
        assert result is not None
        assert "wait" in result.lower()

    def test_build_why_wait_high_confidence(self):
        *_, _build_why_wait = self._import_helpers()
        conf = {"composite": 80, "timing": {"score": 70}}
        result = _build_why_wait(conf, 3.0)
        assert result is None  # No reason to wait


# ──────────────────────────────────────────────────────────────
# 4. Trust Strip & Feature Staging
# ──────────────────────────────────────────────────────────────

class TestTrustStrip:
    def test_trust_strip_in_recommendations_endpoint(self):
        """Verify trust_strip and portfolio_heat keys exist in recommendation response schema."""
        with open("src/api/main.py") as f:
            content = f.read()
        assert '"trust_strip"' in content
        assert '"feature_stage"' in content
        assert '"portfolio_heat"' in content
        assert '"assumptions"' in content
        assert "gross returns" in content

    def test_signal_enrichment_keys(self):
        """Verify every signal has calibration, action_state, trust_strip, contradiction fields."""
        with open("src/api/main.py") as f:
            content = f.read()
        required_keys = [
            '"calibrated_confidence"',
            '"action_state"',
            '"trust_strip"',
            '"reasons_for"',
            '"reasons_against"',
            '"invalidation"',
            '"pre_mortem"',
            '"why_wait"',
        ]
        for key in required_keys:
            assert key in content, f"Missing {key} in signal output"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
