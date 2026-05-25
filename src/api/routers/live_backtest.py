"""Live backtest endpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query, Request

from src.api.deps import sanitize_for_json, validate_ticker
from src.api.technical_indicators import compute_indicators as _compute_indicators
from src.core.risk_limits import BACKTEST_DEFAULTS, RISK, SIGNAL_THRESHOLDS

router = APIRouter(prefix="/api/live", tags=["live"])


@router.post("/backtest")
async def live_backtest(
    request: Request,
    ticker: str = Query(..., description="Stock symbol"),
    strategy: str = Query(
        "all", description="swing / breakout / momentum / mean_reversion / all"
    ),
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    period: str = Query(
        "1y", description="Fallback period if no dates: 1mo 3mo 6mo 1y 2y 5y"
    ),
):
    """
    Phase 5: Production backtest engine with 5-year stress testing.

    Returns per-strategy metrics, market-event period breakdown,
    rolling performance, drawdown analysis, and regime-aware stats.
    Uses real yfinance data — NOT synthetic.
    """
    import asyncio

    import numpy as np

    ticker = validate_ticker(ticker)

    # Fetch historical data via MarketDataService
    mds = request.app.state.market_data
    try:
        if start_date and end_date:
            hist = await mds.get_history(ticker, period="5y", interval="1d")
            if hist is not None and not hist.empty:
                hist = hist.loc[start_date:end_date]
        else:
            hist = await mds.get_history(ticker, period=period, interval="1d")
    except Exception as e:
        raise HTTPException(400, f"Failed to fetch data for {ticker}: {e}")

    if hist is None or hist.empty or len(hist) < 30:
        raise HTTPException(400, f"Insufficient data for {ticker} (need 30+ bars)")

    close = hist["Close"].values
    volume = hist["Volume"].values
    dates_idx = hist.index

    # ── Market event detection (from price data, not hardcoded) ──
    def _detect_market_events(close_arr, dates) -> list:
        """Identify stress/recovery periods from price action alone.
        Returns list of {name, start, end, type, return_pct}."""
        n = len(close_arr)
        if n < 60:
            return []
        events = []
        # 1) Find all drawdown events > 10% from rolling 60-day peak
        peak = close_arr[0]
        dd_start = None
        for i in range(1, n):
            if close_arr[i] > peak:
                if dd_start is not None and peak > 0:
                    dd_pct = (close_arr[i - 1] - peak) / peak * 100
                    if dd_pct < -10:
                        events.append(
                            {
                                "name": f"Drawdown {dd_pct:.0f}%",
                                "start": str(dates[dd_start].date()),
                                "end": str(dates[i - 1].date()),
                                "start_idx": dd_start,
                                "end_idx": i - 1,
                                "type": "crash",
                                "return_pct": round(dd_pct, 2),
                            }
                        )
                    dd_start = None
                peak = close_arr[i]
            elif dd_start is None and (close_arr[i] - peak) / peak < -0.05:
                dd_start = i
        # Check if we ended in a drawdown
        if dd_start is not None and peak > 0:
            dd_pct = (close_arr[-1] - peak) / peak * 100
            if dd_pct < -10:
                events.append(
                    {
                        "name": f"Drawdown {dd_pct:.0f}%",
                        "start": str(dates[dd_start].date()),
                        "end": str(dates[-1].date()),
                        "start_idx": dd_start,
                        "end_idx": n - 1,
                        "type": "crash",
                        "return_pct": round(dd_pct, 2),
                    }
                )

        # 2) Find sustained rallies (>20% gain over 60+ days from trough)
        trough = close_arr[0]
        rally_start = 0
        for i in range(1, n):
            if close_arr[i] < trough:
                trough = close_arr[i]
                rally_start = i
            elif (
                trough > 0
                and (close_arr[i] - trough) / trough > 0.20
                and i - rally_start >= 60
            ):
                gain = (close_arr[i] - trough) / trough * 100
                events.append(
                    {
                        "name": f"Rally +{gain:.0f}%",
                        "start": str(dates[rally_start].date()),
                        "end": str(dates[i].date()),
                        "start_idx": rally_start,
                        "end_idx": i,
                        "type": "rally",
                        "return_pct": round(gain, 2),
                    }
                )
                trough = close_arr[i]
                rally_start = i

        # 3) Detect high-volatility regimes (20-day realized vol > 35% annualized)
        daily_ret = np.diff(close_arr) / close_arr[:-1]
        vol_window = 20
        if len(daily_ret) >= vol_window:
            rolling_vol = np.array(
                [
                    np.std(daily_ret[max(0, j - vol_window) : j]) * np.sqrt(252) * 100
                    for j in range(vol_window, len(daily_ret))
                ]
            )
            in_high_vol = False
            hv_start = 0
            for j in range(len(rolling_vol)):
                idx = j + vol_window
                if rolling_vol[j] > 35 and not in_high_vol:
                    in_high_vol = True
                    hv_start = idx
                elif rolling_vol[j] <= 30 and in_high_vol:
                    if idx - hv_start >= 10:
                        period_ret = (
                            (close_arr[idx] - close_arr[hv_start])
                            / close_arr[hv_start]
                            * 100
                        )
                        events.append(
                            {
                                "name": "High Vol Regime",
                                "start": str(dates[hv_start].date()),
                                "end": str(dates[idx].date()),
                                "start_idx": hv_start,
                                "end_idx": idx,
                                "type": "high_vol",
                                "return_pct": round(period_ret, 2),
                            }
                        )
                    in_high_vol = False

        # 4) Label known calendar events if they fall within the data range
        known_events = [
            ("COVID Crash", "2020-02-19", "2020-03-23"),
            ("COVID Recovery", "2020-03-24", "2020-08-31"),
            ("2022 Rate Hike Selloff", "2022-01-03", "2022-10-12"),
            ("2023 AI Rally", "2023-01-01", "2023-07-31"),
            ("2024 Election Ramp", "2024-10-01", "2024-12-31"),
        ]
        start_str = str(dates[0].date())
        end_str = str(dates[-1].date())
        for ename, estart, eend in known_events:
            if estart >= start_str and eend <= end_str:
                try:
                    mask = (dates >= estart) & (dates <= eend)
                    sel = close_arr[mask]
                    if len(sel) >= 5:
                        eret = (sel[-1] - sel[0]) / sel[0] * 100
                        sidx = int(np.argmax(mask))
                        eidx = sidx + len(sel) - 1
                        events.append(
                            {
                                "name": ename,
                                "start": estart,
                                "end": eend,
                                "start_idx": sidx,
                                "end_idx": eidx,
                                "type": "named",
                                "return_pct": round(eret, 2),
                            }
                        )
                except Exception:
                    pass

        # Deduplicate: keep named events over auto-detected if overlapping
        events.sort(key=lambda e: e["start"])
        return events

    # ── Strategy Engine v2 ── trailing stops, multi-position, regime-adaptive ──
    def _run_strategy(strat_id: str) -> dict:
        """Run a single strategy backtest – v2 competitive engine."""
        n = len(close)
        # ── Indicators (causal, no look-ahead bias) ──
        _ind = _compute_indicators(close, volume)
        sma20 = _ind["sma20"]
        sma50 = _ind["sma50"]
        sma200 = _ind["sma200"]
        rsi = _ind["rsi"]
        vol_ratio = _ind["vol_ratio"]
        atr_pct = _ind["atr_pct"]

        # ── Multi-position tracking ──
        MAX_POS = 3
        positions: list = (
            []
        )  # [{idx, price, trailing_high, stop_pct, target_pct, max_hold}]
        trades: list = []

        # ── Execution Cost Model (P1: Backtest Realism) ──
        COMMISSION_PER_SHARE = BACKTEST_DEFAULTS.commission_per_share
        MIN_COMMISSION = BACKTEST_DEFAULTS.min_commission
        SLIPPAGE_BASE_BPS = BACKTEST_DEFAULTS.slippage_base_bps
        ACCOUNT_SIZE = BACKTEST_DEFAULTS.account_size

        def _calc_slippage(bar_idx, entry=True):
            """ATR-based slippage: base + volume-scaled impact."""
            base = SLIPPAGE_BASE_BPS / 10_000
            vol_impact = 0.0
            if bar_idx > 0:
                avg_v = float(np.mean(volume[max(0, bar_idx - 20) : bar_idx + 1]))
                if avg_v > 0:
                    # Assume 1% of avg volume as our order → impact
                    vol_impact = 0.01 * close[bar_idx] / avg_v * 100
                    vol_impact = min(vol_impact, 0.002)  # cap at 20bps
            return base + vol_impact

        def _calc_commission(shares, price):
            """Per-share commission with minimum."""
            return max(MIN_COMMISSION, shares * COMMISSION_PER_SHARE)

        def _close_position(pos, bar_idx, reason):
            ep = pos["price"]
            xp = close[bar_idx]
            # Apply slippage on exit (sell at worse price)
            exit_slip = _calc_slippage(bar_idx, entry=False)
            xp_net = xp * (1 - exit_slip)
            # Commission (entry + exit)
            shares = int(ACCOUNT_SIZE * RISK.max_position_pct / ep)
            shares = max(1, shares)
            entry_comm = _calc_commission(shares, ep)
            exit_comm = _calc_commission(shares, xp_net)
            total_cost_pct = (entry_comm + exit_comm) / (shares * ep) * 100
            pnl_gross = (xp - ep) / ep
            pnl_net = (xp_net - pos["entry_cost"]) / pos[
                "entry_cost"
            ] - total_cost_pct / 100
            trades.append(
                {
                    "entry_idx": pos["idx"],
                    "exit_idx": bar_idx,
                    "entry_date": str(dates_idx[pos["idx"]].date()),
                    "exit_date": str(dates_idx[bar_idx].date()),
                    "entry_price": round(ep, 2),
                    "exit_price": round(xp, 2),
                    "pnl_pct": round(pnl_net * 100, 2),
                    "pnl_gross_pct": round(pnl_gross * 100, 2),
                    "costs_pct": round((pnl_gross - pnl_net) * 100, 2),
                    "reason": reason,
                    "hold_days": bar_idx - pos["idx"],
                }
            )

        for i in range(200, n):
            # ── Regime detection ──
            trending = close[i] > sma50[i] and sma50[i] > sma200[i]
            cur_atr = max(atr_pct[i], 0.005)

            # ── Exit logic (trailing + stop + target + time) ──
            still_open = []
            for pos in positions:
                ep = pos["price"]
                pnl_pct = (close[i] - ep) / ep
                hold_days = i - pos["idx"]
                # Update trailing high
                if close[i] > pos["trailing_high"]:
                    pos["trailing_high"] = close[i]
                # Trailing stop: activates when price > 50% of target
                trail_active = pnl_pct > pos["target_pct"] * 0.5
                if trail_active:
                    trail_stop = pos["trailing_high"] * (1 - pos["stop_pct"] * 0.6)
                    if close[i] < trail_stop:
                        _close_position(pos, i, "trailing")
                        continue
                # Hard stop
                if pnl_pct <= -pos["stop_pct"]:
                    _close_position(pos, i, "stop")
                    continue
                # Target hit
                if pnl_pct >= pos["target_pct"]:
                    _close_position(pos, i, "target")
                    continue
                # Time exit
                if hold_days >= pos["max_hold"]:
                    _close_position(pos, i, "time")
                    continue
                still_open.append(pos)
            positions = still_open

            # ── Entry logic (multi-position, proximity filter) ──
            if len(positions) >= MAX_POS:
                continue
            # Proximity filter – no new entry within 2% of existing position
            if any(abs(close[i] - p["price"]) / p["price"] < 0.02 for p in positions):
                continue

            enter = False
            if strat_id == "momentum":
                enter = (
                    close[i] > sma20[i] > sma50[i]
                    and rsi[i] > SIGNAL_THRESHOLDS.rsi_momentum_low
                    and rsi[i] < SIGNAL_THRESHOLDS.rsi_momentum_high
                    and vol_ratio[i] > SIGNAL_THRESHOLDS.volume_confirmation
                )
                stop_pct = cur_atr * SIGNAL_THRESHOLDS.stop_atr_multiplier_momentum
                target_pct = (
                    SIGNAL_THRESHOLDS.target_trending
                    if trending
                    else SIGNAL_THRESHOLDS.target_normal
                )
                max_hold = (
                    SIGNAL_THRESHOLDS.max_hold_momentum_trending
                    if trending
                    else SIGNAL_THRESHOLDS.max_hold_momentum_normal
                )
            elif strat_id == "breakout":
                hi20 = np.max(close[max(0, i - 20) : i])
                enter = (
                    close[i] > hi20
                    and vol_ratio[i] > SIGNAL_THRESHOLDS.volume_surge_threshold
                    and close[i] > sma20[i]
                )
                stop_pct = cur_atr * SIGNAL_THRESHOLDS.stop_atr_multiplier_breakout
                target_pct = (
                    SIGNAL_THRESHOLDS.target_breakout_trending
                    if trending
                    else SIGNAL_THRESHOLDS.target_breakout_normal
                )
                max_hold = (
                    SIGNAL_THRESHOLDS.max_hold_breakout_trending
                    if trending
                    else SIGNAL_THRESHOLDS.max_hold_breakout_normal
                )
            elif strat_id == "mean_reversion":
                enter = (
                    rsi[i] < SIGNAL_THRESHOLDS.rsi_oversold
                    and close[i]
                    < sma20[i] * (1 - SIGNAL_THRESHOLDS.mean_rev_sma_distance)
                    and vol_ratio[i] > SIGNAL_THRESHOLDS.volume_confirmation
                )
                stop_pct = cur_atr * SIGNAL_THRESHOLDS.stop_atr_multiplier_mean_rev
                target_pct = cur_atr * 3
                max_hold = SIGNAL_THRESHOLDS.max_hold_mean_rev
            elif strat_id == "swing":
                # Swing: oversold bounce near moving average support
                enter = (
                    rsi[i] < SIGNAL_THRESHOLDS.rsi_swing_entry
                    and close[i] > sma50[i] * (1 - SIGNAL_THRESHOLDS.swing_sma_distance)
                    and (close[i] > sma20[i] or close[i - 1] < sma20[i - 1])
                    and close[i] > close[i - 1]  # uptick confirmation
                )
                stop_pct = cur_atr * SIGNAL_THRESHOLDS.stop_atr_multiplier_swing
                target_pct = (
                    SIGNAL_THRESHOLDS.target_swing_trending
                    if trending
                    else SIGNAL_THRESHOLDS.target_swing_normal
                )
                max_hold = (
                    SIGNAL_THRESHOLDS.max_hold_swing_trending
                    if trending
                    else SIGNAL_THRESHOLDS.max_hold_swing_normal
                )

            if enter:
                # Apply entry slippage (buy at worse price)
                entry_slip = _calc_slippage(i, entry=True)
                entry_cost = close[i] * (1 + entry_slip)
                positions.append(
                    {
                        "idx": i,
                        "price": close[i],
                        "entry_cost": entry_cost,
                        "trailing_high": close[i],
                        "stop_pct": stop_pct,
                        "target_pct": target_pct,
                        "max_hold": max_hold,
                    }
                )

        # Close remaining positions at end
        for pos in positions:
            _close_position(pos, n - 1, "end")

        # ── Analytics ──
        returns = [t["pnl_pct"] / 100 for t in trades]
        gross_returns = [t["pnl_gross_pct"] / 100 for t in trades]
        total_trades = len(trades)
        winners = sum(1 for r in returns if r > 0)
        losers = total_trades - winners
        win_rate = (winners / total_trades * 100) if total_trades else 0
        avg_win = float(np.mean([r for r in returns if r > 0]) * 100) if winners else 0
        avg_loss_val = (
            float(np.mean([r for r in returns if r <= 0]) * 100) if losers else 0
        )
        total_costs = sum(t.get("costs_pct", 0) for t in trades)

        # Compounded return (equity curve) — net of costs
        equity = 1.0
        for r in returns:
            equity *= 1 + r
        compounded_return = (equity - 1) * 100
        # Gross compounded (for comparison)
        equity_gross = 1.0
        for r in gross_returns:
            equity_gross *= 1 + r
        compounded_gross = (equity_gross - 1) * 100
        simple_return = sum(returns) * 100

        # Sharpe
        if returns and np.std(returns) > 0:
            avg_hold = float(np.mean([t["hold_days"] for t in trades]))
            sharpe = float(
                np.mean(returns) / np.std(returns) * np.sqrt(252 / max(1, avg_hold))
            )
        else:
            sharpe = 0

        # Max drawdown on compounded equity curve
        eq_curve = []
        eq = 1.0
        for r in returns:
            eq *= 1 + r
            eq_curve.append(eq)
        eq_arr = np.array(eq_curve) if eq_curve else np.array([1])
        peak = np.maximum.accumulate(eq_arr)
        with np.errstate(divide="ignore", invalid="ignore"):
            dd = np.where(peak > 0, (eq_arr - peak) / peak, 0.0)
        max_dd = float(np.min(dd)) * 100 if len(dd) else 0

        # Profit factor
        gross_profit = sum(r for r in returns if r > 0)
        gross_loss = abs(sum(r for r in returns if r <= 0))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else 99

        # Rolling Sharpe
        rolling_sharpe = []
        window = min(20, max(5, total_trades // 5))
        for k in range(window, total_trades):
            chunk = returns[k - window : k]
            if np.std(chunk) > 0:
                rs_val = float(np.mean(chunk) / np.std(chunk) * np.sqrt(12))
            else:
                rs_val = 0
            rolling_sharpe.append({"trade": k, "sharpe": round(rs_val, 2)})

        # Exit reason breakdown
        exit_reasons = {}
        for t in trades:
            r = t["reason"]
            exit_reasons[r] = exit_reasons.get(r, 0) + 1

        # Yearly breakdown
        yearly = {}
        for t in trades:
            yr = t["entry_date"][:4]
            if yr not in yearly:
                yearly[yr] = {"trades": 0, "winners": 0, "return_pct": 0}
            yearly[yr]["trades"] += 1
            if t["pnl_pct"] > 0:
                yearly[yr]["winners"] += 1
            yearly[yr]["return_pct"] += t["pnl_pct"]
        for yr in yearly:
            yearly[yr]["return_pct"] = round(yearly[yr]["return_pct"], 2)
            yearly[yr]["win_rate"] = (
                round(yearly[yr]["winners"] / yearly[yr]["trades"] * 100, 1)
                if yearly[yr]["trades"] > 0
                else 0
            )

        return {
            "strategy": strat_id,
            "total_trades": total_trades,
            "winners": winners,
            "losers": losers,
            "win_rate": round(win_rate, 1),
            "total_return": round(compounded_return, 2),
            "gross_return": round(compounded_gross, 2),
            "total_costs_pct": round(total_costs, 2),
            "simple_return": round(simple_return, 2),
            "avg_win": round(avg_win, 2),
            "avg_loss": round(avg_loss_val, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "profit_factor": round(profit_factor, 2),
            "exit_reasons": exit_reasons,
            "yearly": yearly,
            "rolling_sharpe": rolling_sharpe[-50:],
            "trades": trades[-30:],
            "all_trades": trades,  # needed for event breakdown
            "cost_model": {
                "commission_per_share": COMMISSION_PER_SHARE,
                "min_commission": MIN_COMMISSION,
                "slippage_base_bps": SLIPPAGE_BASE_BPS,
                "note": "Net returns include commissions + ATR-based slippage",
            },
            "score": round(sharpe * 20 + win_rate * 0.5 + compounded_return * 0.3, 1),
        }

    # ── Run strategies ──
    strats_to_run = (
        ["swing", "breakout", "momentum", "mean_reversion"]
        if strategy == "all"
        else [strategy]
    )
    results = {}
    for sid in strats_to_run:
        try:
            results[sid] = await asyncio.to_thread(_run_strategy, sid)
        except Exception as e:
            results[sid] = {
                "strategy": sid,
                "error": str(e),
                "total_trades": 0,
                "score": 0,
            }

    ranked = sorted(results.values(), key=lambda x: x.get("score", 0), reverse=True)
    best = ranked[0]["strategy"] if ranked else "none"

    # ── Detect market events ──
    events = _detect_market_events(close, dates_idx)

    # ── Per-event performance for the best strategy ──
    event_performance = []
    best_trades = ranked[0].get("all_trades", []) if ranked else []
    for ev in events:
        ev_trades = [
            t
            for t in best_trades
            if t["entry_idx"] >= ev["start_idx"] and t["entry_idx"] <= ev["end_idx"]
        ]
        ev_win = sum(1 for t in ev_trades if t["pnl_pct"] > 0)
        ev_ret = sum(t["pnl_pct"] for t in ev_trades)
        event_performance.append(
            {
                "name": ev["name"],
                "type": ev["type"],
                "start": ev["start"],
                "end": ev["end"],
                "market_return": ev["return_pct"],
                "strategy_trades": len(ev_trades),
                "strategy_winners": ev_win,
                "strategy_return": round(ev_ret, 2),
                "win_rate": round(ev_win / len(ev_trades) * 100, 1) if ev_trades else 0,
                "alpha": round(ev_ret - ev["return_pct"], 2),
            }
        )

    # ── Buy-and-hold benchmark ──
    bh_return = ((close[-1] - close[0]) / close[0]) * 100

    # ── Daily equity curve (for best strategy, sampled) ──
    daily_returns = np.diff(close) / close[:-1]
    bh_curve = list(np.cumprod(1 + daily_returns))
    sample_step = max(1, len(bh_curve) // 100)
    bh_sampled = [
        {
            "day": i * sample_step,
            "equity": round(bh_curve[min(i * sample_step, len(bh_curve) - 1)], 4),
        }
        for i in range(min(100, len(bh_curve)))
    ]

    # ── Strategy vs Buy-Hold equity curves (time-series for charting) ──
    # Buy-hold normalized to 100
    bh_norm = [100.0] + [round(100.0 * v, 2) for v in bh_curve]
    # Strategy equity from best strategy's trade PnLs
    strat_equity_ts = [100.0]
    if best_trades:
        eq = 100.0
        trade_map = {}  # date → cumulative equity
        for t in best_trades:
            eq *= 1 + t["pnl_pct"] / 100.0
            trade_map[t.get("exit_date", "")] = round(eq, 2)
        # Build daily series: equity changes on exit dates, flat otherwise
        eq = 100.0
        for k in range(1, len(close)):
            d_str = (
                str(dates_idx[k].date())
                if hasattr(dates_idx[k], "date")
                else str(dates_idx[k])[:10]
            )
            if d_str in trade_map:
                eq = trade_map[d_str]
            strat_equity_ts.append(round(eq, 2))
    else:
        strat_equity_ts = bh_norm  # fallback if no trades

    # Build timestamped arrays (sampled to ~150 points)
    n_pts = len(close)
    sample_eq = max(1, n_pts // 150)
    equity_chart = {
        "bh": [],
        "strategy": [],
        "signals": [],  # entry/exit markers
    }
    for k in range(0, n_pts, sample_eq):
        ts = int(dates_idx[k].timestamp()) if hasattr(dates_idx[k], "timestamp") else k
        equity_chart["bh"].append({"time": ts, "value": round(bh_norm[k], 2)})
        if k < len(strat_equity_ts):
            equity_chart["strategy"].append({"time": ts, "value": strat_equity_ts[k]})
    # Always include last point
    if n_pts - 1 > 0:
        ts_last = (
            int(dates_idx[-1].timestamp())
            if hasattr(dates_idx[-1], "timestamp")
            else n_pts - 1
        )
        equity_chart["bh"].append({"time": ts_last, "value": round(bh_norm[-1], 2)})
        if len(strat_equity_ts) == n_pts:
            equity_chart["strategy"].append(
                {"time": ts_last, "value": strat_equity_ts[-1]}
            )
    # Signal markers (entry/exit points from best strategy trades)
    if best_trades:
        for t in best_trades[-50:]:  # last 50 trades
            e_ts = 0
            x_ts = 0
            for k2 in range(len(dates_idx)):
                d_str2 = (
                    str(dates_idx[k2].date())
                    if hasattr(dates_idx[k2], "date")
                    else str(dates_idx[k2])[:10]
                )
                if d_str2 == t.get("entry_date", ""):
                    e_ts = (
                        int(dates_idx[k2].timestamp())
                        if hasattr(dates_idx[k2], "timestamp")
                        else k2
                    )
                if d_str2 == t.get("exit_date", ""):
                    x_ts = (
                        int(dates_idx[k2].timestamp())
                        if hasattr(dates_idx[k2], "timestamp")
                        else k2
                    )
            if e_ts:
                equity_chart["signals"].append(
                    {
                        "time": e_ts,
                        "position": "belowBar",
                        "color": "#00d4aa",
                        "shape": "arrowUp",
                        "text": "BUY",
                    }
                )
            if x_ts:
                clr = "#00d4aa" if t["pnl_pct"] >= 0 else "#ff5c5c"
                equity_chart["signals"].append(
                    {
                        "time": x_ts,
                        "position": "aboveBar",
                        "color": clr,
                        "shape": "arrowDown",
                        "text": f"{'+'if t['pnl_pct']>=0 else ''}{t['pnl_pct']:.1f}%",
                    }
                )

    # ── Worst periods (largest losing streaks) ──
    worst_streaks = []
    if best_trades:
        streak = 0
        streak_ret = 0
        for t in best_trades:
            if t["pnl_pct"] < 0:
                streak += 1
                streak_ret += t["pnl_pct"]
            else:
                if streak >= 3:
                    worst_streaks.append(
                        {"losses": streak, "total_pct": round(streak_ret, 2)}
                    )
                streak = 0
                streak_ret = 0
        if streak >= 3:
            worst_streaks.append({"losses": streak, "total_pct": round(streak_ret, 2)})
        worst_streaks.sort(key=lambda x: x["total_pct"])

    # Strip internal fields before returning
    for r in ranked:
        r.pop("all_trades", None)

    return sanitize_for_json(
        {
            "ticker": ticker,
            "period": f"{start_date} to {end_date}" if start_date else period,
            "bars": len(close),
            "date_range": f"{dates_idx[0].date()} → {dates_idx[-1].date()}",
            "benchmark_return": round(bh_return, 2),
            "best_strategy": best,
            "strategies": ranked,
            "events": event_performance,
            "worst_streaks": worst_streaks[:5],
            "bh_equity_sampled": bh_sampled,
            "equity_chart": equity_chart,
            "trust": {
                "mode": "BACKTEST",
                "source": "yfinance_historical",
                "note": "Real price data. Gross returns — no commissions, fees, or slippage. Past performance ≠ future results.",
                "data_points": len(close),
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
