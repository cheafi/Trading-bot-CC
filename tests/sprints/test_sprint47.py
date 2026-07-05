"""Sprint 47 tests."""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))

def test_meta_ensemble_import():
    from src.engines.meta_ensemble import MetaEnsemble
    me = MetaEnsemble()
    assert me.sample_count == 0
    assert not me.is_trained

def test_meta_ensemble_record():
    from src.engines.meta_ensemble import MetaEnsemble
    me = MetaEnsemble()
    me.record_outcome(components={"net_expectancy": 0.5}, pnl_pct=2.5,
                      r_multiple=1.2, regime_label="bull", strategy_id="m")
    assert me.sample_count == 1

def test_meta_ensemble_state():
    from src.engines.meta_ensemble import MetaEnsemble
    me = MetaEnsemble()
    d = me.get_state().to_dict()
    assert "n_samples" in d and "weights" in d

def test_trust_badge():
    from src.core.trust_metadata import TrustBadge, TrustMetadata
    meta = TrustMetadata.for_entry(badge=TrustBadge.PAPER, source_count=3)
    assert meta.to_dict()["badge"] == "PAPER"

def test_trust_header():
    from src.core.trust_metadata import TrustBadge, TrustMetadata
    meta = TrustMetadata.for_entry(badge=TrustBadge.PAPER, source_count=3)
    assert len(meta.header_line()) > 0

def test_freshness():
    from src.core.trust_metadata import FreshnessLevel
    assert FreshnessLevel.FRESH.value == "FRESH"

def test_pnl_breakdown():
    from src.core.trust_metadata import PnLBreakdown
    pnl = PnLBreakdown.from_trade(gross_pnl_pct=10.0, fees_pct=0.1,
                                   slippage_pct=0.05)
    assert pnl.to_dict()["gross_pnl_pct"] == 10.0

def test_meta_ensemble_endpoint():
    from src.api.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/v6/meta-ensemble" in routes

def test_trust_card_endpoint():
    from src.api.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/v6/trust-card/{ticker}" in routes

def test_model_version_endpoint():
    from src.api.main import app
    routes = [r.path for r in app.routes if hasattr(r, "path")]
    assert "/api/v6/model-version" in routes

def test_discord_swing():
    from src.notifications.discord_bot import _register_swing_commands
    assert callable(_register_swing_commands)

def test_model_version():
    from src.core.trust_metadata import MODEL_VERSION
    assert MODEL_VERSION.startswith("v")
