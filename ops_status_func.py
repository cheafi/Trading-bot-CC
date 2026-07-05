@app.get("/api/ops/status", tags=["monitoring"])
async def ops_status():
    """Phase 3: Rich operator status for the Operator Console surface."""
    import time as _time

    engine = _get_engine()
    uptime_s = (datetime.now(timezone.utc) - startup_time).total_seconds()

    # Uptime formatting
    days = int(uptime_s // 86400)
    hours = int((uptime_s % 86400) // 3600)
    minutes = int((uptime_s % 3600) // 60)
    uptime_str = f"{days}d {hours}h {minutes}m" if days else f"{hours}h {minutes}m"

    # Engine metrics
    running = False
    cycle_count = 0
    signals_today = 0
    trades_today = 0
    circuit_breaker = False
    circuit_breaker_reason = ""
    dry_run = True
    last_cycle = None
    cached_recs = 0

    if engine:
        running = getattr(engine, "running", False)
        dry_run = getattr(engine, "dry_run", True)
        cycle_count = getattr(engine, "cycle_count", 0)
        signals_today = getattr(engine, "signals_today", 0)
        trades_today = getattr(engine, "trades_today", 0)
        circuit_breaker = getattr(engine, "circuit_breaker_triggered", False)
        circuit_breaker_reason = getattr(engine, "circuit_breaker_reason", "")
        cached_recs = len(getattr(engine, "_cached_recommendations", []))
        lc = getattr(engine, "last_cycle_time", None)
        if lc:
            last_cycle = str(lc)

    # Component health
    components = {}
    try:
        if engine:
            hc = await engine.health_check()
            components = hc.get("components", {})
    except Exception:
        pass

    # Market data stats
    cache_stats = {}
    try:
        cache_stats = app.state.market_data.cache_stats()
    except Exception:
        pass

    # Latency probe (time a simple regime fetch)
    t0 = _time.monotonic()
    try:
        await _get_regime()
        regime_latency_ms = round((_time.monotonic() - t0) * 1000, 1)
    except Exception:
        regime_latency_ms = -1

    return _sanitize_for_json(
        {
            "uptime": uptime_str,
            "uptime_seconds": round(uptime_s),
            "startup_time": startup_time.isoformat() + "Z",
            "version": APP_VERSION,
            "engine": {
                "running": running,
                "dry_run": dry_run,
                "cycle_count": cycle_count,
                "signals_today": signals_today,
                "trades_today": trades_today,
                "cached_recommendations": cached_recs,
                "circuit_breaker": circuit_breaker,
                "circuit_breaker_reason": circuit_breaker_reason,
                "last_cycle": last_cycle,
            },
            "components": components,
            "cache_stats": cache_stats,
            "latency": {
                "regime_ms": regime_latency_ms,
            },
            "trust": {
                "mode": "PAPER" if dry_run else "LIVE",
                "source": "engine + system",
                "as_of": datetime.now(timezone.utc).isoformat() + "Z",
            },
            "phase9_engines": {
                "loaded": _P9_ENGINES,
                "breakout_monitor": (
                    {"active": len(getattr(BreakoutMonitor, "_active", {}))}
                    if _P9_ENGINES
                    else {}
                ),
                "decision_journal": (
                    {"entries": len(getattr(get_journal(), "_decisions", []))}
                    if _P9_ENGINES
                    else {}
                ),
                "components": (
                    [
                        "StructureDetector",
                        "EntryQuality",
                        "BreakoutMonitor",
                        "PortfolioGate",
                        "EarningsCalendar",
                        "FundamentalData",
                        "DecisionJournal",
                    ]
                    if _P9_ENGINES
                    else []
                ),
            },
        }
    )


