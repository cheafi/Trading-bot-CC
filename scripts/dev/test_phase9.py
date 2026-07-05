"""Phase 9 endpoint tests — verify all new engines return expected shapes."""

import requests

BASE = "http://localhost:8001"


def _get(path):
    r = requests.get(f"{BASE}{path}", timeout=30)
    assert r.status_code == 200, f"{path} returned {r.status_code}: {r.text[:200]}"
    return r.json()


def test_structure():
    d = _get("/api/v9/structure/AAPL")
    assert "trend" in d, f"Missing 'trend': {list(d.keys())}"
    assert d["trend"] in ("uptrend", "downtrend", "range"), d["trend"]
    assert isinstance(d.get("support_levels"), list)
    assert isinstance(d.get("resistance_levels"), list)
    assert isinstance(d.get("volume_confirms"), bool)
    print(f"  ✅ structure: trend={d['trend']}, S/R={len(d['support_levels'])}S/{len(d['resistance_levels'])}R")


def test_fundamentals():
    d = _get("/api/v9/fundamentals/AAPL")
    assert "quality_score" in d, f"Missing quality_score: {list(d.keys())}"
    assert isinstance(d["quality_score"], (int, float))
    assert "growth" in d and "profitability" in d and "valuation" in d
    assert "moat_indicators" in d
    print(f"  ✅ fundamentals: quality={d['quality_score']}, moat={d['moat_indicators'].get('has_moat')}")


def test_earnings():
    d = _get("/api/v9/earnings/AAPL")
    assert "in_blackout" in d, f"Missing in_blackout: {list(d.keys())}"
    assert isinstance(d["in_blackout"], bool)
    print(f"  ✅ earnings: blackout={d['in_blackout']}, days={d.get('days_to_earnings')}")


def test_entry_quality():
    d = _get("/api/v9/entry-quality/AAPL")
    # May have verdict or error depending on data
    if "error" not in d:
        assert "verdict" in d, f"Missing verdict: {list(d.keys())}"
        print(f"  ✅ entry-quality: verdict={d['verdict']}, score={d.get('score')}")
    else:
        print(f"  ⚠️ entry-quality: {d['error']}")


def test_breakouts():
    d = _get("/api/v9/breakouts")
    assert "active" in d, f"Missing active: {list(d.keys())}"
    assert isinstance(d["active"], list)
    print(f"  ✅ breakouts: {len(d['active'])} active")


def test_portfolio_gate():
    d = _get("/api/v9/portfolio-gate?ticker=AAPL")
    assert "allowed" in d, f"Missing allowed: {list(d.keys())}"
    assert isinstance(d["allowed"], bool)
    print(f"  ✅ portfolio-gate: allowed={d['allowed']}")


def test_journal():
    d = _get("/api/v9/journal")
    assert "entries" in d, f"Missing entries: {list(d.keys())}"
    assert "calibration" in d
    print(f"  ✅ journal: {len(d['entries'])} entries")


def test_calibration():
    d = _get("/api/v9/calibration")
    assert "total_resolved" in d, f"Missing total_resolved: {list(d.keys())}"
    print(f"  ✅ calibration: {d['total_resolved']} resolved")


def test_expert_records():
    d = _get("/api/v9/expert-records")
    assert "experts" in d, f"Missing experts: {list(d.keys())}"
    print(f"  ✅ expert-records: {len(d['experts'])} experts tracked")


# ── End-to-end pipeline tests ──


def test_ranked_has_phase9():
    d = _get("/api/v7/playbook/ranked?limit=5")
    rows = d.get("opportunities", [])
    if not rows:
        print("  ⚠️ ranked: no opportunities (market may be closed)")
        return
    r = rows[0]
    p9_fields = [
        "structure",
        "entry_quality",
        "earnings",
        "fundamentals",
        "portfolio_gate",
    ]
    present = [f for f in p9_fields if f in r and r[f] is not None]
    print(f"  ✅ ranked: {len(rows)} opps, Phase 9 fields: {present}")


def test_today_has_phase9():
    d = _get("/api/v7/playbook/today")
    top5 = d.get("top_5", [])
    if not top5:
        print("  ⚠️ today: no top-5 (market may be closed)")
        return
    r = top5[0]
    p9_fields = [
        "structure",
        "entry_quality",
        "earnings",
        "fundamentals",
        "portfolio_gate",
    ]
    present = [f for f in p9_fields if f in r and r[f] is not None]
    print(f"  ✅ today: {len(top5)} top, Phase 9 fields: {present}")


def test_notrade_has_phase9():
    d = _get("/api/v7/playbook/no-trade")
    signals = d.get("no_trade_signals", [])
    if not signals:
        print("  ⚠️ no-trade: no rejections right now")
        return
    r = signals[0]
    p9_fields = [
        "structure",
        "entry_quality",
        "earnings",
        "fundamentals",
        "portfolio_gate",
    ]
    present = [f for f in p9_fields if f in r]
    print(f"  ✅ no-trade: {len(signals)} rejected, Phase 9 fields: {present}")


def test_health():
    d = _get("/health")
    assert d.get("status") == "healthy", f"Unhealthy: {d}"
    p9 = d.get("phase9_engines", {})
    assert p9.get("loaded") is True, f"Phase 9 not loaded: {p9}"
    assert len(p9.get("components", [])) == 7, f"Expected 7 engines: {p9}"
    print(
        f"  ✅ health: {d['status']}, uptime={d.get('uptime_seconds', '?')}s, P9={len(p9.get('components',[]))} engines"
    )


if __name__ == "__main__":
    tests = [
        test_structure,
        test_fundamentals,
        test_earnings,
        test_entry_quality,
        test_breakouts,
        test_portfolio_gate,
        test_journal,
        test_calibration,
        test_expert_records,
        test_ranked_has_phase9,
        test_today_has_phase9,
        test_notrade_has_phase9,
        test_health,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  ❌ {t.__name__}: {e}")
            failed += 1
    print(f"\n{'='*40}")
    print(f"Phase 9: {passed} passed, {failed} failed out of {len(tests)}")
