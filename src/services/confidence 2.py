"""CC — 4-Layer Confidence Engine (extracted from src/api/main.py)."""
from src.core.risk_limits import RISK, SIGNAL_THRESHOLDS  # noqa

def compute_4layer_confidence(
    close,
    sma20,
    sma50,
    sma200,
    rsi,
    atr_pct,
    vol_ratio,
    idx,
    volume,
    regime_trending,
    days_to_earnings=None,
    data_freshness=1.0,
    # ── Phase 9 engine results (optional) ──
    structure_result=None,
    entry_quality_result=None,
    earnings_info=None,
    fundamentals_info=None,
    regime_label=None,
    ticker_sector=None,
) -> dict:
    """Compute 4-layer confidence: Thesis / Timing / Execution / Data.

    Returns dict with each layer 0-100, composite, grade, action.
    Phase 9 engines feed penalties/bonuses into layer scores.
    """
    import numpy as np

    i = idx
    # ── 1) Thesis Confidence ──
    thesis_factors = []
    # Trend alignment
    if close[i] > sma50[i] > sma200[i]:
        thesis_factors.append(("Strong uptrend (price > SMA50 > SMA200)", 25))
    elif close[i] > sma50[i]:
        thesis_factors.append(("Moderate uptrend (price > SMA50)", 15))
    elif close[i] < sma50[i] < sma200[i]:
        thesis_factors.append(("Downtrend (price < SMA50 < SMA200)", -10))
    else:
        thesis_factors.append(("Sideways / mixed trend", 5))
    # RSI regime
    if 40 < rsi[i] < SIGNAL_THRESHOLDS.rsi_near_overbought:
        thesis_factors.append(("RSI in healthy zone", 15))
    elif rsi[i] < SIGNAL_THRESHOLDS.rsi_oversold:
        thesis_factors.append(("RSI oversold — bounce potential", 10))
    elif rsi[i] > SIGNAL_THRESHOLDS.rsi_momentum_high:
        thesis_factors.append(("RSI overbought — caution", -5))
    else:
        thesis_factors.append(("RSI neutral", 5))
    # Volume confirmation
    if vol_ratio[i] > SIGNAL_THRESHOLDS.volume_surge_threshold:
        thesis_factors.append(
            (f"Volume surge (>{SIGNAL_THRESHOLDS.volume_surge_threshold}x avg)", 15)
        )
    elif vol_ratio[i] > SIGNAL_THRESHOLDS.volume_confirmation:
        thesis_factors.append(("Normal volume", 8))
    else:
        thesis_factors.append(("Below-avg volume", -3))
    # SMA slope (momentum)
    if i > 20 and sma20[i] > sma20[i - 10]:
        thesis_factors.append(("SMA20 rising", 10))
    elif i > 20:
        thesis_factors.append(("SMA20 falling", -5))
    thesis_score = max(0, min(100, 50 + sum(f[1] for f in thesis_factors)))

    # ── 2) Timing Confidence ──
    timing_factors = []
    # Distance from SMA20 (near = better timing)
    dist_sma20 = abs(close[i] - sma20[i]) / sma20[i] if sma20[i] > 0 else 0
    if dist_sma20 < 0.02:
        timing_factors.append(("Price near SMA20 support", 20))
    elif dist_sma20 < 0.05:
        timing_factors.append(("Moderate distance from SMA20", 10))
    else:
        timing_factors.append(("Extended from SMA20", -5))
    # ATR — not too volatile
    if atr_pct[i] < 0.02:
        timing_factors.append(("Low volatility — good for entry", 15))
    elif atr_pct[i] < 0.04:
        timing_factors.append(("Normal volatility", 10))
    else:
        timing_factors.append(("High volatility — wait for calm", -10))
    # Recent pullback (close dipped then recovered)
    if i > 5 and close[i] > close[i - 1] and close[i - 1] < close[i - 3]:
        timing_factors.append(("Pullback bounce pattern", 15))
    else:
        timing_factors.append(("No clear pullback entry", 0))
    # Event proximity
    if days_to_earnings is not None and days_to_earnings <= 3:
        timing_factors.append(("Earnings in ≤3 days — BLACKOUT", -25))
    elif days_to_earnings is not None and days_to_earnings <= 7:
        timing_factors.append(("Earnings within 7 days — caution", -10))
    timing_score = max(0, min(100, 50 + sum(f[1] for f in timing_factors)))

    # ── 3) Execution Confidence ──
    exec_factors = []
    # Volume / liquidity proxy
    avg_vol = float(np.mean(volume[max(0, i - 20) : i + 1])) if i > 0 else 0
    if avg_vol > 5_000_000:
        exec_factors.append(("High liquidity (>5M avg vol)", 25))
    elif avg_vol > 1_000_000:
        exec_factors.append(("Adequate liquidity (>1M)", 15))
    elif avg_vol > 100_000:
        exec_factors.append(("Low liquidity — wider spreads", 5))
    else:
        exec_factors.append(("Very low liquidity — risky", -15))
    # Price level (penny stock?)
    if close[i] > 20:
        exec_factors.append(("Price >$20 — normal spreads", 15))
    elif close[i] > 5:
        exec_factors.append(("Price $5-20 — moderate", 5))
    else:
        exec_factors.append(("Price <$5 — wide spreads likely", -10))
    exec_score = max(0, min(100, 50 + sum(f[1] for f in exec_factors)))

    # ── 4) Data Confidence ──
    data_factors = []
    bar_count = i + 1
    if bar_count >= 200:
        data_factors.append(("200+ bars of history — full indicators", 25))
    elif bar_count >= 50:
        data_factors.append(("50+ bars — basic indicators OK", 15))
    else:
        data_factors.append(("Limited history (<50 bars)", -10))
    if data_freshness >= 0.9:
        data_factors.append(("Fresh data", 15))
    elif data_freshness >= 0.5:
        data_factors.append(("Slightly stale data", 5))
    else:
        data_factors.append(("Stale data — low trust", -15))
    data_score = max(0, min(100, 50 + sum(f[1] for f in data_factors)))

    # ── Phase 9 Engine Adjustments ──
    p9_adjustments = []

    # Entry quality: REJECT verdict → execution penalty
    if entry_quality_result and isinstance(entry_quality_result, dict):
        eq_verdict = entry_quality_result.get("verdict", "").upper()
        eq_score_val = entry_quality_result.get("score", 50)
        if eq_verdict == "REJECT":
            exec_factors.append(("P9: Entry quality REJECT", -25))
            exec_score = max(0, exec_score - 25)
            p9_adjustments.append("entry_quality_reject")
        elif eq_verdict == "POOR" or eq_score_val < 35:
            exec_factors.append(("P9: Entry quality poor", -12))
            exec_score = max(0, exec_score - 12)
            p9_adjustments.append("entry_quality_poor")

    # Earnings blackout from Phase 9 EarningsCalendar
    if earnings_info and isinstance(earnings_info, dict):
        if earnings_info.get("in_blackout"):
            timing_factors.append(("P9: Earnings blackout period", -20))
            timing_score = max(0, timing_score - 20)
            p9_adjustments.append("earnings_blackout_p9")

    # Structure: extended from resistance → timing penalty
    if structure_result and isinstance(structure_result, dict):
        if structure_result.get("is_extended"):
            timing_factors.append(("P9: Price extended from structure", -15))
            timing_score = max(0, timing_score - 15)
            p9_adjustments.append("structure_extended")
        trend_q = structure_result.get("trend_quality", "")
        if trend_q and str(trend_q).upper() in ("WEAK", "POOR"):
            thesis_factors.append(("P9: Weak trend quality", -10))
            thesis_score = max(0, thesis_score - 10)
            p9_adjustments.append("weak_trend")

    # Fundamentals: low quality → thesis penalty
    if fundamentals_info and isinstance(fundamentals_info, dict):
        fq = fundamentals_info.get("quality")
        if fq is not None and fq < 40:
            thesis_factors.append((f"P9: Fundamental quality {fq}/100", -15))
            thesis_score = max(0, thesis_score - 15)
            p9_adjustments.append("weak_fundamentals")

    # Regime gating: CRISIS/RISK_OFF → suppress non-defensive
    if regime_label and str(regime_label).upper() in ("CRISIS", "RISK_OFF", "DOWNTREND"):
        defensive_sectors = {"utilities", "healthcare", "consumer_staples", "XLU", "XLV", "XLP"}
        is_defensive = ticker_sector and str(ticker_sector).lower() in defensive_sectors
        if not is_defensive:
            thesis_factors.append((f"P9: Regime {regime_label} — non-defensive", -15))
            thesis_score = max(0, thesis_score - 15)
            timing_factors.append((f"P9: Regime {regime_label} — adverse", -10))
            timing_score = max(0, timing_score - 10)
            p9_adjustments.append("adverse_regime")

    # ── Historical Analog: fetch similar cases and win rate ──
    try:
        from src.engines.historical_analog import analog_summary, find_similar_cases

        # Use strategy if available, else fallback
        strategy = None
        if structure_result and isinstance(structure_result, dict):
            strategy = structure_result.get("strategy")
        if not strategy:
            strategy = "momentum"  # fallback default
        regime_label_str = str(regime_label) if regime_label else ""
        cases = find_similar_cases(
            strategy=strategy,
            regime=regime_label_str,
            grade=str(grade) if "grade" in locals() else "",
            direction="LONG",
        )
        analog = analog_summary(cases)
        win_rate = analog.get("win_rate", 0)
        analog_count = analog.get("count", 0)
    except Exception as _analog_exc:
        analog = {"count": 0, "win_rate": 0, "message": "Analog lookup failed"}
        win_rate = 0
        analog_count = 0

    # ── Composite (blend with historical win rate if enough analogs) ──
    base_composite = (
        0.35 * thesis_score
        + 0.30 * timing_score
        + 0.20 * exec_score
        + 0.15 * data_score
    )
    composite = base_composite
    analog_weight = 0.20 if analog_count >= 5 else 0.10 if analog_count >= 2 else 0.0
    if analog_weight > 0:
        composite = (1 - analog_weight) * base_composite + analog_weight * win_rate
    composite = round(composite, 1)

    # Penalties
    penalties = []
    if days_to_earnings is not None and days_to_earnings <= 2:
        penalties.append("earnings_blackout")
        composite -= 15
    if atr_pct[i] > RISK.max_atr_pct_for_entry:
        penalties.append("extreme_volatility")
        composite -= 10
    composite = max(0, min(100, composite))

    if composite >= SIGNAL_THRESHOLDS.strong_buy_threshold:
        grade, action = "A", "Strong conviction — full size"
    elif composite >= SIGNAL_THRESHOLDS.buy_threshold:
        grade, action = "B", "Tradeable — normal size"
    elif composite >= SIGNAL_THRESHOLDS.watch_threshold:
        grade, action = "C", "Watch or pilot size only"
    else:
        grade, action = "D", "No Trade — conditions unfavorable"

    # ── 7-Tier Decision (P9: matches spec) ──
    # Trade / Watch / Wait / Hold / Reduce / Exit / No Trade
    if composite >= SIGNAL_THRESHOLDS.strong_buy_threshold and not penalties:
        decision_tier = "TRADE"
        sizing = "Full position" f" ({RISK.max_position_pct*100:.0f}%" " of portfolio)"
    elif composite >= SIGNAL_THRESHOLDS.buy_threshold:
        decision_tier = "TRADE"
        sizing = "Half position" f" ({RISK.max_position_pct*50:.1f}%" " of portfolio)"
    elif composite >= SIGNAL_THRESHOLDS.watch_threshold:
        decision_tier = "WATCH"
        sizing = "No position — watchlist only"
    elif composite >= 45:
        decision_tier = "WAIT"
        sizing = "Setup forming — not yet actionable"
    elif composite >= 40:
        decision_tier = "NO_TRADE"
        sizing = "Abstain — conditions unfavorable"
    else:
        decision_tier = "NO_TRADE"
        sizing = "Conditions hostile — stay flat"

    # ── Abstention Rule (P1: Confidence Calibration) ──
    ABSTENTION_THRESHOLD = SIGNAL_THRESHOLDS.abstention_threshold
    should_trade = (
        composite >= ABSTENTION_THRESHOLD and "earnings_blackout" not in penalties
    )
    abstain_reason = None
    if not should_trade:
        if "earnings_blackout" in penalties:
            abstain_reason = "Earnings blackout — too risky to enter"
        elif composite < ABSTENTION_THRESHOLD:
            abstain_reason = f"Confidence {composite:.0f} < {ABSTENTION_THRESHOLD} threshold — abstaining"

    # ── Structured Evidence (P1: Decision Output) ──
    reasons_for = [
        f[0] for f in thesis_factors + timing_factors + exec_factors if f[1] > 5
    ]
    reasons_against = [
        f[0]
        for f in thesis_factors + timing_factors + exec_factors + data_factors
        if f[1] < -3
    ]
    invalidation = []
    if close[i] > sma50[i]:
        invalidation.append(f"Break below SMA50 ({sma50[i]:.2f}) → thesis invalid")
    if close[i] > sma20[i]:
        invalidation.append(f"Close below SMA20 ({sma20[i]:.2f}) → timing fails")
    if atr_pct[i] > 0.03:
        invalidation.append(
            f"ATR expansion beyond {atr_pct[i]*1.5:.1%} → risk too high"
        )
    if not invalidation:
        invalidation.append("Broad market crash or sector-wide sell-off")

    # ── Confidence Decay (P1) ──
    # Signal age penalty: -2 points per day if data not refreshed
    confidence_decay_rate = 2.0  # points per day

    # ── Brier Score Tracking (P1: Calibration) ──
    # Predicted probability = composite / 100
    # Actual outcome collected post-trade for calibration
    calibration_meta = {
        "predicted_prob": round(composite / 100, 3),
        "confidence_bucket": (
            "high"
            if composite >= SIGNAL_THRESHOLDS.high_confidence_threshold
            else "medium" if composite >= SIGNAL_THRESHOLDS.watch_threshold else "low"
        ),
        "decay_rate_per_day": confidence_decay_rate,
        "abstention_threshold": ABSTENTION_THRESHOLD,
        "should_trade": should_trade,
        "note": "Brier score = mean((predicted_prob - actual_outcome)^2) — track post-trade",
    }

    return {
        "thesis": {"score": round(thesis_score, 1), "factors": thesis_factors},
        "timing": {"score": round(timing_score, 1), "factors": timing_factors},
        "execution": {"score": round(exec_score, 1), "factors": exec_factors},
        "data": {"score": round(data_score, 1), "factors": data_factors},
        "composite": round(composite, 1),
        "grade": grade,
        "action": action,
        "decision_tier": decision_tier,
        "sizing": sizing,
        "should_trade": should_trade,
        "abstain_reason": abstain_reason,
        "reasons_for": reasons_for[:5],
        "reasons_against": reasons_against[:5],
        "invalidation": invalidation[:4],
        "penalties": penalties,
        "p9_adjustments": p9_adjustments,
        "calibration": calibration_meta,
        "historical_analog": analog,
        "historical_win_rate": win_rate,
        "historical_analog_count": analog_count,
    }


