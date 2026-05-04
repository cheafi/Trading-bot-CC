"""
Peer Comparison Engine — Sprint 73
====================================
Three types of peer comparison:
  1. Sector peers — same industry, ranked by RS
  2. Behavior peers — similar RS + volume + setup pattern
  3. Setup peers — historical cases with similar chart structure

Answers: "Why this stock and not its peers?"
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


# ── Sector Peer Groups ──────────────────────────────────────────────────────

PEER_GROUPS: Dict[str, List[str]] = {
    # Semis
    "NVDA": ["AMD", "AVGO", "MU", "INTC", "TXN", "QCOM", "AMAT", "TSM"],
    "AMD": ["NVDA", "INTC", "MU", "AVGO", "QCOM", "TXN"],
    "AVGO": ["NVDA", "AMD", "TXN", "QCOM", "AMAT"],
    "INTC": ["AMD", "NVDA", "TXN", "MU"],
    # Big tech
    "AAPL": ["MSFT", "GOOGL", "META", "AMZN"],
    "MSFT": ["AAPL", "GOOGL", "CRM", "ORCL", "ADBE"],
    "GOOGL": ["META", "MSFT", "AMZN", "NFLX"],
    "META": ["GOOGL", "NFLX", "SNAP", "PINS"],
    "AMZN": ["GOOGL", "MSFT", "NFLX", "SHOP"],
    # Consumer
    "TSLA": ["GM", "F", "RIVN", "NIO"],
    "NFLX": ["DIS", "GOOGL", "META"],
    # Financials
    "JPM": ["BAC", "GS", "MS", "C", "WFC"],
    "GS": ["MS", "JPM", "SCHW"],
    "V": ["MA", "PYPL", "SQ"],
    # Healthcare
    "UNH": ["HUM", "CI", "ELV"],
    "LLY": ["MRK", "PFE", "ABBV", "JNJ"],
    "JNJ": ["PFE", "ABBV", "MRK", "LLY"],
    # Energy
    "XOM": ["CVX", "COP", "EOG", "SLB"],
    "CVX": ["XOM", "COP", "EOG"],
    # Industrials
    "CAT": ["DE", "BA", "GE", "HON"],
    "BA": ["LMT", "RTX", "GE", "NOC"],
}

# Fallback: sector → representative tickers
_SECTOR_FALLBACK: Dict[str, List[str]] = {
    "Technology": ["AAPL", "MSFT", "NVDA", "CRM", "ADBE", "ORCL"],
    "Communication": ["META", "GOOGL", "NFLX", "DIS"],
    "Consumer Discretionary": ["AMZN", "TSLA", "HD", "NKE"],
    "Financials": ["JPM", "BAC", "GS", "V", "MA"],
    "Healthcare": ["UNH", "JNJ", "LLY", "ABBV", "PFE"],
    "Energy": ["XOM", "CVX", "COP", "EOG"],
    "Industrials": ["CAT", "BA", "GE", "HON", "UPS"],
    "Materials": ["LIN", "APD", "NEM", "FCX"],
    "Utilities": ["NEE", "DUK", "SO", "AEP"],
    "Real Estate": ["PLD", "AMT", "CCI", "EQIX"],
    "Consumer Staples": ["PG", "KO", "PEP", "WMT", "COST"],
}


class PeerEngine:
    """Peer comparison across sector, behavior, and setup dimensions."""

    def get_sector_peers(
        self,
        ticker: str,
        limit: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Return sector peers ranked by RS composite.
        Each peer includes RS data for direct comparison.
        """
        ticker = ticker.upper()
        candidates = PEER_GROUPS.get(ticker, [])

        if not candidates:
            # Fallback to sector
            from src.engines.rs_hub import _get_sector
            sector = _get_sector(ticker)
            candidates = [
                t for t in _SECTOR_FALLBACK.get(sector, [])
                if t != ticker
            ]

        if not candidates:
            return []

        # Fetch RS for all peers
        peers = []
        try:
            from src.services.rs_data_service import compute_rs_date_aligned, fetch_closes_batch
            closes = fetch_closes_batch(candidates + ["SPY"])
            spy = closes.get("SPY")
            if spy is None or len(spy) < 22:
                return [{"ticker": t, "rs_composite": 100.0} for t in candidates[:limit]]

            for t in candidates:
                t_closes = closes.get(t)
                if t_closes is None or len(t_closes) < 22:
                    continue
                rs = compute_rs_date_aligned(t_closes, spy)
                peers.append({
                    "ticker": t,
                    "rs_composite": rs["rs_composite"],
                    "rs_slope": rs["rs_slope"],
                    "rs_status": str(rs["rs_status"]),
                })
        except Exception as e:
            logger.debug("[PeerEngine] RS fetch failed: %s", e)
            return [{"ticker": t, "rs_composite": 100.0} for t in candidates[:limit]]

        # Sort by RS descending
        peers.sort(key=lambda p: p["rs_composite"], reverse=True)
        return peers[:limit]

    def get_behavior_peers(
        self,
        ticker: str,
        rs_composite: float,
        rs_slope: float,
        limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        Find tickers with similar RS behavior:
        similar composite level + similar slope direction.
        """
        try:
            from src.services.rs_data_service import compute_rs_date_aligned, fetch_closes_batch
            from src.engines.rs_hub import SECTOR_MAP

            # Search across a broad universe
            universe = list(SECTOR_MAP.keys())
            universe = [t for t in universe if t != ticker.upper()]

            closes = fetch_closes_batch(universe + ["SPY"])
            spy = closes.get("SPY")
            if spy is None or len(spy) < 22:
                return []

            similar = []
            for t in universe:
                t_closes = closes.get(t)
                if t_closes is None or len(t_closes) < 22:
                    continue
                rs = compute_rs_date_aligned(t_closes, spy)
                # Similarity: close in composite (±15) and same slope direction
                comp_diff = abs(rs["rs_composite"] - rs_composite)
                slope_same = (rs["rs_slope"] > 0) == (rs_slope > 0)
                if comp_diff <= 15 and slope_same:
                    similar.append({
                        "ticker": t,
                        "rs_composite": rs["rs_composite"],
                        "rs_slope": rs["rs_slope"],
                        "similarity": round(100 - comp_diff * 3, 1),
                    })

            similar.sort(key=lambda p: p["similarity"], reverse=True)
            return similar[:limit]
        except Exception as e:
            logger.debug("[PeerEngine] behavior peers: %s", e)
            return []

    def compare_vs_peers(
        self,
        ticker: str,
        limit: int = 5,
    ) -> Dict[str, Any]:
        """
        Full peer comparison report:
        - sector peers with RS ranking
        - which peer is stronger/weaker
        - why this ticker vs alternatives
        """
        ticker = ticker.upper()
        sector_peers = self.get_sector_peers(ticker, limit=limit)

        # Get subject's own RS
        subject_rs = 100.0
        try:
            from src.services.rs_data_service import compute_rs_date_aligned, fetch_single
            t_closes = fetch_single(ticker)
            spy_closes = fetch_single("SPY")
            if t_closes is not None and spy_closes is not None and len(t_closes) >= 22:
                rs = compute_rs_date_aligned(t_closes, spy_closes)
                subject_rs = rs["rs_composite"]
        except Exception:
            pass

        # Find stronger and weaker peers
        stronger = [p for p in sector_peers if p["rs_composite"] > subject_rs]
        weaker = [p for p in sector_peers if p["rs_composite"] < subject_rs]

        # Build explanation
        explanations = []
        if not stronger:
            explanations.append(f"{ticker} is the RS leader among its sector peers")
        else:
            top = stronger[0]["ticker"]
            explanations.append(
                f"{top} has stronger RS ({stronger[0]['rs_composite']:.0f} vs {subject_rs:.0f})"
            )
        if weaker:
            bottom = weaker[-1]["ticker"]
            explanations.append(
                f"{ticker} outperforms {bottom} (RS {subject_rs:.0f} vs {weaker[-1]['rs_composite']:.0f})"
            )

        return {
            "ticker": ticker,
            "rs_composite": subject_rs,
            "sector_peers": sector_peers,
            "stronger_peers": [p["ticker"] for p in stronger],
            "weaker_peers": [p["ticker"] for p in weaker],
            "peer_rank": len(stronger) + 1,
            "peer_count": len(sector_peers) + 1,
            "explanations": explanations,
        }
