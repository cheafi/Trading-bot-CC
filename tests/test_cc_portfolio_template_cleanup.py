import re
import unittest


class TestCCPortfolioTemplateCleanup(unittest.TestCase):
    def test_no_duplicate_portfolio_title_in_header_summary(self):
        # Regression: subtitle used to repeat base.title, rendering the same title twice.
        html = _read_index_html()
        self.assertNotIn(
            "):base.title);",
            html,
            "Expected headerSummary subtitle to not fallback to base.title",
        )
        self.assertNotIn(
            ":base.title);",
            html,
            "Expected headerSummary subtitle to not fallback to base.title",
        )

    def test_targets_placeholder_is_user_friendly(self):
        html = _read_index_html()
        self.assertIn("Target weights: AAPL 40% · MSFT 30%", html)
        # Ensure we don't show raw JSON examples in normal UI copy.
        self.assertNotIn('Targets JSON {"AAPL":40,"MSFT":30}', html)

    def test_var_wording(self):
        pf = _portfolio_tab_html()
        full = _read_index_html()
        self.assertIn("Estimated 1-day 95% VaR", pf)
        self.assertNotIn("VaR-95 (1d)", pf)
        self.assertNotIn("PARAM·EST", full)
        self.assertNotIn("PARAM·LIVE", full)
        self.assertIn("pfVar95MethodBadge()", pf)
        self.assertRegex(full, r"return\s+'parametric'")

    def test_var_label_not_force_uppercase(self):
        pf = _portfolio_tab_html()
        idx = pf.find("Estimated 1-day 95% VaR")
        self.assertGreater(idx, -1, "VaR label should exist in portfolio tab")
        block = pf[idx : idx + 900]
        self.assertIn("pfVar95MethodBadge()", block)
        self.assertNotIn("uppercase", block, "VaR title should not use CSS uppercase")

    def test_concentration_warning_copy_present(self):
        html = _portfolio_tab_html()
        self.assertIn("Single-name concentration is extreme.", html)
        self.assertIn("One position =", html)

    def test_primary_risk_blocker_copy_present(self):
        html = _portfolio_tab_html()
        self.assertIn("Primary risk blocker:", html)
        self.assertIn("SET STOP", html)

    def test_pluralization_one_position(self):
        src = _read_portfolio_router_py()
        self.assertIn("def positions_label(count: int)", src)
        self.assertIn('return "1 position"', src)
        html = _read_index_html()
        self.assertIn("portfolioSummaryPositionsLabel()", html)
        pf = _portfolio_tab_html()
        self.assertNotRegex(
            pf,
            r"total_positions\s*\+\s*' positions'",
            "Portfolio tab should not concatenate raw ' positions' suffix",
        )

    def test_in_card_set_stop_is_secondary_outline(self):
        html = _portfolio_tab_html()
        self.assertIn("portfolioOpenStopForTicker(pos.ticker)", html)
        self.assertIn(">Set stop</button>", html)
        self.assertIn("pfPosRisk(pos).nextAction!=='SET STOP'", html)

    def test_no_stop_plan_warning_once_per_card(self):
        full = _read_index_html()
        self.assertIn("anchorBadge:'NO STOP PLAN'", full)
        self.assertIn("stopDefined?(pos.risk_status||'IN TRADE'):'—'", full)
        self.assertNotIn(
            "stopDefined?'IN TRADE':'NO STOP PLAN'",
            full,
            "pfPosRisk should not set riskStatus to NO STOP PLAN when stop missing",
        )


def _read_index_html() -> str:
    from pathlib import Path

    p = Path(__file__).resolve().parents[1] / "src" / "api" / "templates" / "index.html"
    return p.read_text(encoding="utf-8")


def _portfolio_tab_html() -> str:
    html = _read_index_html()
    start = html.find("tab==='portfolio'")
    end = html.find("<!-- ── Closed-Trade Ledger", start)
    if start < 0 or end < 0:
        return html
    return html[start:end]


def _read_portfolio_router_py() -> str:
    from pathlib import Path

    p = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "api"
        / "routers"
        / "portfolio.py"
    )
    return p.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
