"""Sprint 4 patch part 2: __init__ components + regime gate."""
path = "src/engines/auto_trading_engine.py"
with open(path, "r") as f:
    code = f.read()

# PATCH 2: Add component initialization
marker2 = "self._trades_today: List[Dict[str, Any]] = []"
insert2 = """self._trades_today: List[Dict[str, Any]] = []

        # Sprint 4: decision-layer components
        self.regime_router = RegimeRouter()
        self.ensembler = OpportunityEnsembler()
        self.context_assembler = ContextAssembler()
        self.leaderboard = StrategyLeaderboard()
        self._regime_state: Dict[str, Any] = {}
        self._context: Dict[str, Any] = {}"""

if marker2 in code and "self.regime_router" not in code:
    code = code.replace(marker2, insert2)
    print("OK 2: Added component initialization")
else:
    if "self.regime_router" in code:
        print("SKIP 2: Already present")
    else:
        print("FAIL 2: Pattern not found")

# PATCH 3: Add regime gate before signal generation
marker3 = "        # Generate signals for active markets\n        signals = await self._generate_signals(active_markets)"
insert3 = """        # Assemble decision context
        try:
            self._context = self.context_assembler.assemble_sync()
        except Exception as e:
            logger.warning(f"Context assembly failed: {e}")
            self._context = {}

        # Regime classification and trade gate
        mkt_state = self._context.get("market_state", {})
        self._regime_state = self.regime_router.classify(mkt_state)

        if not self._regime_state.get("should_trade", True):
            if self._cycle_count % 30 == 0:
                logger.info(
                    "Regime gate: no-trade "
                    f"(entropy={self._regime_state.get('entropy', 0):.2f})"
                )
            await self._monitor_positions()
            return

        # Generate signals for active markets
        signals = await self._generate_signals(active_markets)"""

if marker3 in code and "regime_router" not in code.split("_generate_signals(active_markets)")[0].split("_run_cycle")[1]:
    code = code.replace(marker3, insert3)
    print("OK 3: Added regime gate")
elif "Regime gate" in code:
    print("SKIP 3: Already present")
else:
    # Try line-by-line
    lines = code.split("\n")
    for i, line in enumerate(lines):
        if "# Generate signals for active markets" in line:
            indent = "        "
            gate_block = [
                f"{indent}# Assemble decision context",
                f"{indent}try:",
                f"{indent}    self._context = self.context_assembler.assemble_sync()",
                f"{indent}except Exception as e:",
                f"{indent}    logger.warning(f\"Context assembly failed: {{e}}\")",
                f"{indent}    self._context = {{}}",
                "",
                f"{indent}# Regime classification and trade gate",
                f"{indent}mkt_state = self._context.get(\"market_state\", {{}})",
                f"{indent}self._regime_state = self.regime_router.classify(mkt_state)",
                "",
                f"{indent}if not self._regime_state.get(\"should_trade\", True):",
                f"{indent}    if self._cycle_count % 30 == 0:",
                f"{indent}        logger.info(",
                f"{indent}            \"Regime gate: no-trade \"",
                f"{indent}            f\"(entropy={{self._regime_state.get('entropy', 0):.2f}})\"",
                f"{indent}        )",
                f"{indent}    await self._monitor_positions()",
                f"{indent}    return",
                "",
            ]
            for j, gl in enumerate(gate_block):
                lines.insert(i + j, gl)
            code = "\n".join(lines)
            print("OK 3: Added regime gate (line insert)")
            break
    else:
        print("FAIL 3: Could not find insertion point")

with open(path, "w") as f:
    f.write(code)

import ast
try:
    ast.parse(code)
    print("Syntax: OK")
except SyntaxError as e:
    print(f"SYNTAX ERROR: {e}")
