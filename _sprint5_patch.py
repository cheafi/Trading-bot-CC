"""Sprint 5: Config integration + PositionManager wiring + learning loop."""
import ast

# ── PATCH 1: Add decision-layer config fields to TradingConfig ──
config_path = "src/core/config.py"
with open(config_path, "r") as f:
    cfg = f.read()

old_risk = """    # Signal filters
    min_confidence: int = Field(default=50, alias="MIN_CONFIDENCE")
    max_vix_for_trading: float = Field(default=40.0, alias="MAX_VIX_FOR_TRADING")"""

new_risk = """    # Signal filters
    min_confidence: int = Field(default=50, alias="MIN_CONFIDENCE")
    max_vix_for_trading: float = Field(default=40.0, alias="MAX_VIX_FOR_TRADING")

    # Regime router thresholds
    regime_vix_crisis: float = Field(default=35.0, alias="REGIME_VIX_CRISIS")
    regime_no_trade_entropy: float = Field(default=1.35, alias="REGIME_NO_TRADE_ENTROPY")
    regime_min_confidence: float = Field(default=0.40, alias="REGIME_MIN_CONFIDENCE")

    # Ensembler thresholds
    ensemble_min_score: float = Field(default=0.35, alias="ENSEMBLE_MIN_SCORE")

    # Expression engine
    options_enabled: bool = Field(default=False, alias="OPTIONS_ENABLED")
    max_option_allocation: float = Field(default=0.20, alias="MAX_OPTION_ALLOCATION")
    min_option_oi: int = Field(default=500, alias="MIN_OPTION_OI")

    # Strategy leaderboard
    strategy_cooldown_score: float = Field(default=0.20, alias="STRATEGY_COOLDOWN_SCORE")
    strategy_reduced_score: float = Field(default=0.35, alias="STRATEGY_REDUCED_SCORE")
    strategy_retire_days: int = Field(default=90, alias="STRATEGY_RETIRE_DAYS")

    # Position management
    stop_loss_pct: float = Field(default=0.03, alias="STOP_LOSS_PCT")
    trailing_stop_pct: float = Field(default=0.02, alias="TRAILING_STOP_PCT")
    max_hold_days: int = Field(default=30, alias="MAX_HOLD_DAYS")"""

if old_risk in cfg and "regime_vix_crisis" not in cfg:
    cfg = cfg.replace(old_risk, new_risk)
    print("OK 1: Added decision-layer config fields")
else:
    print("SKIP 1: already present or pattern mismatch")

with open(config_path, "w") as f:
    f.write(cfg)

# ── PATCH 2: RegimeRouter reads from config ──
rr_path = "src/engines/regime_router.py"
with open(rr_path, "r") as f:
    rr = f.read()

old_rr_init = """    def __init__(self, no_trade_entropy: float = 1.35,
                 min_confidence: float = 0.40):
        \"\"\"
        Args:
            no_trade_entropy: if entropy exceeds this, should_trade = False
            min_confidence: if max regime prob < this, reduce sizing
        \"\"\"
        self.no_trade_entropy = no_trade_entropy
        self.min_confidence = min_confidence"""

new_rr_init = """    def __init__(self, no_trade_entropy: float = None,
                 min_confidence: float = None):
        \"\"\"
        Args:
            no_trade_entropy: if entropy exceeds this, should_trade = False
            min_confidence: if max regime prob < this, reduce sizing
        \"\"\"
        # Read from config with fallback defaults
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            self.no_trade_entropy = no_trade_entropy or tc.regime_no_trade_entropy
            self.min_confidence = min_confidence or tc.regime_min_confidence
            self.VIX_CRISIS = tc.regime_vix_crisis
        except Exception:
            self.no_trade_entropy = no_trade_entropy or 1.35
            self.min_confidence = min_confidence or 0.40"""

if old_rr_init in rr:
    rr = rr.replace(old_rr_init, new_rr_init)
    print("OK 2: RegimeRouter reads from config")
else:
    print("SKIP 2: RegimeRouter pattern mismatch")

with open(rr_path, "w") as f:
    f.write(rr)

# ── PATCH 3: OpportunityEnsembler reads from config ──
oe_path = "src/engines/opportunity_ensembler.py"
with open(oe_path, "r") as f:
    oe = f.read()

old_oe_init = """    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_score: float = 0.35,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.min_score = min_score"""

new_oe_init = """    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_score: float = None,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        # Read from config with fallback
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            self.min_score = min_score or tc.ensemble_min_score
        except Exception:
            self.min_score = min_score or 0.35"""

if old_oe_init in oe:
    oe = oe.replace(old_oe_init, new_oe_init)
    print("OK 3: OpportunityEnsembler reads from config")
else:
    print("SKIP 3: OpportunityEnsembler pattern mismatch")

with open(oe_path, "w") as f:
    f.write(oe)

# ── PATCH 4: ExpressionEngine reads from config ──
ee_path = "src/engines/expression_engine.py"
with open(ee_path, "r") as f:
    ee = f.read()

old_ee_init = """    def __init__(
        self,
        options_enabled: bool = False,
        max_option_allocation: float = 0.20,
    ):
        \"\"\"
        Args:
            options_enabled: master switch for options
            max_option_allocation: max portfolio % in options
        \"\"\"
        self.options_enabled = options_enabled
        self.max_option_allocation = max_option_allocation"""

new_ee_init = """    def __init__(
        self,
        options_enabled: bool = None,
        max_option_allocation: float = None,
    ):
        \"\"\"
        Args:
            options_enabled: master switch for options
            max_option_allocation: max portfolio % in options
        \"\"\"
        # Read from config with fallback
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            self.options_enabled = (
                options_enabled if options_enabled is not None
                else tc.options_enabled
            )
            self.max_option_allocation = (
                max_option_allocation or tc.max_option_allocation
            )
            self.MIN_OPTION_OI = tc.min_option_oi
        except Exception:
            self.options_enabled = options_enabled or False
            self.max_option_allocation = (
                max_option_allocation or 0.20
            )"""

if old_ee_init in ee:
    ee = ee.replace(old_ee_init, new_ee_init)
    print("OK 4: ExpressionEngine reads from config")
else:
    print("SKIP 4: ExpressionEngine pattern mismatch")

with open(ee_path, "w") as f:
    f.write(ee)

# ── PATCH 5: StrategyLeaderboard reads from config ──
lb_path = "src/engines/strategy_leaderboard.py"
with open(lb_path, "r") as f:
    lb = f.read()

old_lb_init = """    def __init__(self):
        self._strategies: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []"""

new_lb_init = """    def __init__(self):
        self._strategies: Dict[str, Dict[str, Any]] = {}
        self._history: List[Dict[str, Any]] = []
        # Read from config with fallback
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            self.COOLDOWN_SCORE = tc.strategy_cooldown_score
            self.REDUCED_SCORE = tc.strategy_reduced_score
            self.RETIRE_AFTER_DAYS = tc.strategy_retire_days
        except Exception:
            pass  # use class-level defaults"""

if old_lb_init in lb:
    lb = lb.replace(old_lb_init, new_lb_init)
    print("OK 5: StrategyLeaderboard reads from config")
else:
    print("SKIP 5: StrategyLeaderboard pattern mismatch")

with open(lb_path, "w") as f:
    f.write(lb)

# ── PATCH 6: Wire PositionManager into AutoTradingEngine ──
ate_path = "src/engines/auto_trading_engine.py"
with open(ate_path, "r") as f:
    ate = f.read()

# Add PositionManager import
old_ate_import = "from src.engines.strategy_leaderboard import StrategyLeaderboard"
new_ate_import = """from src.engines.strategy_leaderboard import StrategyLeaderboard
from src.algo.position_manager import PositionManager, RiskParameters"""

if old_ate_import in ate and "PositionManager" not in ate:
    ate = ate.replace(old_ate_import, new_ate_import)
    print("OK 6a: Added PositionManager import")
else:
    print("SKIP 6a: import already present or mismatch")

# Add PositionManager init
old_ate_ctx = """        self._context: Dict[str, Any] = {}"""
new_ate_ctx = """        self._context: Dict[str, Any] = {}

        # Position management with trailing stops + R-targets
        try:
            from src.core.config import get_trading_config
            tc = get_trading_config()
            risk_params = RiskParameters(
                max_position_pct=tc.max_position_pct,
                max_sector_pct=tc.max_sector_pct,
                max_portfolio_var=tc.max_portfolio_var,
                max_drawdown_pct=tc.max_drawdown_pct,
                risk_per_trade=tc.risk_per_trade,
            )
        except Exception:
            risk_params = RiskParameters()
        self.position_mgr = PositionManager(params=risk_params)"""

if old_ate_ctx in ate and "position_mgr" not in ate:
    ate = ate.replace(old_ate_ctx, new_ate_ctx)
    print("OK 6b: Added PositionManager init")
else:
    print("SKIP 6b: PositionManager init already present or mismatch")

# Add post-trade outcome recording after successful execution
old_result_append = """                    result["composite_score"] = opp["composite_score"]
                    self._trades_today.append(result)"""

new_result_append = """                    result["composite_score"] = opp["composite_score"]
                    self._trades_today.append(result)
                    # Record in PositionManager for trailing stops
                    try:
                        self.position_mgr.open_position(
                            ticker=signal.ticker,
                            entry_price=result.get(
                                "entry_price", signal.entry_price
                            ),
                            shares=self._calculate_position_size(signal),
                            direction=signal.direction.value
                            if hasattr(signal.direction, "value")
                            else str(signal.direction),
                            strategy_name=opp.get("strategy_name", "unknown"),
                        )
                    except Exception as e:
                        logger.warning(f"PositionManager track error: {e}")"""

if old_result_append in ate:
    ate = ate.replace(old_result_append, new_result_append)
    print("OK 6c: Added post-trade PositionManager tracking")
else:
    print("SKIP 6c: result append pattern mismatch")

with open(ate_path, "w") as f:
    f.write(ate)

# ── Validate all files ──
print("\nValidating syntax...")
for p in [config_path, rr_path, oe_path, ee_path, lb_path, ate_path]:
    try:
        ast.parse(open(p).read())
        print(f"  OK: {p}")
    except SyntaxError as e:
        print(f"  FAIL: {p} — {e}")

print("\nDone.")
