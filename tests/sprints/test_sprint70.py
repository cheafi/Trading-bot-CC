"""Sprint 70 — Wire historical_analog into VCP, GapScanner, 3 API endpoints."""
import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(__file__))


# ── 1. VCPIntelligence now populates similar_cases ──────────────

class TestVCPAnalogWiring:
    def _make_trades_file(self):
        tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
        trades = [
            {"ticker": "AAPL", "strategy_id": "vcp", "direction": "LONG",
             "regime_at_entry": "UPTREND", "setup_grade": "A",
             "pnl_pct": 8.8, "r_multiple": 2.1, "hold_days": 12},
            {"ticker": "MSFT", "strategy_id": "vcp", "direction": "LONG",
             "regime_at_entry": "UPTREND", "setup_grade": "B",
             "pnl_pct": -2.5, "r_multiple": -0.8, "hold_days": 5},
        ]
        for t in trades:
            tmp.write(json.dumps(t) + "\n")
        tmp.close()
        return tmp.name

    def test_vcp_analyze_populates_similar_cases(self):
        """VCPIntelligence.analyze() should populate similar_cases."""
        from src.engines.vcp_intelligence import VCPIntelligence
        from src.engines.sector_classifier import SectorContext
        from src.engines import historical_analog

        path = self._make_trades_file()
        try:
            old_path = historical_analog._TRADES_PATH
            historical_analog._TRADES_PATH = path

            vcp = VCPIntelligence()
            sig = {"ticker": "TEST", "strategy": "vcp", "contraction_count": 3,
                   "score": 7, "distance_from_highs": 3}
            ctx = SectorContext(ticker="TEST")
            regime = {"trend": "UPTREND", "risk_score": 3}
            result = vcp.analyze(sig, ctx, regime)
            assert result.action.similar_cases, "similar_cases should not be empty"
            assert result.action.similar_cases[0]["ticker"] in ("AAPL", "MSFT")
        finally:
            historical_analog._TRADES_PATH = old_path
            os.unlink(path)

    def test_vcp_no_match_empty_cases(self):
        """No matching strategy → empty similar_cases."""
        from src.engines.vcp_intelligence import VCPIntelligence
        from src.engines.sector_classifier import SectorContext
        from src.engines import historical_analog

        path = self._make_trades_file()
        try:
            old_path = historical_analog._TRADES_PATH
            historical_analog._TRADES_PATH = path

            vcp = VCPIntelligence()
            sig = {"ticker": "X", "strategy": "momentum", "contraction_count": 3,
                   "score": 7, "distance_from_highs": 3}
            # strategy=momentum won't match "vcp" trades — but VCP detection
            # uses contraction_count so it'll still be is_vcp=True
            # The historical_analog uses sig["strategy"] so "momentum" won't match "vcp"
            ctx = SectorContext(ticker="X")
            regime = {"trend": "UPTREND"}
            result = vcp.analyze(sig, ctx, regime)
            # "momentum" strategy won't find "vcp" trades
            assert result.action.similar_cases == []
        finally:
            historical_analog._TRADES_PATH = old_path
            os.unlink(path)


# ── 2. GapScanner ────────────────────────────────────────────────

class TestGapScanner:
    def test_gap_scanner_detects_breakaway(self):
        from src.engines.scanner_matrix import GapScanner
        scanner = GapScanner()
        # Create OHLCV with a gap up
        opens  = [100, 101, 102, 103, 108, 109]
        closes = [101, 102, 103, 104, 109, 110]
        highs  = [102, 103, 104, 105, 110, 111]
        lows   = [99,  100, 101, 102, 107, 108]
        sig = {"ticker": "GAP", "opens": opens, "closes": closes,
               "highs": highs, "lows": lows}
        hits = scanner.scan([sig], {"trend": "UPTREND"})
        # Should detect at least one gap
        assert len(hits) >= 1
        assert hits[0].scanner_name == "gap"

    def test_gap_scanner_no_ohlcv_skips(self):
        from src.engines.scanner_matrix import GapScanner
        scanner = GapScanner()
        sig = {"ticker": "NOOHLCV", "score": 5}
        hits = scanner.scan([sig], {})
        assert hits == []

    def test_gap_scanner_in_registry(self):
        from src.engines.scanner_matrix import ScannerMatrix
        matrix = ScannerMatrix()
        names = [s.name for s in matrix.scanners]
        assert "gap" in names


# ── 3. API endpoints ────────────────────────────────────────────

class TestAPIEndpoints:
    def test_compare_route_exists(self):
        from src.api.routers.intel import router
        paths = [r.path for r in router.routes]
        assert "/api/v6/compare/{ticker}" in paths

    def test_gaps_route_exists(self):
        from src.api.routers.intel import router
        paths = [r.path for r in router.routes]
        assert "/api/v6/gaps/{ticker}" in paths

    def test_analogs_route_exists(self):
        from src.api.routers.intel import router
        paths = [r.path for r in router.routes]
        assert "/api/v6/analogs/{ticker}" in paths

    def test_analog_endpoint_returns_summary(self):
        """Direct function call test for analogs."""
        import asyncio
        from src.api.routers.intel import historical_analogs
        result = asyncio.run(historical_analogs("AAPL", strategy="vcp", regime=""))
        assert "ticker" in result
        assert "summary" in result
        assert result["ticker"] == "AAPL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
