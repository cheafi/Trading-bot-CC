"""Sprint 58 — Frontend Decision-Product Transformation Tests.

Validates the index.html template restructure:
- Today tab fetches /api/v7/today and renders regime + top ranked + funnel + avoid
- Signals→Board tab fetches /api/v7/opportunities and renders ranked decision cards
- Alpine.js data model includes today7/opps/oppsSort state
- Fetch functions fetchToday7/fetchOpps exist
- Tab labels updated (Today 🎯, Board 📊)
- Why-now / why-not / invalidation / action fields rendered
"""

import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parent
# Try workspace copy first, then /tmp/cc_temp
for base in [ROOT, pathlib.Path("/tmp/cc_temp")]:
    idx = base / "src" / "api" / "templates" / "index.html"
    if idx.exists():
        break

HTML = idx.read_text()


# ── helpers ──
def _has(pattern: str, text: str = HTML) -> bool:
    return bool(re.search(pattern, text))


def _count(pattern: str, text: str = HTML) -> int:
    return len(re.findall(pattern, text))


# ═══════════════════════════════════════════════════
# 1. Today tab — regime action banner
# ═══════════════════════════════════════════════════

class TestTodayTab:
    """Today tab now shows v7 decision data instead of raw market data."""

    def test_today_tab_has_regime_banner(self):
        assert _has(r"today7\.regime"), "Today tab should reference today7.regime"

    def test_regime_risk_state_coloring(self):
        assert _has(r"today7\.regime\.risk_state"), "Should color-code by risk_state"

    def test_regime_tradeability_pill(self):
        assert _has(r"today7\.regime\.tradeability"), "Should show tradeability pill"

    def test_regime_summary_text(self):
        assert _has(r"today7\.regime\.summary"), "Should show regime summary"

    def test_regime_trend_vol_pills(self):
        assert _has(r"today7\.regime\.trend")
        assert _has(r"today7\.regime\.volatility")

    def test_regime_score_pill(self):
        assert _has(r"today7\.regime\.score")


# ═══════════════════════════════════════════════════
# 2. Filter funnel visualization
# ═══════════════════════════════════════════════════

class TestFilterFunnel:
    def test_funnel_present(self):
        assert _has(r"today7\.filter_funnel"), "Filter funnel should be in Today tab"

    def test_funnel_steps(self):
        for step in ["universe", "triggered", "score_gte_6", "score_gte_7", "score_gte_8"]:
            assert _has(step), f"Funnel step '{step}' should appear"

    def test_funnel_bar_visualization(self):
        assert _has(r"height.*filter_funnel"), "Funnel should have visual bars"


# ═══════════════════════════════════════════════════
# 3. Top ranked opportunities
# ═══════════════════════════════════════════════════

class TestTopRanked:
    def test_top_ranked_section(self):
        assert _has(r"today7\.top_ranked"), "Today tab should show top_ranked"

    def test_rank_number_display(self):
        assert _has(r"#.*idx\+1"), "Should show rank number"

    def test_opp_ticker_strategy_score(self):
        assert _has(r"opp\.ticker")
        assert _has(r"opp\.strategy")
        assert _has(r"opp\.score")

    def test_opp_action_display(self):
        assert _has(r"opp\.action"), "Should show action (BUY/AVOID)"

    def test_opp_why_now(self):
        assert _has(r"opp\.why_now"), "Should show why_now"

    def test_opp_why_not(self):
        assert _has(r"opp\.why_not"), "Should show why_not"

    def test_opp_timing_rr(self):
        assert _has(r"opp\.timing")
        assert _has(r"opp\.risk_reward")


# ═══════════════════════════════════════════════════
# 4. Avoid list
# ═══════════════════════════════════════════════════

class TestAvoidList:
    def test_avoid_list_section(self):
        assert _has(r"today7\.avoid_list"), "Should render avoid list"

    def test_avoid_ticker_reason(self):
        assert _has(r"a\.ticker.*a\.reason|a\.reason.*a\.ticker"), "Each avoid item shows ticker+reason"


# ═══════════════════════════════════════════════════
# 5. Board (Opportunities) tab
# ═══════════════════════════════════════════════════

class TestBoardTab:
    def test_board_tab_label(self):
        assert _has(r"label:'Board'"), "Signals tab renamed to Board"

    def test_board_icon_changed(self):
        assert _has(r"icon:'📊',label:'Board'"), "Board tab should use 📊 icon"

    def test_today_icon_changed(self):
        assert _has(r"icon:'🎯',label:'Today'"), "Today tab should use 🎯 icon"

    def test_opps_sort_buttons(self):
        assert _has(r"oppsSort==='score'"), "Should have score sort button"
        assert _has(r"oppsSort==='risk_reward'"), "Should have R:R sort button"

    def test_opps_card_layout(self):
        assert _has(r"r\.action"), "Board cards show action"
        assert _has(r"r\.why_now"), "Board cards show why_now"
        assert _has(r"r\.why_not"), "Board cards show why_not"
        assert _has(r"r\.invalidation"), "Board cards show invalidation"

    def test_opps_position_hint(self):
        assert _has(r"r\.position_hint"), "Board cards show position hint"


# ═══════════════════════════════════════════════════
# 6. Alpine.js data model
# ═══════════════════════════════════════════════════

class TestAlpineDataModel:
    def test_today7_state(self):
        assert _has(r"today7:\{"), "Alpine data should have today7 object"

    def test_today7_fields(self):
        assert _has(r"today7.*regime.*top_ranked.*filter_funnel.*avoid_list")

    def test_opps_state(self):
        assert _has(r"opps:\[\]"), "Alpine data should have opps array"

    def test_opps_sort_state(self):
        assert _has(r"oppsSort:'score'"), "Default sort should be 'score'"


# ═══════════════════════════════════════════════════
# 7. Fetch functions
# ═══════════════════════════════════════════════════

class TestFetchFunctions:
    def test_fetch_today7_exists(self):
        assert _has(r"async fetchToday7\(\)"), "fetchToday7 function should exist"

    def test_fetch_today7_endpoint(self):
        assert _has(r"/api/v7/today"), "fetchToday7 should call /api/v7/today"

    def test_fetch_opps_exists(self):
        assert _has(r"async fetchOpps\(\)"), "fetchOpps function should exist"

    def test_fetch_opps_endpoint(self):
        assert _has(r"/api/v7/opportunities"), "fetchOpps should call /api/v7/opportunities"

    def test_sort_opps_exists(self):
        assert _has(r"sortOpps\(\)"), "sortOpps function should exist"

    def test_init_calls_fetch_today7(self):
        assert _has(r"this\.fetchToday7\(\)"), "init should call fetchToday7"

    def test_auto_refresh_today7(self):
        assert _has(r"setInterval.*fetchToday7"), "fetchToday7 should auto-refresh"

    def test_switch_tab_today_fetches(self):
        assert _has(r"t==='today'.*fetchToday7|fetchToday7.*t==='today'"), "Switching to today should fetch v7"

    def test_switch_tab_signals_fetches_opps(self):
        assert _has(r"fetchOpps"), "Switching to signals/board should fetch opps"


# ═══════════════════════════════════════════════════
# 8. Market data collapsed (not removed)
# ═══════════════════════════════════════════════════

class TestMarketDataPreserved:
    def test_indices_still_present(self):
        assert _has(r"x-for=\"i in indices\""), "Indices data should still be rendered"

    def test_sectors_still_present(self):
        assert _has(r"x-for=\"s in sectors\""), "Sector heatmap should still be rendered"

    def test_market_data_collapsed(self):
        assert _has(r"<details"), "Market data should be in a collapsible <details>"

    def test_market_data_summary(self):
        assert _has(r"Market Data"), "Collapsible should be labeled 'Market Data'"


# ═══════════════════════════════════════════════════
# 9. Decision router endpoints exist in codebase
# ═══════════════════════════════════════════════════

class TestDecisionRouterExists:
    def test_decision_router_file(self):
        router_file = ROOT / "src" / "api" / "routers" / "decision.py"
        if not router_file.exists():
            router_file = pathlib.Path("/tmp/cc_temp/src/api/routers/decision.py")
        assert router_file.exists(), "decision.py router should exist"

    def test_decision_router_has_today(self):
        router_file = ROOT / "src" / "api" / "routers" / "decision.py"
        if not router_file.exists():
            router_file = pathlib.Path("/tmp/cc_temp/src/api/routers/decision.py")
        code = router_file.read_text()
        assert "/api/v7/today" in code

    def test_decision_router_has_opportunities(self):
        router_file = ROOT / "src" / "api" / "routers" / "decision.py"
        if not router_file.exists():
            router_file = pathlib.Path("/tmp/cc_temp/src/api/routers/decision.py")
        code = router_file.read_text()
        assert "/api/v7/opportunities" in code


# ═══════════════════════════════════════════════════
# 10. No regressions — key preserved elements
# ═══════════════════════════════════════════════════

class TestNoRegressions:
    def test_dossier_tab_preserved(self):
        assert _has(r"tab==='dossier'"), "Dossier tab should still work"

    def test_brief_tab_preserved(self):
        assert _has(r"tab==='brief'"), "Brief tab should still work"

    def test_options_tab_preserved(self):
        assert _has(r"tab==='options'"), "Options tab should still work"

    def test_ops_tab_preserved(self):
        assert _has(r"tab==='ops'"), "Ops tab should still work"

    def test_fetch_mkt_preserved(self):
        assert _has(r"fetchMkt\(\)"), "fetchMkt should still exist"

    def test_fetch_signals_preserved(self):
        assert _has(r"fetchSignals\(\)"), "fetchSignals should still exist"

    def test_fetch_dossier_preserved(self):
        assert _has(r"fetchDossier\(\)"), "fetchDossier should still exist"

    def test_open_dossier_preserved(self):
        assert _has(r"openDossier\("), "openDossier should still work"

    def test_strategy_health_preserved(self):
        assert _has(r"strategy_scores"), "Strategy health leaderboard preserved"

    def test_alpine_init_preserved(self):
        assert _has(r"init\(\)"), "Alpine init function preserved"

    def test_total_tabs_count(self):
        count = _count(r"\{id:'[^']+',icon:'[^']+',label:'[^']+'}")
        assert count == 9, f"Should have 9 tabs, got {count}"
