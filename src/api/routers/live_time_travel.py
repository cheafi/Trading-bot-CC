"""Live time-travel historical replay endpoint."""

from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.api.live_analytics import compute_4layer_confidence, run_expert_council
from src.api.technical_indicators import compute_indicators as _compute_indicators
from src.core.risk_limits import SIGNAL_THRESHOLDS

router = APIRouter(prefix="/api/live", tags=["live"])


@router.post("/time-travel")
async def live_time_travel(
    request: Request,
    ticker: str = Query(..., description="Stock symbol"),
    target_date: str = Query(
        ..., description="Target date YYYY-MM-DD — what would the system suggest?"
    ),
    strategy: str = Query(
        "all", description="momentum / breakout / swing / mean_reversion / all"
    ),
):
    """
    Phase 7: Time Travel — go back to any date and see what the system
    would have recommended. Includes:
    - Regime detection as of that date
    - 4-layer confidence (Thesis / Timing / Execution / Data)
    - 7-member Expert Council
    - Strategy signals
    - What actually happened after (forward returns)
    """

    import numpy as np

    ticker = validate_ticker(ticker)

    # Parse target date
    try:
        from datetime import datetime as _dt

        tgt = _dt.strptime(target_date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(422, "Invalid date format. Use YYYY-MM-DD.")

    # Fetch enough history: ~2 years before target + after for forward returns
    mds = request.app.state.market_data
    try:
        hist = await mds.get_history(ticker, period="5y", interval="1d")
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch data for {ticker}: {e}")

    if hist is None or hist.empty or len(hist) < 50:
        raise HTTPException(404, f"Insufficient data for {ticker}")

    # Resolve columns
    c_col = "Close" if "Close" in hist.columns else "close"
    v_col = "Volume" if "Volume" in hist.columns else "volume"
    h_col = "High" if "High" in hist.columns else "high"
    l_col = "Low" if "Low" in hist.columns else "low"

    all_dates = hist.index
    # Find the target date index (nearest trading day)
    target_idx = None
    for j, d in enumerate(all_dates):
        if d.date() >= tgt:
            target_idx = j
            break
    if target_idx is None:
        target_idx = len(all_dates) - 1

    if target_idx < 200:
        raise HTTPException(
            400,
            f"Not enough history before {target_date}. Need 200+ trading days of prior data.",
        )

    actual_date = str(all_dates[target_idx].date())

    # Slice data up to target date (inclusive)
    close_all = hist[c_col].values.astype(float)
    volume_all = hist[v_col].values.astype(float)
    close = close_all[: target_idx + 1]
    volume = volume_all[: target_idx + 1]
    n = len(close)
    i = n - 1  # last bar = target date

    # ── Indicators (causal, no look-ahead bias) ──
    _ind = _compute_indicators(close, volume)
    sma20 = _ind["sma20"]
    sma50 = _ind["sma50"]
    sma200 = _ind["sma200"]
    rsi = _ind["rsi"]
    vol_ratio = _ind["vol_ratio"]
    atr_pct = _ind["atr_pct"]

    # ── Regime as of target date ──
    trending = bool(close[i] > sma50[i] and sma50[i] > sma200[i])
    if trending:
        regime_label = "UPTREND"
    elif close[i] < sma50[i] and sma50[i] < sma200[i]:
        regime_label = "DOWNTREND"
    else:
        regime_label = "SIDEWAYS"
    vol_regime = (
        "LOW" if atr_pct[i] < 0.015 else "HIGH" if atr_pct[i] > 0.035 else "NORMAL"
    )

    # ── 4-Layer Confidence ──
    confidence = compute_4layer_confidence(
        close,
        sma20,
        sma50,
        sma200,
        rsi,
        atr_pct,
        vol_ratio,
        i,
        volume,
        trending,
    )

    # ── Expert Council ──
    council = run_expert_council(
        close,
        sma20,
        sma50,
        sma200,
        rsi,
        vol_ratio,
        atr_pct,
        i,
        volume,
        trending,
        ticker=ticker,
    )

    # ── Strategy signals as of target date ──
    cur_atr = max(float(atr_pct[i]), 0.005)
    strategy_signals = {}
    _ST = SIGNAL_THRESHOLDS
    strats_to_check = (
        ["momentum", "breakout", "swing", "mean_reversion"]
        if strategy == "all"
        else [strategy]
    )
    for sid in strats_to_check:
        enter = False
        stop_pct = target_pct = 0.0
        max_hold = _ST.max_hold_mean_rev
        if sid == "momentum":
            enter = bool(
                close[i] > sma20[i] > sma50[i]
                and rsi[i] > _ST.rsi_momentum_low
                and rsi[i] < _ST.rsi_momentum_high
                and vol_ratio[i] > _ST.volume_confirmation
            )
            stop_pct = cur_atr * _ST.stop_atr_multiplier_momentum
            target_pct = _ST.target_trending if trending else _ST.target_normal
            max_hold = (
                _ST.max_hold_momentum_trending
                if trending
                else _ST.max_hold_momentum_normal
            )
        elif sid == "breakout":
            hi20 = float(np.max(close[max(0, i - 20) : i]))
            enter = bool(
                close[i] > hi20
                and vol_ratio[i] > _ST.volume_surge_threshold
                and close[i] > sma20[i]
            )
            stop_pct = cur_atr * _ST.stop_atr_multiplier_breakout
            target_pct = (
                _ST.target_breakout_trending if trending else _ST.target_breakout_normal
            )
            max_hold = (
                _ST.max_hold_breakout_trending
                if trending
                else _ST.max_hold_breakout_normal
            )
        elif sid == "mean_reversion":
            enter = bool(
                rsi[i] < _ST.rsi_oversold
                and close[i] < sma20[i] * (1 - _ST.mean_rev_sma_distance)
                and vol_ratio[i] > _ST.volume_confirmation
            )
            stop_pct = cur_atr * _ST.stop_atr_multiplier_mean_rev
            target_pct = cur_atr * 3
            max_hold = _ST.max_hold_mean_rev
        elif sid == "swing":
            enter = bool(
                rsi[i] < _ST.rsi_swing_entry
                and close[i] > sma50[i] * (1 - _ST.swing_sma_distance)
                and (close[i] > sma20[i] or close[i - 1] < sma20[i - 1])
                and close[i] > close[i - 1]
            )
            stop_pct = cur_atr * _ST.stop_atr_multiplier_swing
            target_pct = (
                _ST.target_swing_trending if trending else _ST.target_swing_normal
            )
            max_hold = (
                _ST.max_hold_swing_trending if trending else _ST.max_hold_swing_normal
            )
        entry_price = round(float(close[i]), 2)
        strategy_signals[sid] = {
            "triggered": enter,
            "entry_price": entry_price,
            "stop_loss": round(entry_price * (1 - stop_pct), 2),
            "target": round(entry_price * (1 + target_pct), 2),
            "stop_pct": round(stop_pct * 100, 2),
            "target_pct": round(target_pct * 100, 2),
            "max_hold_days": max_hold,
        }

    # ── Final action (arbiter) — v2 with decision_tier + consensus ──
    council_members = council["members"]
    council_summary = council["summary"]
    active_signals = [s for s, v in strategy_signals.items() if v["triggered"]]
    avg_council = council_summary["avg_score"]
    consensus = council_summary["consensus"]
    disagreement = council_summary["disagreement"]

    # Use calibrated decision_tier from confidence engine
    tier = confidence.get("decision_tier", "WATCH")
    should_trade = confidence.get("should_trade", True)

    if not should_trade:
        final_action = "NO TRADE — ABSTAIN"
        final_reason = confidence.get("abstain_reason", "Abstention rule triggered")
    elif tier == "HEDGE" or "bearish" in consensus:
        final_action = "NO TRADE"
        final_reason = f"Decision tier={tier}, council consensus={consensus}"
    elif tier == "NO_TRADE":
        final_action = "NO TRADE"
        final_reason = "Confidence below threshold"
    elif not active_signals:
        final_action = "WATCH"
        final_reason = "No strategy triggered — monitor for setup"
    elif disagreement > 25:
        # Experts disagree strongly — reduce size regardless of tier
        final_action = "BUY — PILOT SIZE"
        final_reason = f"{tier} tier but high expert disagreement ({disagreement:.0f})"
    elif tier == "STRONG_BUY" and "bullish" in consensus:
        final_action = "BUY — FULL SIZE"
        final_reason = (
            f"Strong conviction + council {consensus} + {', '.join(active_signals)}"
        )
    elif tier == "BUY_SMALL":
        final_action = "BUY — NORMAL SIZE"
        final_reason = f"Good confidence + {', '.join(active_signals)} triggered"
    elif tier == "WATCH":
        final_action = "BUY — PILOT SIZE"
        final_reason = "Moderate confidence — small position only"
    else:
        final_action = "WATCH"
        final_reason = f"Mixed signals — tier={tier}, consensus={consensus}"

    # ── Forward returns (what actually happened) ──
    forward = {}
    for days in [1, 5, 10, 20, 60]:
        fwd_idx = target_idx + days
        if fwd_idx < len(close_all):
            fwd_return = (
                (close_all[fwd_idx] - close_all[target_idx])
                / close_all[target_idx]
                * 100
            )
            forward[f"{days}d"] = {
                "return_pct": round(float(fwd_return), 2),
                "price": round(float(close_all[fwd_idx]), 2),
                "date": (
                    str(all_dates[fwd_idx].date()) if fwd_idx < len(all_dates) else None
                ),
            }

    # ── Price context ──
    pct_from_high = round(
        (close[i] - max(close[max(0, i - 252) :]))
        / max(close[max(0, i - 252) :])
        * 100,
        2,
    )
    pct_from_low = round(
        (close[i] - min(close[max(0, i - 252) :]))
        / min(close[max(0, i - 252) :])
        * 100,
        2,
    )

    return sanitize_for_json(
        {
            "ticker": ticker,
            "target_date": actual_date,
            "price": round(float(close[i]), 2),
            "regime": {
                "label": regime_label,
                "trending": trending,
                "volatility": vol_regime,
                "rsi": round(float(rsi[i]), 1),
                "atr_pct": round(float(atr_pct[i]) * 100, 2),
                "vol_ratio": round(float(vol_ratio[i]), 2),
                "sma20": round(float(sma20[i]), 2),
                "sma50": round(float(sma50[i]), 2),
                "sma200": round(float(sma200[i]), 2),
            },
            "confidence": confidence,
            "expert_council": council_members,
            "council_summary": council_summary,
            "council_avg": avg_council,
            "strategy_signals": strategy_signals,
            "final_action": final_action,
            "final_reason": final_reason,
            "forward_returns": forward,
            "price_context": {
                "pct_from_52w_high": pct_from_high,
                "pct_from_52w_low": pct_from_low,
            },
            "bars_before": target_idx,
            "bars_after": len(close_all) - target_idx - 1,
            "trust": {
                "mode": "TIME_TRAVEL",
                "source": "yfinance_historical",
                "note": "Historical replay — shows what system would have suggested on this date. NOT a live recommendation.",
                "data_points": n,
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
        }
    )
