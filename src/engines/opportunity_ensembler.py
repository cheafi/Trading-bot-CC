"""
Opportunity Ensembler — Quantamental Rank & Filter.

Scoring philosophy: Robert Mercer / Elwyn Berlekamp
  "We're right 50.75% of the time, but we're 100% right 50.75% of the time."
  "We need a smaller edge on each trade."

This means we don't need certainty — we need POSITIVE NET EXPECTANCY
applied consistently. Every gate here is designed to protect that edge.

Quantamental signals incorporated from je-suis-tm/quant-trading:
  1. MACD momentum divergence — trend direction confirmation
  2. Bollinger Band position — volatility regime + breakout timing
  3. RSI regime — overbought/oversold pattern recognition
  4. Dual Thrust levels — opening-range breakout validation
  5. Heikin-Ashi noise filter — smoothed momentum direction
  6. Pair-trade RS ranking — sector relative strength bonus
  7. Regime-conditional strategy weights — only run strategies
     that have positive expectancy in the current regime

Scoring formula — net expectancy first:
  net_exp     = p(win) * avg_win_R − p(loss) * avg_loss_R   [primary, 35%]
  momentum    = MACD + Heikin-Ashi direction agreement       [15%]
  timing      = BB position + Dual Thrust proximity          [15%]
  regime_fit  = strategy×regime affinity (regime router)     [20%]
  rs_rank     = Mansfield RS vs SPY                          [10%]
  health      = strategy leaderboard Bayesian win rate        [5%]

Design: pure scoring, no I/O, no broker calls.
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.models import TradeRecommendation

logger = logging.getLogger(__name__)


# ── Component weights ─────────────────────────────────────────────
# Weights must sum to 1.0.
# net_expectancy is primary: a positive-EV trade is worth taking
# even in a sub-optimal regime; a negative-EV trade is never worth it.
DEFAULT_WEIGHTS: Dict[str, float] = {
    "net_expectancy": 0.35,   # Kelly/Mercer: only edge that matters
    "momentum":       0.15,   # MACD + Heikin-Ashi confirmation
    "timing":         0.15,   # BB position + Dual Thrust proximity
    "regime_fit":     0.20,   # regime × strategy affinity
    "rs_rank":        0.10,   # Mansfield RS vs benchmark
    "health":         0.05,   # leaderboard Bayesian win rate
}

# Suppression thresholds
MIN_COMPOSITE_SCORE  = 0.32   # below this → no trade
MIN_RISK_REWARD      = 2.0    # R:R gate for TRADE conviction
MIN_WIN_PROBABILITY  = 0.40   # below this → low-edge discard
MAX_REGIME_ENTROPY   = 0.90   # high entropy → regime uncertainty → no trade

# Strategy → regime affinity map
# (strategy_family: {regime_component: affinity_score 0-1})
STRATEGY_REGIME_AFFINITY: Dict[str, Dict[str, float]] = {
    "momentum":    {"risk_on_uptrend": 0.90, "neutral_range": 0.35, "risk_off_downtrend": 0.05},
    "breakout":    {"risk_on_uptrend": 0.85, "neutral_range": 0.40, "risk_off_downtrend": 0.10},
    "vcp":         {"risk_on_uptrend": 0.80, "neutral_range": 0.50, "risk_off_downtrend": 0.10},
    "swing":       {"risk_on_uptrend": 0.60, "neutral_range": 0.70, "risk_off_downtrend": 0.20},
    "mean_rev":    {"risk_on_uptrend": 0.30, "neutral_range": 0.85, "risk_off_downtrend": 0.45},
    "pair":        {"risk_on_uptrend": 0.50, "neutral_range": 0.90, "risk_off_downtrend": 0.60},
    "defensive":   {"risk_on_uptrend": 0.15, "neutral_range": 0.50, "risk_off_downtrend": 0.90},
    "earnings":    {"risk_on_uptrend": 0.55, "neutral_range": 0.55, "risk_off_downtrend": 0.20},
    "london_bkout":{"risk_on_uptrend": 0.65, "neutral_range": 0.60, "risk_off_downtrend": 0.15},
    "dual_thrust": {"risk_on_uptrend": 0.70, "neutral_range": 0.65, "risk_off_downtrend": 0.10},
}


class OpportunityEnsembler:
    """
    Quantamental ensemble ranker.

    Scores TradeRecommendation objects using a multi-factor model
    grounded in positive net expectancy, then applies suppression gates.

    Usage:
        ensembler = OpportunityEnsembler()
        ranked = ensembler.rank_opportunities(recs, regime_state)
    """

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        min_score: float = MIN_COMPOSITE_SCORE,
        min_rr: float = MIN_RISK_REWARD,
        min_pwin: float = MIN_WIN_PROBABILITY,
    ):
        self.weights  = weights or DEFAULT_WEIGHTS.copy()
        self.min_score = min_score
        self.min_rr    = min_rr
        self.min_pwin  = min_pwin
        self._validate_weights()
        logger.debug(
            "OpportunityEnsembler init: min_score=%.2f, min_rr=%.1f, min_pwin=%.2f",
            min_score, min_rr, min_pwin,
        )

    # ── Main API ──────────────────────────────────────────────────

    def rank_opportunities(
        self,
        recommendations: List["TradeRecommendation"],
        regime: Dict[str, Any],
        strategy_health: Optional[Dict[str, float]] = None,
    ) -> List["TradeRecommendation"]:
        """Score, suppress, and rank a list of TradeRecommendation objects.

        Args:
            recommendations: list of TradeRecommendation from signal pipeline
            regime: regime state dict (should_trade, entropy, risk_on_uptrend, …)
            strategy_health: optional {strategy_id: 0-1} from leaderboard

        Returns:
            Sorted list, tradeable first, then by composite_score desc.
        """
        if not recommendations:
            return []

        scored = [
            self._score_one(rec, regime, strategy_health or {})
            for rec in recommendations
        ]
        scored = self._apply_suppression(scored, regime)
        scored.sort(
            key=lambda r: (r.trade_decision, r.composite_score),
            reverse=True,
        )
        n_trade = sum(1 for r in scored if r.trade_decision)
        logger.info(
            "OpportunityEnsembler: ranked %d, tradeable %d",
            len(scored), n_trade,
        )
        return scored

    def score_recommendation(
        self,
        rec: "TradeRecommendation",
        regime: Dict[str, Any],
        strategy_health: Optional[Dict[str, float]] = None,
    ) -> "TradeRecommendation":
        """Score a single recommendation (convenience method)."""
        scored = self._score_one(rec, regime, strategy_health or {})
        return self._apply_suppression([scored], regime)[0]

    # ── Scoring ───────────────────────────────────────────────────

    def _score_one(
        self,
        rec: "TradeRecommendation",
        regime: Dict[str, Any],
        strategy_health: Dict[str, float],
    ) -> "TradeRecommendation":
        """Compute all score components and set composite_score."""
        w = self.weights

        # ── Component 1: Net Expectancy (Mercer/Berlekamp principle) ──
        # net_exp = p(win) * avg_win_R − p(loss) * avg_loss_R
        # Positive net_exp = positive edge = worth taking.
        pwin = self._get_pwin(rec)
        avg_win_r  = max(rec.risk_reward_ratio, 1.0)   # normalise: 1R stop
        avg_loss_r = 1.0
        net_exp    = pwin * avg_win_r - (1.0 - pwin) * avg_loss_r
        # Normalise to 0–1 using a 5R scale (net_exp=5R → score=1.0)
        # net_exp can range from about -1 (worst) to +5 (excellent)
        # score = (net_exp + 1) / 6  → -1R=0.0, 0R=0.167, 5R=1.0
        net_exp_norm = max(0.0, min(1.0, (net_exp + 1.0) / 6.0))

        # ── Component 2: Momentum (MACD + Heikin-Ashi) ──
        # From je-suis-tm #1 and #3: momentum alignment boosts conviction
        momentum = self._score_momentum(rec)

        # ── Component 3: Timing (BB position + Dual Thrust) ──
        # From je-suis-tm #9 and #7: buy at right point in volatility cycle
        timing = self._score_timing(rec)

        # ── Component 4: Regime Fit ──
        # Strategy must match regime — wrong strategy in wrong regime
        # destroys edge regardless of signal quality
        regime_fit = self._score_regime_fit(rec, regime)

        # ── Component 5: RS Rank (Mansfield RS) ──
        # Only trade leaders, avoid laggards — je-suis-tm pair trading insight
        rs_rank = self._score_rs_rank(rec)

        # ── Component 6: Strategy Health ──
        # Bayesian win rate from leaderboard
        health = strategy_health.get(rec.strategy_id, rec.strategy_health or 0.5)
        health = max(0.0, min(1.0, health))

        # ── Composite ──
        composite = (
            w["net_expectancy"] * net_exp_norm
            + w["momentum"]     * momentum
            + w["timing"]       * timing
            + w["regime_fit"]   * regime_fit
            + w["rs_rank"]      * rs_rank
            + w["health"]       * health
        )
        composite = round(max(0.0, min(1.0, composite)), 4)

        # Populate
        rec.composite_score = composite
        rec.trade_decision  = True   # suppression pass follows
        rec.suppression_reason = ""
        rec.components = {
            "net_expectancy":  round(net_exp_norm, 3),
            "net_exp_raw_R":   round(net_exp, 3),
            "pwin":            round(pwin, 3),
            "rr":              round(avg_win_r, 2),
            "momentum":        round(momentum, 3),
            "timing":          round(timing, 3),
            "regime_fit":      round(regime_fit, 3),
            "rs_rank":         round(rs_rank, 3),
            "health":          round(health, 3),
        }
        return rec

    # ── Component helpers ─────────────────────────────────────────

    def _get_pwin(self, rec: "TradeRecommendation") -> float:
        """Best available win-probability estimate."""
        # Priority: calibrated edge > ml_win_prob > raw confidence
        if rec.edge_p_t1 > 0:
            return min(1.0, rec.edge_p_t1)
        if rec.ml_win_probability > 0:
            return min(1.0, rec.ml_win_probability)
        return min(1.0, max(0.0, rec.signal_confidence / 100.0))

    def _score_momentum(self, rec: "TradeRecommendation") -> float:
        """MACD + Heikin-Ashi momentum alignment score (0–1).

        je-suis-tm #1 (MACD): momentum divergence confirms direction.
        je-suis-tm #3 (Heikin-Ashi): noise-filtered candle direction.

        Scoring:
          Both agree with signal direction → 1.0
          One agrees → 0.6
          Neither agrees → 0.3
          Both conflict → 0.0
        """
        direction = (rec.direction or "LONG").upper()
        meta = rec.metadata or {}

        macd_hist = meta.get("macd_hist", None)
        ha_direction = meta.get("ha_direction", None)  # "UP" / "DOWN"

        signals_aligned = 0
        signals_available = 0

        if macd_hist is not None:
            signals_available += 1
            macd_bullish = float(macd_hist) > 0
            if direction == "LONG" and macd_bullish:
                signals_aligned += 1
            elif direction == "SHORT" and not macd_bullish:
                signals_aligned += 1

        if ha_direction is not None:
            signals_available += 1
            ha_bullish = str(ha_direction).upper() == "UP"
            if direction == "LONG" and ha_bullish:
                signals_aligned += 1
            elif direction == "SHORT" and not ha_bullish:
                signals_aligned += 1

        if signals_available == 0:
            # No momentum data: use timing_score from signal as proxy
            return min(1.0, max(0.0, rec.timing_score))

        ratio = signals_aligned / signals_available
        # Map: 0 → 0.1, 0.5 → 0.6, 1.0 → 1.0
        return 0.1 + 0.9 * ratio

    def _score_timing(self, rec: "TradeRecommendation") -> float:
        """Bollinger Band position + Dual Thrust timing quality (0–1).

        je-suis-tm #9 (BB): buy near lower band (mean-reversion) or
          just after upper-band breakout (momentum walk).
        je-suis-tm #7 (Dual Thrust): price above upper thrust = confirmed breakout.

        BB scoring for LONG:
          Near lower band (bb_pct_b < 0.25):  0.80  — mean-reversion entry
          Mid-band (0.25–0.75):               0.55  — neutral
          Near upper band (bb_pct_b > 0.75):  0.70  — momentum breakout
          BB contracted (width < 0.05):       +0.15 bonus — coil before expansion

        Dual Thrust bonus: price above upper threshold = extra 0.10
        """
        direction = (rec.direction or "LONG").upper()
        meta = rec.metadata or {}

        bb_pct_b   = meta.get("bb_pct_b", 0.5)
        bb_contracted = meta.get("bb_contracted", False)
        dual_thrust_break = meta.get("dual_thrust_upper_break", False)  # for LONG
        bb_pct_b = float(bb_pct_b)

        if direction == "LONG":
            if bb_pct_b < 0.25:
                base = 0.80  # near lower band — mean-reversion zone
            elif bb_pct_b > 0.75:
                base = 0.70  # upper-band walk — momentum zone
            else:
                base = 0.55
        else:  # SHORT
            if bb_pct_b > 0.75:
                base = 0.80  # near upper band — mean-reversion short zone
            elif bb_pct_b < 0.25:
                base = 0.70  # lower-band walk — momentum short zone
            else:
                base = 0.55

        bonus = 0.0
        if bb_contracted:
            bonus += 0.15   # coiled spring — breakout expected
        if dual_thrust_break:
            bonus += 0.10   # confirmed Dual Thrust breakout

        return min(1.0, base + bonus)

    def _score_regime_fit(
        self,
        rec: "TradeRecommendation",
        regime: Dict[str, Any],
    ) -> float:
        """Regime × strategy affinity (0–1).

        Strategies have different edge in different regimes.
        e.g. momentum strategies need risk_on_uptrend to work;
             mean reversion works best in sideways (neutral_range).
        """
        strat = (rec.strategy_id or "").lower()
        risk_on  = float(regime.get("risk_on_uptrend", 0.33))
        neutral  = float(regime.get("neutral_range", 0.33))
        risk_off = float(regime.get("risk_off_downtrend", 0.33))

        # Find matching strategy family
        family = self._resolve_strategy_family(strat)
        affinity = STRATEGY_REGIME_AFFINITY.get(family, {})

        if not affinity:
            # Unknown strategy: conservative neutral score
            return 0.40

        fit = (
            affinity.get("risk_on_uptrend", 0.5)    * risk_on
            + affinity.get("neutral_range", 0.5)    * neutral
            + affinity.get("risk_off_downtrend", 0.5) * risk_off
        )
        return round(max(0.0, min(1.0, fit)), 3)

    def _score_rs_rank(self, rec: "TradeRecommendation") -> float:
        """Mansfield RS vs benchmark score (0–1).

        Inspired by je-suis-tm pair trading: always long the stronger
        asset relative to its benchmark.

        rs_status mapping:
          LEADER  → 1.00
          STRONG  → 0.75
          NEUTRAL → 0.50
          WEAK    → 0.25
          LAGGARD → 0.10
        """
        meta = rec.metadata or {}
        rs_status = meta.get("rs_status", "").upper()
        rs_composite = float(meta.get("rs_composite", 100.0))

        status_map = {
            "LEADER":  1.00,
            "STRONG":  0.75,
            "NEUTRAL": 0.50,
            "WEAK":    0.25,
            "LAGGARD": 0.10,
        }
        if rs_status in status_map:
            return status_map[rs_status]

        # Fall back to numeric rs_composite (100 = neutral)
        return max(0.0, min(1.0, (rs_composite - 50.0) / 200.0 + 0.25))

    # ── Suppression gates ─────────────────────────────────────────

    def _apply_suppression(
        self,
        recs: List["TradeRecommendation"],
        regime: Dict[str, Any],
    ) -> List["TradeRecommendation"]:
        """Apply suppression gates. Sets trade_decision=False when failing."""
        should_trade  = regime.get("should_trade", True)
        no_trade_rsn  = regime.get("no_trade_reason", "")
        entropy       = float(regime.get("entropy", 0.0))

        for rec in recs:
            # Gate 1: regime-level no-trade (VIX crisis, choppy, etc.)
            if not should_trade:
                self._suppress(rec, "regime_no_trade",
                    f"Regime gate: {no_trade_rsn or 'should_trade=False'}")
                continue

            # Gate 2: regime uncertainty too high (entropy > threshold)
            if entropy > MAX_REGIME_ENTROPY:
                self._suppress(rec, "high_entropy",
                    f"Regime entropy {entropy:.2f} > {MAX_REGIME_ENTROPY:.2f} — regime unclear")
                continue

            # Gate 3: net expectancy gate — no negative-EV trades
            pwin = rec.components.get("pwin", 0.5) if rec.components else 0.5
            rr   = rec.components.get("rr", 1.5)   if rec.components else 1.5
            net_exp = pwin * rr - (1.0 - pwin)
            if net_exp <= 0:
                self._suppress(rec, "negative_expectancy",
                    f"Net expectancy {net_exp:.3f}R ≤ 0 — no edge")
                continue

            # Gate 4: composite score below minimum
            if rec.composite_score < self.min_score:
                self._suppress(rec, "below_min_score",
                    f"Composite {rec.composite_score:.3f} < {self.min_score:.3f}")
                continue

            # Gate 5: win probability too low
            if pwin < self.min_pwin:
                self._suppress(rec, "low_pwin",
                    f"Win probability {pwin:.1%} < {self.min_pwin:.1%} minimum")
                continue

            # Gate 6: R:R gate for TRADE conviction
            action = getattr(rec, "action_state", "WATCH") or "WATCH"
            if action == "TRADE" and rec.risk_reward_ratio < self.min_rr:
                self._suppress(rec, "rr_too_low",
                    f"R:R {rec.risk_reward_ratio:.1f} < {self.min_rr:.1f} for TRADE")
                continue

            # All gates passed
            rec.trade_decision = True

        return recs

    @staticmethod
    def _suppress(
        rec: "TradeRecommendation",
        reason: str,
        why: str,
    ) -> None:
        rec.trade_decision     = False
        rec.suppression_reason = reason
        rec.why_not_trade      = why

    # ── Utilities ─────────────────────────────────────────────────

    @staticmethod
    def _resolve_strategy_family(strategy_id: str) -> str:
        """Map strategy_id to a family key in STRATEGY_REGIME_AFFINITY."""
        s = strategy_id.lower()
        for family in STRATEGY_REGIME_AFFINITY:
            if family in s:
                return family
        # Keyword fallbacks
        if any(k in s for k in ("macd", "trend", "ema_cross")):
            return "momentum"
        if any(k in s for k in ("bb", "bollinger", "range", "channel")):
            return "mean_rev"
        if any(k in s for k in ("vcp", "cup", "handle")):
            return "vcp"
        if any(k in s for k in ("earning", "catalyst")):
            return "earnings"
        return "swing"   # default family

    def _validate_weights(self):
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "OpportunityEnsembler weights sum to %.4f, expected 1.0; normalising",
                total,
            )
            self.weights = {k: v / total for k, v in self.weights.items()}

    def get_weight_summary(self) -> Dict[str, float]:
        """Return current weights (useful for dashboard display)."""
        return {k: round(v, 4) for k, v in self.weights.items()}


# ── CLI smoke test ────────────────────────────────────────────────

if __name__ == "__main__":
    print("OpportunityEnsembler: quantamental scoring engine loaded")
    e = OpportunityEnsembler()
    print(f"  weights: {e.get_weight_summary()}")
    print(f"  min_score={e.min_score}, min_rr={e.min_rr}, min_pwin={e.min_pwin}")
