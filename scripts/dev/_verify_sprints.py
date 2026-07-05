from src.services.fund_persistence import save_engine_state, load_engine_state
from src.engines.calibration_engine import CalibrationEngine

e = CalibrationEngine()
e.record_outcome(0.72, True, "bull", "momentum")
e.save()
e2 = CalibrationEngine()
assert e2.load()
print("CalibrationEngine save/load OK")

from src.engines.strategy_optimizer import STRATEGY_REGISTRY

assert len(STRATEGY_REGISTRY["SWING"]["param_grid"]["stop_atr"]) >= 6
assert len(STRATEGY_REGISTRY["BREAKOUT"]["param_grid"]["lookback"]) >= 5
print("PARAM_GRID expanded OK")

from src.engines.expert_council import FundamentalExpert, SectorBucket
from unittest.mock import MagicMock

fe = FundamentalExpert()
sector = MagicMock()
sector.sector_bucket = SectorBucket.HIGH_GROWTH
sig = {
    "risk_reward": 3.5,
    "score": 7.5,
    "fundamentals": {"trailingPE": 22, "profitMargins": 0.20},
}
vote = fe.vote(sig, sector, {"should_trade": True})
assert vote is not None
print("FundamentalExpert real data wired OK")

from src.services.fund_lab_service import FundLabService

for name, spec in FundLabService.FUND_UNIVERSES.items():
    assert "style" in spec and "regime_gates" in spec["style"]
print("Fund style configs OK")

from src.api.routers.fund_portfolio import router

assert router.prefix == "/api/v7/funds"
print("fund_portfolio router OK")

from src.services.fund_config_tuner import get_fund_config_tuner

tuner = get_fund_config_tuner()
cand = tuner.propose("FUND_ALPHA", {"top_n": 6})
assert cand["top_n"] == 6
print("FundConfigTuner OK")

print("\nALL SPRINTS 92-95 VERIFIED")
