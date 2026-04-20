"""Sprint 49-53 intelligence endpoints — extracted from main.py."""
from __future__ import annotations

from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse

from src.engines.confidence_calibrator import ConfidenceCalibrator
from src.engines.correlation_risk import CorrelationRiskEngine
from src.engines.cross_asset_monitor import CrossAssetMonitor
from src.engines.decision_journal import DecisionJournal
from src.engines.expert_tracker import ExpertTracker
from src.engines.learning_loop import LearningLoopPipeline
from src.engines.market_intel import MarketIntelEngine
from src.engines.portfolio_risk_budget import PortfolioRiskBudget
from src.engines.position_sizer import PositionSizer
from src.engines.professional_kpi import ProfessionalKPI
from src.engines.regime_filter import RegimeFilter
from src.engines.risk_scorecard import RiskScorecardEngine
from src.engines.signal_decay import SignalDecayTracker
from src.engines.trade_gate import TradeGate
from src.engines.watchlist_intel import WatchlistIntelEngine
from src.engines.meta_ensemble import MetaEnsemble
from src.core.trust_metadata import FreshnessLevel

router = APIRouter()

# ── Singletons ──────────────────────────────────────────────────
_signal_decay = SignalDecayTracker()
_learning_loop = LearningLoopPipeline()
_meta_ensemble: MetaEnsemble = MetaEnsemble()
_position_sizer = PositionSizer()
_correlation_risk = CorrelationRiskEngine()
_trade_gate = TradeGate()
_decision_journal = DecisionJournal()
_market_intel = MarketIntelEngine()
_risk_scorecard = RiskScorecardEngine()
_watchlist_intel = WatchlistIntelEngine()
_expert_tracker = ExpertTracker()
_regime_filter = RegimeFilter()
_cross_asset_monitor = CrossAssetMonitor()
_confidence_calibrator = ConfidenceCalibrator()
_portfolio_risk_budget = PortfolioRiskBudget()
_professional_kpi = ProfessionalKPI()


def _get_verify_api_key():
    """Import verify_api_key lazily to avoid circular imports."""
    from src.api.main import verify_api_key
    return verify_api_key


@router.get("/api/v6/signal-decay", tags=["analytics"],
         summary="Signal freshness tracking")
async def signal_decay_summary():
    return _signal_decay.summary()


@router.get("/api/v6/signal-decay/active", tags=["analytics"])
async def signal_decay_active():
    return {"signals": _signal_decay.active_signals()}


@router.post("/api/v6/learning-loop/record", tags=["analytics"],
          summary="Record closed trade for learning")
async def learning_loop_record(request: Request):
    body = await request.json()
    result = _learning_loop.record_closed_trade(
        ticker=body["ticker"],
        direction=body.get("direction", "LONG"),
        entry_price=body["entry_price"],
        exit_price=body["exit_price"],
        entry_time=body.get("entry_time", ""),
        exit_time=body.get("exit_time", ""),
        strategy_id=body.get("strategy_id", "manual"),
        regime_at_entry=body.get("regime", ""),
        setup_grade=body.get("setup_grade", "C"),
        component_scores=body.get("component_scores"),
    )
    return result


@router.get("/api/v6/learning-loop", tags=["analytics"],
         summary="Learning loop summary")
async def learning_loop_summary():
    return _learning_loop.summary()


@router.get("/api/v6/learning-loop/trades", tags=["analytics"])
async def learning_loop_trades(limit: int = 50):
    return {"trades": _learning_loop.get_trade_log(limit)}


@router.get("/api/v6/meta-ensemble", tags=["analytics"])
async def api_meta_ensemble():
    """MetaEnsemble state: learned weights, sample count, training status."""
    global _meta_ensemble
    state = _meta_ensemble.get_state()
    learned = _meta_ensemble.get_learned_weights()
    return {
        "is_trained": _meta_ensemble.is_trained,
        "sample_count": _meta_ensemble.sample_count,
        "min_samples_required": 30,
        "learned_weights": learned,
        "state": state.to_dict(),
    }


@router.post("/api/v6/meta-ensemble/record", tags=["analytics"])
async def api_meta_ensemble_record(request: Request):
    """Record a closed trade outcome for meta-ensemble learning."""
    global _meta_ensemble
    body = await request.json()
    components = body.get("components", {})
    pnl_pct = body.get("pnl_pct", 0.0)
    r_multiple = body.get("r_multiple", 0.0)
    regime = body.get("regime", "unknown")
    strategy = body.get("strategy", "unknown")
    _meta_ensemble.record_outcome(
        components=components, pnl_pct=pnl_pct,
        r_multiple=r_multiple, regime_label=regime, strategy_id=strategy,
    )
    return {
        "recorded": True,
        "sample_count": _meta_ensemble.sample_count,
        "is_trained": _meta_ensemble.is_trained,
    }


@router.get("/api/v6/trust-card/{ticker}", tags=["analytics"])
async def api_trust_card(ticker: str):
    """Trust metadata card — badge, freshness, model version."""
    ticker = ticker.upper()
    meta = TrustMetadata.for_entry(
        badge=TrustBadge.PAPER,
        source_count=3,
        model_version=MODEL_VERSION,
    )
    return {
        "ticker": ticker,
        "trust": meta.to_dict(),
        "header": meta.header_line(),
        "footer": meta.footer_line(),
    }


@router.get("/api/v6/model-version", tags=["analytics"])
async def api_model_version():
    """Current model version and trust badge defaults."""
    return {
        "model_version": MODEL_VERSION,
        "trust_badges": [b.value for b in TrustBadge],
        "freshness_levels": [f.value for f in FreshnessLevel],
    }



# ══════════════════════════════════════════════════════════════════════
# Sprint 50 — Position Sizing, Concentration Risk, Trade Gate, Decision Journal
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v6/position-size", tags=["v6-risk"])
async def position_size_endpoint(
    ticker: str = "AAPL",
    price: float = 150.0,
    stop_price: float = 145.0,
    method: str = "atr_fixed_risk",
    _: bool = Depends(_get_verify_api_key()),
):
    """Calculate recommended position size for a trade."""
    result = _position_sizer.size_position(
        ticker=ticker,
        price=price,
        stop_price=stop_price,
        method=method,
    )
    return {
        "ticker": result.ticker,
        "shares": result.shares,
        "dollar_amount": result.dollar_amount,
        "position_pct": result.position_pct,
        "risk_per_share": result.risk_per_share,
        "total_risk": result.total_risk,
        "risk_pct_of_equity": result.risk_pct_of_equity,
        "method": result.method,
        "notes": result.notes,
        "sizer_config": _position_sizer.summary(),
    }


@router.get("/api/v6/concentration-risk", tags=["v6-risk"])
async def concentration_risk_endpoint(
    _: bool = Depends(_get_verify_api_key()),
):
    """Analyse portfolio concentration and correlation risk."""
    holdings = _user_portfolio.get("holdings", [])
    if not holdings:
        return {
            "status": "no_portfolio",
            "message": "Import portfolio first via POST /api/portfolio/import",
        }
    return _correlation_risk.summary(holdings)


@router.get("/api/v6/trade-gate", tags=["v6-risk"])
async def trade_gate_endpoint(
    ticker: str = "AAPL",
    vix: float = 20.0,
    drawdown_pct: float = 0.0,
    open_positions: int = 0,
    portfolio_heat_pct: float = 0.0,
    regime: str = "UNKNOWN",
    _: bool = Depends(_get_verify_api_key()),
):
    """Evaluate pre-trade gate: should we even be trading right now?"""
    result = _trade_gate.evaluate(
        current_drawdown_pct=drawdown_pct,
        open_positions=open_positions,
        portfolio_heat_pct=portfolio_heat_pct,
        vix=vix,
        regime=regime,
        ticker=ticker,
    )
    return result.to_dict()


@router.get("/api/v6/decision-journal", tags=["v6-risk"])
async def decision_journal_endpoint(
    ticker: str = "",
    _: bool = Depends(_get_verify_api_key()),
):
    """View decision journal — audit trail for all signal decisions."""
    if ticker:
        entries = _decision_journal.by_ticker(ticker)
        return {"ticker": ticker, "entries": entries, "count": len(entries)}
    return _decision_journal.summary()


@router.post("/api/v6/decision-journal/record", tags=["v6-risk"])
async def decision_journal_record(
    ticker: str = "AAPL",
    decision: str = "PASS",
    price: float = 0.0,
    regime: str = "",
    score: float = 0.0,
    confidence: float = 0.0,
    setup_grade: str = "",
    _: bool = Depends(_get_verify_api_key()),
):
    """Manually record a decision in the journal (for testing/integration)."""
    entry = _decision_journal.record(
        ticker=ticker,
        decision=decision,
        price=price,
        regime=regime,
        score=score,
        confidence=confidence,
        setup_grade=setup_grade,
    )
    return {"recorded": True, "entry_id": entry.entry_id}



# ══════════════════════════════════════════════════════════════════════
# Sprint 51 — Market Intel, Risk Scorecard, Watchlist Intelligence
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v6/market-intel", tags=["v6-intel"])
async def market_intel_endpoint(
    request: Request,
    ticker: str = "AAPL",
    _: bool = Depends(_get_verify_api_key()),
):
    """Multi-dimensional market intelligence for a ticker."""
    try:
        from src.api.main import live_quote
        from src.api.main import live_quote
        q_resp = await live_quote(ticker)
        q = q_resp.get("quote", {})
        price = q.get("price", 0)
        rsi = q.get("rsi", 50)
        vol_ratio = q.get("volume_ratio", 1.0)
        above_sma20 = q.get("above_sma20", False)
        above_sma50 = q.get("above_sma50", False)
        change_pct = q.get("change_pct", 0)
        sb = request.app.state.scoreboard
        regime = sb.regime_label if hasattr(sb, "regime_label") else "UNKNOWN"
        report = _market_intel.analyse(
            ticker=ticker, price=price, rsi=rsi,
            volume_ratio=vol_ratio, above_sma20=above_sma20,
            above_sma50=above_sma50, regime=regime,
            change_pct=change_pct,
        )
        return {
            "ticker": report.ticker,
            "fusion_score": report.fusion_score,
            "fusion_confidence": report.fusion_confidence,
            "dominant_theme": report.dominant_theme,
            "agreement_ratio": report.agreement_ratio,
            "signal_count": report.signal_count,
            "bullish_signals": report.bullish_signals,
            "bearish_signals": report.bearish_signals,
            "neutral_signals": report.neutral_signals,
            "generated_at": report.generated_at,
        }
    except Exception as exc:
        return {
            "ticker": ticker,
            "error": str(exc),
            "fusion_score": 0,
            "signal_count": 0,
        }


@router.get("/api/v6/risk-scorecard", tags=["v6-risk"])
async def risk_scorecard_endpoint(
    drawdown_pct: float = 0.0,
    portfolio_heat_pct: float = 0.0,
    open_positions: int = 0,
    hhi_score: float = 0.0,
    concentration_grade: str = "A",
    vix: float = 20.0,
    regime: str = "UNKNOWN",
    _: bool = Depends(_get_verify_api_key()),
):
    """Unified risk scorecard combining all risk dimensions."""
    result = _risk_scorecard.evaluate(
        drawdown_pct=drawdown_pct,
        portfolio_heat_pct=portfolio_heat_pct,
        open_positions=open_positions,
        hhi_score=hhi_score,
        concentration_grade=concentration_grade,
        vix=vix,
        regime=regime,
    )
    return result.to_dict()


@router.get("/api/v6/watchlist", tags=["v6-intel"])
async def watchlist_endpoint(
    top_n: int = 20,
    urgency: str = "",
    _: bool = Depends(_get_verify_api_key()),
):
    """Get ranked intelligent watchlist."""
    items = _watchlist_intel.ranked(
        top_n=top_n,
        urgency_filter=urgency if urgency else None,
    )
    stats = _watchlist_intel.stats()
    return {"items": items, "stats": stats}


@router.post("/api/v6/watchlist/add", tags=["v6-intel"])
async def watchlist_add_endpoint(
    ticker: str = "AAPL",
    score: float = 0.5,
    direction: str = "LONG",
    setup_grade: str = "C",
    why_now: str = "",
    regime: str = "UNKNOWN",
    price: float = 0.0,
    _: bool = Depends(_get_verify_api_key()),
):
    """Add a ticker to the intelligent watchlist."""
    item = _watchlist_intel.add(
        ticker=ticker, score=score, direction=direction,
        setup_grade=setup_grade, why_now=why_now,
        regime=regime, price=price,
    )
    return {"added": True, "ticker": ticker, "urgency": item.urgency}


@router.delete("/api/v6/watchlist/{ticker}", tags=["v6-intel"])
async def watchlist_remove_endpoint(
    ticker: str,
    _: bool = Depends(_get_verify_api_key()),
):
    """Remove a ticker from the watchlist."""
    removed = _watchlist_intel.remove(ticker)
    return {"removed": removed, "ticker": ticker}



# ══════════════════════════════════════════════════════════════════════
# Sprint 52 — Expert Tracker, Regime Filter, Cross-Asset, Calibration
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v6/expert-tracker", tags=["v6-intel"])
async def expert_tracker_endpoint(
    _: bool = Depends(_get_verify_api_key()),
):
    """View expert track-record leaderboard and weights."""
    return _expert_tracker.summary()


@router.post("/api/v6/expert-tracker/record", tags=["v6-intel"])
async def expert_tracker_record(
    expert_role: str = "trend_expert",
    predicted_direction: str = "LONG",
    actual_direction: str = "LONG",
    regime: str = "ALL",
    _: bool = Depends(_get_verify_api_key()),
):
    """Record an expert prediction outcome for track-record tracking."""
    rec = _expert_tracker.record_outcome(
        expert_role=expert_role,
        predicted_direction=predicted_direction,
        actual_direction=actual_direction,
        regime=regime,
    )
    if rec is None:
        return {"recorded": False}
    return {"recorded": True, "expert": rec.to_dict()}


@router.get("/api/v6/regime-filter", tags=["v6-intel"])
async def regime_filter_endpoint(
    score: float = 0.6,
    setup_grade: str = "B",
    regime: str = "SIDEWAYS",
    direction: str = "LONG",
    rsi: float = 50.0,
    _: bool = Depends(_get_verify_api_key()),
):
    """Evaluate whether a signal passes regime-adjusted quality filters."""
    result = _regime_filter.evaluate(
        score=score, setup_grade=setup_grade,
        regime=regime, direction=direction, rsi=rsi,
    )
    return result.to_dict()


@router.get("/api/v6/cross-asset", tags=["v6-intel"])
async def cross_asset_endpoint(
    vix: float = 20.0,
    spy_change_pct: float = 0.0,
    tlt_change_pct: float = 0.0,
    gld_change_pct: float = 0.0,
    iwm_change_pct: float = 0.0,
    dxy_change_pct: float = 0.0,
    breadth_pct: float = 50.0,
    _: bool = Depends(_get_verify_api_key()),
):
    """Cross-asset stress analysis and divergence detection."""
    report = _cross_asset_monitor.analyse(
        vix=vix, spy_change_pct=spy_change_pct,
        tlt_change_pct=tlt_change_pct,
        gld_change_pct=gld_change_pct,
        iwm_change_pct=iwm_change_pct,
        dxy_change_pct=dxy_change_pct,
        breadth_pct=breadth_pct,
    )
    return report.to_dict()


@router.get("/api/v6/confidence-calibration", tags=["v6-intel"])
async def confidence_calibration_endpoint(
    raw_confidence: float = 0.75,
    _: bool = Depends(_get_verify_api_key()),
):
    """Get calibrated confidence and calibration analysis."""
    calibrated = _confidence_calibrator.calibrate(raw_confidence)
    summary = _confidence_calibrator.summary()
    return {
        "raw_confidence": raw_confidence,
        "calibrated_confidence": calibrated,
        "calibration_status": summary,
    }



# ══════════════════════════════════════════════════════════════════════
# Sprint 53 — Portfolio Risk Budget, Professional KPI
# ══════════════════════════════════════════════════════════════════════


@router.get("/api/v6/portfolio-risk-budget", tags=["v6-intel"])
async def portfolio_risk_budget_endpoint(
    request: Request,
    _: bool = Depends(_get_verify_api_key()),
):
    """Portfolio-level risk budget check: exposure, concentration, heat."""
    # Build exposure from current positions (or empty if none)
    positions = getattr(request.app.state, "positions", [])
    equity = getattr(request.app.state, "account_value", 100_000)
    exposure = _portfolio_risk_budget.build_exposure(
        positions=positions, equity=equity
    )
    from src.api.main import _sanitize_for_json
    from src.api.main import _sanitize_for_json
    return _sanitize_for_json(exposure.to_dict())


@router.get("/api/v6/professional-kpi", tags=["v6-intel"])
async def professional_kpi_endpoint(
    _: bool = Depends(_get_verify_api_key()),
):
    """Professional trading KPI dashboard — institutional-grade metrics."""
    snapshot = _professional_kpi.compute()
    from src.api.main import _sanitize_for_json
    from src.api.main import _sanitize_for_json
    return _sanitize_for_json(snapshot.to_dict())


@router.post("/api/v6/professional-kpi/record-trade", tags=["v6-intel"])
async def professional_kpi_record_trade(
    pnl_pct: float = 0.0,
    r_multiple: float = 0.0,
    hold_hours: float = 0.0,
    _: bool = Depends(_get_verify_api_key()),
):
    """Record a trade outcome for KPI tracking."""
    _professional_kpi.record_trade(pnl_pct=pnl_pct, r_multiple=r_multiple, hold_hours=hold_hours)
    return {"recorded": True, "kpi": _professional_kpi.compute().to_dict()}


@router.post("/api/v6/professional-kpi/record-cycle", tags=["v6-intel"])
async def professional_kpi_record_cycle(
    traded: bool = True,
    _: bool = Depends(_get_verify_api_key()),
):
    """Record a screening cycle for funnel KPI tracking."""
    _professional_kpi.record_cycle(traded=traded)
    return {"recorded": True, "kpi": _professional_kpi.compute().to_dict()}

