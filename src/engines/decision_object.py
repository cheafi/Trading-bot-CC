"""
Decision Object — Sprint 73
==============================
Single structured decision object used by ALL surfaces:
  dashboard, Discord, journal, backtest, portfolio review.

Every trading decision flows through this schema.
No more scatter — one object, many consumers.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class DecisionObject:
    """
    The atomic unit of every trade decision.
    Produced by the decision pipeline, consumed by all surfaces.
    """

    # ── Identity ──
    ticker: str = ""
    date: str = ""
    generated_at: str = ""

    # ── Macro Context ──
    macro_regime: str = "UNKNOWN"  # RISK_ON / RISK_OFF / NEUTRAL
    vix_regime: str = "NORMAL"  # NORMAL / ELEVATED / RISK_OFF

    # ── Sector Context ──
    sector: str = "—"
    sector_etf: str = "SPY"
    sector_type: str = "—"  # HIGH_GROWTH / CYCLICAL / DEFENSIVE / THEME
    sector_stage: str = "—"  # EARLY_LEADER / CROWDED / ROTATION_OUT / FRESH_BREAKOUT

    # ── Strategy Classification ──
    strategy_style: str = (
        "—"  # PULLBACK_TREND / BREAKOUT / MEAN_REVERT / GAP_CONTINUATION
    )
    setup_type: str = "—"  # from brief/scanner

    # ── RS Context ──
    rs_rank: int = 0  # 1 = strongest
    rs_composite: float = 100.0
    rs_state: str = "NEUTRAL"  # EMERGING / CONFIRMED_LEADER / FADING / etc.
    leadership: str = "NEUTRAL"  # LEADER / FOLLOWER / LAGGARD

    # ── Confidence Breakdown (0-100 each) ──
    thesis_confidence: int = 50  # Is the thesis sound?
    timing_confidence: int = 50  # Is the timing right?
    execution_confidence: int = 50  # Can we execute cleanly?
    data_confidence: int = 50  # Is data reliable?
    final_confidence: int = 50  # Weighted composite

    # ── Action ──
    action: str = "WAIT"  # TRADE / WATCH / WAIT / NO_TRADE / REJECT
    conviction_tier: str = "WAIT"  # TRADE / LEADER / WATCH / WAIT

    # ── Levels ──
    entry_zone: str = "—"
    invalidation: str = "—"
    stop: Optional[float] = None
    target: Optional[float] = None
    rr_ratio: Optional[float] = None
    take_profit_logic: str = "Trail after +1R"

    # ── Reasoning ──
    why_now: str = "—"
    why_not_stronger: str = "—"
    contradictions: List[str] = field(default_factory=list)
    note: str = "—"

    # ── Peer Context ──
    peer_comparison: List[str] = field(default_factory=list)
    stronger_peer: str = ""
    weaker_peer: str = ""

    # ── Portfolio Fit ──
    portfolio_fit: str = "—"  # ALLOWED / ALLOWED_SMALL / BLOCKED / CORRELATED
    portfolio_gate_reason: str = ""

    # ── Data Quality ──
    synthetic: bool = False

    # ── Provenance & Enrichment ──
    signal_source: str = "brief"  # "brief"|"scanner"|"expert_council"|"manual"
    trust_level: str = "UNVERIFIED"  # "LIVE"|"CACHED"|"SYNTHETIC"|"UNVERIFIED"
    data_freshness_minutes: int = -1
    benchmark_compare: str = "—"  # e.g. "SPY +2.1% vs ticker +4.3% (63d)"
    mtf_confluence_score: Optional[float] = None
    execution_cost_bps: Optional[float] = None
    calibrated_confidence: Optional[float] = None

    def compute_final_confidence(self) -> int:
        """Weighted confidence: thesis heaviest, data as penalty."""
        self.final_confidence = int(
            0.35 * self.thesis_confidence
            + 0.25 * self.timing_confidence
            + 0.25 * self.execution_confidence
            + 0.15 * self.data_confidence
        )
        return self.final_confidence

    def derive_action(self) -> str:
        """Derive action from confidence + regime gate."""
        fc = self.final_confidence
        if self.macro_regime == "RISK_OFF" or self.vix_regime == "RISK_OFF":
            self.action = "NO_TRADE"
        elif fc >= 75 and self.rs_state in ("CONFIRMED_LEADER", "EMERGING"):
            self.action = "TRADE"
        elif fc >= 60:
            self.action = "WATCH"
        elif fc >= 40:
            self.action = "WAIT"
        else:
            self.action = "REJECT"
        return self.action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "date": self.date,
            "generated_at": self.generated_at,
            # Macro
            "macro_regime": self.macro_regime,
            "vix_regime": self.vix_regime,
            # Sector
            "sector": self.sector,
            "sector_etf": self.sector_etf,
            "sector_type": self.sector_type,
            "sector_stage": self.sector_stage,
            # Strategy
            "strategy_style": self.strategy_style,
            "setup_type": self.setup_type,
            # RS
            "rs_rank": self.rs_rank,
            "rs_composite": self.rs_composite,
            "rs_state": self.rs_state,
            "leadership": self.leadership,
            # Confidence
            "thesis_confidence": self.thesis_confidence,
            "timing_confidence": self.timing_confidence,
            "execution_confidence": self.execution_confidence,
            "data_confidence": self.data_confidence,
            "final_confidence": self.final_confidence,
            # Action
            "action": self.action,
            "conviction_tier": self.conviction_tier,
            # Levels
            "entry_zone": self.entry_zone,
            "invalidation": self.invalidation,
            "stop": self.stop,
            "target": self.target,
            "rr_ratio": self.rr_ratio,
            "take_profit_logic": self.take_profit_logic,
            # Reasoning
            "why_now": self.why_now,
            "why_not_stronger": self.why_not_stronger,
            "contradictions": self.contradictions,
            "note": self.note,
            # Peers
            "peer_comparison": self.peer_comparison,
            "stronger_peer": self.stronger_peer,
            "weaker_peer": self.weaker_peer,
            # Portfolio
            "portfolio_fit": self.portfolio_fit,
            "portfolio_gate_reason": self.portfolio_gate_reason,
            # Meta
            "synthetic": self.synthetic,
            # Provenance & Enrichment
            "signal_source": self.signal_source,
            "trust_level": self.trust_level,
            "data_freshness_minutes": self.data_freshness_minutes,
            "benchmark_compare": self.benchmark_compare,
            "mtf_confluence_score": self.mtf_confluence_score,
            "execution_cost_bps": self.execution_cost_bps,
            "calibrated_confidence": self.calibrated_confidence,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "DecisionObject":
        obj = cls()
        for k, v in d.items():
            if hasattr(obj, k):
                setattr(obj, k, v)
        return obj

    @classmethod
    def from_pipeline_result(
        cls, r: Any, regime: Optional[Dict[str, Any]] = None
    ) -> "DecisionObject":
        """
        Build a DecisionObject from a SectorPipeline PipelineResult.
        This is the canonical adapter — replaces manual r.signal.get() dict assembly.
        """
        sig = r.signal if hasattr(r, "signal") else {}
        conf = r.confidence if hasattr(r, "confidence") else None
        dec = r.decision if hasattr(r, "decision") else None
        sec = r.sector if hasattr(r, "sector") else None
        expl = r.explanation if hasattr(r, "explanation") else None
        fit = r.fit if hasattr(r, "fit") else None
        ranking = r.ranking if hasattr(r, "ranking") else None

        regime = regime or {}
        is_synthetic = sig.get("synthetic", False) or regime.get("synthetic", False)
        trust = "SYNTHETIC" if is_synthetic else "LIVE"

        obj = cls(
            ticker=sig.get("ticker", ""),
            date=sig.get("date", ""),
            generated_at=datetime.now(timezone.utc).isoformat() + "Z",
            macro_regime=(
                "RISK_ON"
                if regime.get("trend", "") in ("BULL", "UPTREND")
                else "RISK_OFF" if regime.get("vix", 0) > 28 else "NEUTRAL"
            ),
            vix_regime=(
                "RISK_OFF"
                if regime.get("vix", 0) > 28
                else "ELEVATED" if regime.get("vix", 0) > 20 else "NORMAL"
            ),
            sector=sec.sector_bucket.value if sec else "—",
            sector_type=sec.sector_bucket.value if sec else "—",
            sector_stage=sec.sector_stage.value if sec else "—",
            strategy_style=sig.get("strategy", "—"),
            setup_type=sig.get("setup", sig.get("strategy", "—")),
            thesis_confidence=int(conf.thesis * 100) if conf else 50,
            timing_confidence=int(conf.timing * 100) if conf else 50,
            execution_confidence=int(conf.execution * 100) if conf else 50,
            data_confidence=int(conf.data * 100) if conf else 50,
            final_confidence=int(conf.final * 100) if conf else 50,
            action=dec.action if dec else "WAIT",
            conviction_tier=(
                "TRADE"
                if fit and fit.final_score >= 8
                else (
                    "LEADER"
                    if fit and fit.final_score >= 6
                    else "WATCH" if fit and fit.final_score >= 3 else "WAIT"
                )
            ),
            entry_zone=str(sig.get("entry", "—")),
            invalidation=str(sig.get("stop", "—")),
            stop=sig.get("stop"),
            target=sig.get("target"),
            rr_ratio=sig.get("risk_reward"),
            why_now=expl.why_now if expl else "—",
            why_not_stronger=expl.why_not_stronger if expl else "—",
            note=sig.get("note", sig.get("thesis", "—")),
            synthetic=is_synthetic,
            signal_source="scanner" if sig.get("scanner_hit") else "brief",
            trust_level=trust,
            data_freshness_minutes=sig.get("data_freshness_minutes", -1),
            mtf_confluence_score=sig.get("mtf_confluence_score"),
            execution_cost_bps=sig.get("execution_cost_bps"),
            calibrated_confidence=sig.get("calibrated_confidence"),
        )
        # Set leadership from leader_status if present
        if sec and hasattr(sec, "leader_status"):
            obj.leadership = sec.leader_status.value
        # Set RS composite if present on signal
        if sig.get("rs_composite"):
            obj.rs_composite = sig["rs_composite"]
        # Ranking
        if ranking:
            obj.rs_rank = getattr(ranking, "discovery_rank", 0) or 0
        return obj


# ── Decision Pipeline ────────────────────────────────────────────────────────


class DecisionPipeline:
    """
    Macro → Sector → RS → Setup → Risk → Portfolio Gate → Decision Object.

    This is the "decision graph" — not multi-agent chat,
    but a clear, ordered, auditable pipeline.
    """

    def build(self, ticker: str) -> DecisionObject:
        """Run the full pipeline for a single ticker."""
        d = DecisionObject(
            ticker=ticker.upper(),
            generated_at=datetime.now(timezone.utc).isoformat() + "Z",
        )

        # Node 1: Macro regime
        self._macro_node(d)
        # Node 2: Sector classification
        self._sector_node(d)
        # Node 3: RS ranking
        self._rs_node(d)
        # Node 4: Setup / signal context
        self._setup_node(d)
        # Node 5: Confidence scoring
        self._confidence_node(d)
        # Node 6: Levels (entry / stop / target)
        self._levels_node(d)
        # Node 7: Reasoning
        self._reasoning_node(d)
        # Node 8: Peer comparison
        self._peer_node(d)
        # Node 9: Portfolio gate
        self._portfolio_gate_node(d)
        # Node 10: Final action
        d.compute_final_confidence()
        d.derive_action()

        return d

    def build_batch(self, tickers: List[str]) -> List[DecisionObject]:
        """Run pipeline for multiple tickers."""
        return [self.build(t) for t in tickers]

    # ── Pipeline Nodes ───────────────────────────────────────────────────

    def _macro_node(self, d: DecisionObject) -> None:
        """Inject macro regime context."""
        try:
            from src.services.regime_service import RegimeService

            regime = RegimeService.get()
            trend = regime.get("trend", "SIDEWAYS")
            vix_regime = regime.get("vix_regime", "NORMAL")
            d.macro_regime = (
                "RISK_ON"
                if trend in ("BULL", "UPTREND") and vix_regime != "RISK_OFF"
                else (
                    "RISK_OFF"
                    if vix_regime == "RISK_OFF" or trend == "BEAR"
                    else "NEUTRAL"
                )
            )
            d.vix_regime = vix_regime
            d.synthetic = regime.get("synthetic", False)
            d.date = regime.get("date", "")
            d.trust_level = "SYNTHETIC" if d.synthetic else "LIVE"
        except Exception as e:
            logger.debug("[Pipeline] macro_node: %s", e)

    def _sector_node(self, d: DecisionObject) -> None:
        """Classify sector and sector stage."""
        from src.engines.rs_hub import _get_sector, _get_sector_etf

        d.sector = _get_sector(d.ticker)
        d.sector_etf = _get_sector_etf(d.ticker)

        # Sector type classification
        growth_sectors = {"Technology", "Communication", "Consumer Discretionary"}
        defensive = {"Utilities", "Consumer Staples", "Healthcare"}
        cyclical = {"Financials", "Industrials", "Materials", "Energy"}

        if d.sector in growth_sectors:
            d.sector_type = "HIGH_GROWTH"
        elif d.sector in defensive:
            d.sector_type = "DEFENSIVE"
        elif d.sector in cyclical:
            d.sector_type = "CYCLICAL"
        else:
            d.sector_type = "OTHER"

        # Sector stage — derived from sector ETF RS vs SPY
        try:
            from src.services.rs_data_service import (
                compute_rs_date_aligned,
                fetch_single,
            )

            etf_closes = fetch_single(d.sector_etf)
            spy_closes = fetch_single("SPY")
            if (
                etf_closes is not None
                and spy_closes is not None
                and len(etf_closes) >= 63
            ):
                rs = compute_rs_date_aligned(etf_closes, spy_closes)
                comp = rs["rs_composite"]
                slope = rs["rs_slope"]
                if comp > 110 and slope > 0:
                    d.sector_stage = "EARLY_LEADER"
                elif comp > 110 and slope <= 0:
                    d.sector_stage = "CROWDED"
                elif comp < 95 and slope < 0:
                    d.sector_stage = "ROTATION_OUT"
                elif comp > 100 and slope > 0.5:
                    d.sector_stage = "FRESH_BREAKOUT"
                else:
                    d.sector_stage = "NEUTRAL"
            else:
                d.sector_stage = "NEUTRAL"
        except Exception:
            d.sector_stage = "NEUTRAL"

    def _rs_node(self, d: DecisionObject) -> None:
        """Inject RS ranking data."""
        try:
            from src.services.rs_data_service import (
                compute_rs_date_aligned,
                fetch_single,
            )
            from src.engines.rs_hub import classify_rs_state

            ticker_closes = fetch_single(d.ticker)
            spy_closes = fetch_single("SPY")
            if (
                ticker_closes is not None
                and spy_closes is not None
                and len(ticker_closes) >= 22
            ):
                rs_data = compute_rs_date_aligned(ticker_closes, spy_closes)
                d.rs_composite = rs_data["rs_composite"]
                d.rs_state = classify_rs_state(
                    rs_data["rs_composite"],
                    rs_data["rs_slope"],
                    rs_data["rs_1m"],
                    rs_data["rs_3m"],
                )
                # Leadership classification
                from src.engines.rs_hub import classify_leadership

                d.leadership = classify_leadership(d.rs_composite, 100.0)
            else:
                d.rs_composite = 100.0
                d.rs_state = "NEUTRAL"
                d.leadership = "NEUTRAL"
        except Exception as e:
            logger.debug("[Pipeline] rs_node: %s", e)

    def _setup_node(self, d: DecisionObject) -> None:
        """Inject signal/setup context from brief data."""
        try:
            from src.services.brief_data_service import find_signal

            signal, section = find_signal(d.ticker)

            if signal:
                d.signal_source = "brief"
                d.setup_type = signal.get("setup", signal.get("strategy", "—"))
                d.note = signal.get("note", signal.get("thesis", "—"))
                score = signal.get("score", 0)
                d.conviction_tier = (
                    "TRADE"
                    if score >= 8
                    else "LEADER" if score >= 6 else "WATCH" if score >= 3 else "WAIT"
                )

                indicators = signal.get("indicators") or {}
                rsi = indicators.get("rsi")

                # Thesis confidence from score
                d.thesis_confidence = min(int(score * 10), 100) if score else 30

                # Timing from RSI
                if rsi and 45 <= rsi <= 70:
                    d.timing_confidence = 75
                elif rsi and 35 <= rsi <= 75:
                    d.timing_confidence = 55
                else:
                    d.timing_confidence = 35

                # Execution from volume/MA
                volume_ok = (indicators.get("volume_ratio", 1.0) or 1.0) >= 1.2
                above_ma = indicators.get("above_ma50", True)
                d.execution_confidence = (
                    80 if volume_ok and above_ma else 55 if above_ma else 35
                )

                # Data confidence
                d.data_confidence = 40 if d.synthetic else 85
        except Exception as e:
            logger.debug("[Pipeline] setup_node: %s", e)

    def _confidence_node(self, d: DecisionObject) -> None:
        """Adjust confidence based on cross-checks."""
        # RS boost/penalty
        if d.rs_state in ("CONFIRMED_LEADER", "EMERGING"):
            d.thesis_confidence = min(100, d.thesis_confidence + 10)
        elif d.rs_state in ("FADING", "BROKEN", "LAGGARD"):
            d.thesis_confidence = max(0, d.thesis_confidence - 15)

        # Regime penalty
        if d.macro_regime == "RISK_OFF":
            d.timing_confidence = max(0, d.timing_confidence - 20)

    def _levels_node(self, d: DecisionObject) -> None:
        """Inject entry/stop/target from signal data."""
        try:
            from src.services.brief_data_service import find_signal

            signal, _ = find_signal(d.ticker)
            if signal:
                entry = signal.get("entry")
                stop = signal.get("stop")
                target = signal.get("target")
                d.entry_zone = str(entry) if entry else "—"
                d.invalidation = str(stop) if stop else "—"
                d.stop = stop
                d.target = target
                if entry and stop and target:
                    risk = abs(entry - stop)
                    reward = abs(target - entry)
                    d.rr_ratio = round(reward / risk, 2) if risk > 0 else None
        except Exception as e:
            logger.debug("[Pipeline] levels_node: %s", e)

    def _reasoning_node(self, d: DecisionObject) -> None:
        """Generate why_now, why_not_stronger, contradictions."""
        reasons = []
        contras = []

        # Why now
        if d.rs_state == "EMERGING":
            reasons.append("RS turning positive — early leadership signal")
        elif d.rs_state == "CONFIRMED_LEADER":
            reasons.append("Sustained RS leadership above benchmark")
        if d.macro_regime == "RISK_ON":
            reasons.append("Macro regime supports risk-taking")
        if d.timing_confidence >= 70:
            reasons.append("RSI in optimal entry zone")

        d.why_now = "; ".join(reasons) if reasons else "No strong catalyst identified"

        # Why not stronger
        weak = []
        if d.timing_confidence < 50:
            weak.append("Timing score below threshold")
        if d.rs_state in ("NEUTRAL", "LAGGARD"):
            weak.append("RS not confirming leadership")
        if d.macro_regime == "NEUTRAL":
            weak.append("Macro regime is uncertain")
        if d.data_confidence < 60:
            weak.append("Data quality concern (may be synthetic)")

        d.why_not_stronger = "; ".join(weak) if weak else "No major weakness identified"

        # Contradictions
        if d.macro_regime == "RISK_OFF" and d.thesis_confidence > 60:
            contras.append("Strong thesis but macro is risk-off")
        if d.rs_state in ("FADING", "BROKEN") and d.conviction_tier in (
            "TRADE",
            "LEADER",
        ):
            contras.append("High conviction but RS is deteriorating")
        if d.execution_confidence < 40 and d.thesis_confidence > 70:
            contras.append("Strong thesis but poor execution conditions")

        d.contradictions = contras

    def _peer_node(self, d: DecisionObject) -> None:
        """Inject peer comparison context."""
        try:
            from src.engines.peer_comparison import PeerEngine

            engine = PeerEngine()
            peers = engine.get_sector_peers(d.ticker, limit=4)
            d.peer_comparison = [p["ticker"] for p in peers]
            if peers:
                d.stronger_peer = (
                    peers[0].get("ticker", "")
                    if peers[0].get("rs_composite", 0) > d.rs_composite
                    else ""
                )
                d.weaker_peer = peers[-1].get("ticker", "") if len(peers) > 1 else ""
        except Exception as e:
            logger.debug("[Pipeline] peer_node: %s", e)

    def _portfolio_gate_node(self, d: DecisionObject) -> None:
        """Check portfolio fit against current holdings and policy."""
        try:
            # Compute interim confidence for gate check
            interim_conf = d.compute_final_confidence()

            if d.macro_regime == "RISK_OFF":
                d.portfolio_fit = "BLOCKED"
                d.portfolio_gate_reason = "Macro regime is risk-off"
            elif d.rs_state in ("BROKEN", "LAGGARD"):
                d.portfolio_fit = "BLOCKED"
                d.portfolio_gate_reason = "RS below threshold"
            elif interim_conf < 50:
                d.portfolio_fit = "BLOCKED"
                d.portfolio_gate_reason = f"Confidence {interim_conf} below minimum"
            elif d.sector_stage == "ROTATION_OUT":
                d.portfolio_fit = "ALLOWED_SMALL"
                d.portfolio_gate_reason = "Sector rotating out — reduce size"
            else:
                d.portfolio_fit = "ALLOWED"
                d.portfolio_gate_reason = ""
        except Exception as e:
            logger.debug("[Pipeline] portfolio_gate: %s", e)
            d.portfolio_fit = "BLOCKED"
            d.portfolio_gate_reason = f"Gate error: {e}"
