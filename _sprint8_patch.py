#!/usr/bin/env python3
"""Sprint 8: Singleton BrokerManager, EdgeCalculator invocation, position sizing, persistence"""
import os, ast

ROOT = os.path.dirname(os.path.abspath(__file__))

def read(rel):
    with open(os.path.join(ROOT, rel), "r") as f:
        return f.read()

def write(rel, txt):
    with open(os.path.join(ROOT, rel), "w") as f:
        f.write(txt)

# ===========================================================================
# PATCH 1: Singleton BrokerManager in AutoTradingEngine
# ===========================================================================
def patch1():
    src = read("src/engines/auto_trading_engine.py")
    changes = 0

    # 1a: Add self._broker_mgr = None in __init__
    marker = "        self.learning_loop = TradeLearningLoop()"
    if "self._broker_mgr" not in src:
        src = src.replace(marker, marker + "\n        self._broker_mgr = None  # singleton, init in run()")
        changes += 1
        print("OK 1a: Added self._broker_mgr = None")
    else:
        print("SKIP 1a: _broker_mgr already present")

    # 1b: Add _get_broker() helper method
    helper = '''
    async def _get_broker(self):
        """Get or create the singleton BrokerManager instance."""
        if self._broker_mgr is None:
            from src.brokers.broker_manager import BrokerManager
            self._broker_mgr = BrokerManager()
            await self._broker_mgr.initialize()
            logger.info("BrokerManager singleton initialized")
        return self._broker_mgr

'''
    if "async def _get_broker(self)" not in src:
        insert_at = "    async def _get_equity(self) -> float:"
        src = src.replace(insert_at, helper + insert_at)
        changes += 1
        print("OK 1b: Added _get_broker() singleton helper")
    else:
        print("SKIP 1b: _get_broker already present")

    # 1c: Replace all 4 BrokerManager() instantiations with _get_broker()
    # Pattern in _execute_signal
    old_exec = """            from src.brokers.broker_manager import BrokerManager
            from src.brokers.base import OrderSide, OrderType

            manager = BrokerManager()
            await manager.initialize()"""
    new_exec = """            from src.brokers.base import OrderSide, OrderType

            manager = await self._get_broker()"""
    if old_exec in src:
        src = src.replace(old_exec, new_exec)
        changes += 1
        print("OK 1c: Replaced BrokerManager in _execute_signal")

    # Pattern in _monitor_positions
    old_mon = """            from src.brokers.broker_manager import BrokerManager
            manager = BrokerManager()
            await manager.initialize()
            broker_positions = await manager.get_positions()"""
    new_mon = """            manager = await self._get_broker()
            broker_positions = await manager.get_positions()"""
    if old_mon in src:
        src = src.replace(old_mon, new_mon)
        changes += 1
        print("OK 1c: Replaced BrokerManager in _monitor_positions")

    # Pattern in _get_equity
    old_eq = """            from src.brokers.broker_manager import BrokerManager
            manager = BrokerManager()
            await manager.initialize()
            account = await manager.get_account()"""
    new_eq = """            manager = await self._get_broker()
            account = await manager.get_account()"""
    if old_eq in src:
        src = src.replace(old_eq, new_eq)
        changes += 1
        print("OK 1c: Replaced BrokerManager in _get_equity")

    # Pattern in _count_positions
    old_cnt = """            from src.brokers.broker_manager import BrokerManager
            manager = BrokerManager()
            await manager.initialize()
            positions = await manager.get_positions()"""
    new_cnt = """            manager = await self._get_broker()
            positions = await manager.get_positions()"""
    if old_cnt in src:
        src = src.replace(old_cnt, new_cnt)
        changes += 1
        print("OK 1c: Replaced BrokerManager in _count_positions")

    write("src/engines/auto_trading_engine.py", src)
    ast.parse(src)
    print(f"OK 1: Singleton BrokerManager ({changes} changes)")


# ===========================================================================
# PATCH 2: BrokerError wrapping in BrokerManager
# ===========================================================================
def patch2():
    src = read("src/brokers/broker_manager.py")

    # 2a: Import BrokerError
    if "BrokerError" not in src:
        old_imp = "from src.core.config import get_settings"
        new_imp = """from src.core.config import get_settings

try:
    from src.core.errors import BrokerError
except ImportError:
    class BrokerError(Exception):
        pass"""
        src = src.replace(old_imp, new_imp, 1)
        print("OK 2a: Added BrokerError import to broker_manager")
    else:
        print("SKIP 2a: BrokerError already imported")

    # 2b: Wrap place_order no-broker case
    old_no_broker = '''        if not target_broker:
            return OrderResult(
                success=False,
                message="No broker available"
            )'''
    new_no_broker = '''        if not target_broker:
            raise BrokerError(
                message="No broker available for order",
                broker=str(broker or self._active_broker),
            )'''
    if old_no_broker in src:
        src = src.replace(old_no_broker, new_no_broker)
        print("OK 2b: place_order raises BrokerError on missing broker")
    else:
        print("SKIP 2b: place_order pattern changed")

    write("src/brokers/broker_manager.py", src)
    ast.parse(src)
    print("OK 2: BrokerManager raises BrokerError")


# ===========================================================================
# PATCH 3: Invoke EdgeCalculator.compute() in signal ranking
# ===========================================================================
def patch3():
    src = read("src/engines/auto_trading_engine.py")

    # Find the signal_dicts building loop and enrich with edge data
    old_signal_dict = '''        # Rank through ensemble scorer
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
            })'''

    new_signal_dict = '''        # Rank through ensemble scorer (with calibrated edge if available)
        signal_dicts = []
        for sig in validated:
            sd = {
                "ticker": sig.ticker,
                "direction": sig.direction.value if hasattr(sig.direction, 'value') else sig.direction,
                "score": sig.confidence / 100 if hasattr(sig, 'confidence') else 0.5,
                "strategy_name": sig.strategy_name if hasattr(sig, 'strategy_name') else "unknown",
                "risk_reward_ratio": getattr(sig, 'risk_reward_ratio', 1.5),
                "expected_return": getattr(sig, 'expected_return', 0.02),
                "_signal_obj": sig,  # keep reference
            }

            # Sprint 8: enrich with EdgeCalculator calibrated probabilities
            if self.edge_calculator is not None:
                try:
                    edge = self.edge_calculator.compute(
                        signal=sig,
                        regime=self._regime_state,
                        features={
                            "relative_volume": getattr(sig, "relative_volume", 1.0),
                            "rsi_14": getattr(sig, "rsi", 50),
                        },
                    )
                    sd["edge_p_t1"] = edge.p_t1
                    sd["edge_p_stop"] = edge.p_stop
                    sd["edge_ev"] = edge.expected_return_pct
                except Exception:
                    pass  # graceful fallback

            signal_dicts.append(sd)'''

    if "edge_p_t1" not in src and old_signal_dict in src:
        src = src.replace(old_signal_dict, new_signal_dict)
        write("src/engines/auto_trading_engine.py", src)
        ast.parse(src)
        print("OK 3: EdgeCalculator.compute() invoked in signal ranking")
    else:
        print("SKIP 3: EdgeCalculator already invoked or pattern changed")


# ===========================================================================
# PATCH 4: Upgrade _calculate_position_size to use PositionManager
# ===========================================================================
def patch4():
    src = read("src/engines/auto_trading_engine.py")

    old_sizing = '''    def _calculate_position_size(self, signal) -> int:
        """
        Risk-based position sizing.
        Risks 1% of equity per trade, using stop distance.
        """
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                equity = 100000.0
            else:
                equity = loop.run_until_complete(self._get_equity())
        except Exception:
            equity = 100000.0

        risk_per_trade = equity * 0.01

        price = getattr(signal, "price", 0) or getattr(signal, "close", 0)
        if not price or price <= 0:
            return 1

        stop_pct = 0.03
        stop_distance = price * stop_pct

        if stop_distance <= 0:
            return 1

        shares = int(risk_per_trade / stop_distance)
        max_shares = int((equity * 0.05) / price)
        return max(1, min(shares, max_shares))'''

    new_sizing = '''    def _calculate_position_size(self, signal) -> int:
        """
        Risk-based position sizing using PositionManager.
        Falls back to simple 1% risk calculation if PositionManager fails.
        """
        price = getattr(signal, "entry_price", 0) or getattr(signal, "price", 0) or getattr(signal, "close", 0)
        if not price or price <= 0:
            return 1

        # Compute stop from signal or config default
        stop_price = price * (1 - trading_config.stop_loss_pct)
        if getattr(signal, "invalidation", None) and getattr(signal.invalidation, "stop_price", 0):
            stop_price = signal.invalidation.stop_price

        # Try PositionManager for full risk-based sizing
        try:
            result = self.position_mgr.calculate_position_size(
                ticker=getattr(signal, "ticker", "UNKNOWN"),
                entry_price=price,
                stop_loss_price=stop_price,
                sector=getattr(signal, "sector", ""),
            )
            if result.get("can_trade") and result.get("shares", 0) > 0:
                return result["shares"]
        except Exception as e:
            logger.debug("PositionManager sizing fallback: %s", e)

        # Fallback: simple 1% risk
        equity = 100000.0
        risk_per_trade = equity * 0.01
        stop_distance = abs(price - stop_price)
        if stop_distance <= 0:
            return 1
        shares = int(risk_per_trade / stop_distance)
        max_shares = int((equity * 0.05) / price)
        return max(1, min(shares, max_shares))'''

    if old_sizing in src:
        src = src.replace(old_sizing, new_sizing)
        write("src/engines/auto_trading_engine.py", src)
        ast.parse(src)
        print("OK 4: Position sizing upgraded to use PositionManager")
    else:
        print("SKIP 4: _calculate_position_size pattern changed")


# ===========================================================================
# PATCH 5: Add JSON persistence for TradeLearningLoop outcomes
# ===========================================================================
def patch5():
    src = read("src/ml/trade_learner.py")

    # 5a: Add _persist/_load methods to TradeLearningLoop
    if "_persist_outcomes" not in src:
        persist_code = '''
    def _persist_outcomes(self):
        """Save trade outcomes to JSON for persistence across restarts."""
        import json
        path = MODEL_DIR / "trade_outcomes.json"
        try:
            data = [o.to_dict() for o in self._outcomes]
            with open(path, "w") as f:
                json.dump(data, f, default=str)
            logger.info("Persisted %d trade outcomes to %s", len(data), path)
        except Exception as e:
            logger.warning("Outcome persistence error: %s", e)

    def _load_persisted_outcomes(self):
        """Load previously saved trade outcomes."""
        import json
        path = MODEL_DIR / "trade_outcomes.json"
        if not path.exists():
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            for d in data:
                record = TradeOutcomeRecord(
                    trade_id=d.get("trade_id", ""),
                    ticker=d.get("ticker", ""),
                    direction=d.get("direction", "LONG"),
                    strategy=d.get("strategy", "unknown"),
                    entry_price=d.get("entry_price", 0),
                    exit_price=d.get("exit_price", 0),
                    entry_time=d.get("entry_time", ""),
                    exit_time=d.get("exit_time", ""),
                    pnl_pct=d.get("pnl_pct", 0),
                    confidence=d.get("confidence", 50),
                    horizon=d.get("horizon", "swing"),
                    exit_reason=d.get("exit_reason", ""),
                )
                self._outcomes.append(record)
                self.predictor.add_outcome(record)
            logger.info("Loaded %d persisted trade outcomes", len(data))
        except Exception as e:
            logger.warning("Outcome load error: %s", e)
'''
        # Insert before get_performance_summary
        marker = "    def get_performance_summary(self)"
        if marker in src:
            src = src.replace(marker, persist_code + "\n" + marker)
            print("OK 5a: Added _persist/_load methods")
        else:
            print("SKIP 5a: get_performance_summary marker not found")
    else:
        print("SKIP 5a: persistence methods already present")

    # 5b: Call _load on __init__ and _persist on record_outcome
    if "_load_persisted_outcomes" in src and "self._load_persisted_outcomes()" not in src:
        # Add load call in __init__
        init_marker = "        self._last_analysis: Optional[Dict[str, Any]] = None"
        if init_marker in src:
            src = src.replace(
                init_marker,
                init_marker + "\n        self._load_persisted_outcomes()"
            )
            print("OK 5b: Added _load_persisted_outcomes() in __init__")

        # Add persist call in record_outcome
        record_marker = '            logger.info(f"Auto-retrained model: {metrics}")'
        if record_marker in src:
            src = src.replace(
                record_marker,
                record_marker + "\n            self._persist_outcomes()"
            )
            print("OK 5b: Added _persist_outcomes() after retrain")
    else:
        print("SKIP 5b: persistence wiring already done or markers missing")

    write("src/ml/trade_learner.py", src)
    ast.parse(src)
    print("OK 5: Learning loop persistence added")


# ===========================================================================
if __name__ == "__main__":
    patch1()
    patch2()
    patch3()
    patch4()
    patch5()
    print("\n=== Sprint 8 patches complete ===")
