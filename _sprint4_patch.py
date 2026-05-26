"""Sprint 4 patch: wire orphaned modules into AutoTradingEngine."""
import re

path = "src/engines/auto_trading_engine.py"
with open(path, "r") as f:
    code = f.read()

# ── PATCH 1: Add new imports after existing imports ──
old_imports = "from src.core.models import Direction, Signal, SignalStatus"
new_imports = """from src.core.models import Direction, Signal, SignalStatus
from src.engines.regime_router import RegimeRouter
from src.engines.opportunity_ensembler import OpportunityEnsembler
from src.engines.context_assembler import ContextAssembler
from src.engines.strategy_leaderboard import StrategyLeaderboard"""

if old_imports in code and "RegimeRouter" not in code:
    code = code.replace(old_imports, new_imports)
    print("OK 1: Added new imports")
else:
    print("SKIP 1: imports already present or pattern mismatch")

# ── PATCH 2: Add new components to __init__ ──
old_init = """        self._signals_today: List[Signal] = []
        self._trades_today: List[Dict[str, Any]] = []"""

new_init = """        self._signals_today: List[Signal] = []
        self._trades_today: List[Dict[str, Any]] = []

        # Sprint 4: decision-layer components
        self.regime_router = RegimeRouter()
        self.ensembler = OpportunityEnsembler()
        self.context_assembler = ContextAssembler()
        self.leaderboard = StrategyLeaderboard()
        self._regime_state: Dict[str, Any] = {}
        self._context: Dict[str, Any] = {}"""

if old_init in code and "regime_router" not in code:
    code = code.replace(old_init, new_init)
    print("OK 2: Added new components to __init__")
else:
    print("SKIP 2: __init__ already patched or pattern mismatch")

# ── PATCH 3: Add regime gate + context assembly in _run_cycle ──
old_cycle = """        # Generate signals for active markets
        signals = await self._generate_signals(active_markets)"""

new_cycle = """        # Assemble decision context (market state, portfolio, news)
        try:
            self._context = self.context_assembler.assemble_sync()
        except Exception as e:
            logger.warning(f"Context assembly failed: {e}")
            self._context = {}

        # Regime classification and trade gate
        market_state = self._context.get("market_state", {})
        self._regime_state = self.regime_router.classify(market_state)

        if not self._regime_state.get("should_trade", True):
            if self._cycle_count % 30 == 0:
                logger.info(
                    f"Regime gate: no-trade "
                    f"(entropy={self._regime_state.get('entropy', 0):.2f}, "
                    f"vix={self._regime_state.get('vix', 0):.1f})"
                )
            # Still monitor positions even when not generating new signals
            await self._monitor_positions()
            return

        # Generate signals for active markets
        signals = await self._generate_signals(active_markets)"""

if old_cycle in code and "regime_router" not in code.split("_run_cycle")[0]:
    code = code.replace(old_cycle, new_cycle)
    print("OK 3: Added regime gate + context assembly")
else:
    print("SKIP 3: regime gate already present or pattern mismatch")

# ── PATCH 4: Replace simple signal iteration with ensembler ──
old_execute = """        # Execute
        for signal in validated:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would execute: {signal.ticker} {signal.direction.value}")
            else:
                result = await self._execute_signal(signal)
                if result:
                    self._trades_today.append(result)"""

new_execute = """        # Rank through ensemble scorer
        signal_dicts = []
        for sig in validated:
            signal_dicts.append({
                "ticker": sig.ticker,
                "direction": sig.direction.value if hasattr(sig.direction, 'value') else sig.direction,
                "score": sig.confidence / 100 if hasattr(sig, 'confidence') else 0.5,
                "strategy_name": sig.strategy_name if hasattr(sig, 'strategy_name') else "unknown",
                "risk_reward_ratio": getattr(sig, 'risk_reward_ratio', 1.5),
                "expected_return": getattr(sig, 'expected_return', 0.02),
                "_signal_obj": sig,  # keep reference
            })

        ranked = self.ensembler.rank_opportunities(
            signal_dicts,
            self._regime_state,
            portfolio_state=self._context.get("portfolio_state"),
            strategy_scores=self.leaderboard.get_strategy_scores(),
        )

        # Execute only approved opportunities
        for opp in ranked:
            if not opp.get("trade_decision", False):
                continue
            signal = opp["original_signal"].get("_signal_obj")
            if signal is None:
                continue
            if self.dry_run:
                logger.info(
                    f"[DRY RUN] Would execute: {signal.ticker} "
                    f"{signal.direction.value} "
                    f"(score={opp['composite_score']:.3f})"
                )
            else:
                result = await self._execute_signal(signal)
                if result:
                    result["composite_score"] = opp["composite_score"]
                    self._trades_today.append(result)"""

if old_execute in code:
    code = code.replace(old_execute, new_execute)
    print("OK 4: Replaced execution with ensembler ranking")
else:
    print("SKIP 4: execute block pattern mismatch")

# ── PATCH 5: Feed context into _validate_signals ──
old_validate_call = """            results = await validator.validate_batch(
                signals=signals,
                news_by_ticker={},
                sentiment_by_ticker={},
            )"""

new_validate_call = """            results = await validator.validate_batch(
                signals=signals,
                news_by_ticker=self._context.get("news_by_ticker", {}),
                sentiment_by_ticker=self._context.get("sentiment", {}),
            )"""

if old_validate_call in code:
    code = code.replace(old_validate_call, new_validate_call)
    print("OK 5: Fed context into GPT validation")
else:
    print("SKIP 5: validate pattern mismatch")

# ── PATCH 6: Feed portfolio context into _generate_signals ──
old_portfolio = """            signals = engine.generate_signals(
                universe=valid_tickers,
                features=features_df,
                market_data=_mkt,
                portfolio={},
            )"""

new_portfolio = """            signals = engine.generate_signals(
                universe=valid_tickers,
                features=features_df,
                market_data=_mkt,
                portfolio=self._context.get("portfolio_state", {}),
            )"""

if old_portfolio in code:
    code = code.replace(old_portfolio, new_portfolio)
    print("OK 6: Fed portfolio context into signal generation")
else:
    print("SKIP 6: portfolio pattern mismatch")

with open(path, "w") as f:
    f.write(code)

print("\nDone. Validating syntax...")
import ast
try:
    ast.parse(code)
    print("OK: syntax valid")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
