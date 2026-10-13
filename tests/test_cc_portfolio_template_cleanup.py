import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CC_APP = ROOT / "src/api/static/cc-app.js"


class TestCCPortfolioTemplateCleanup(unittest.TestCase):
    def test_no_duplicate_portfolio_title_in_header_summary(self):
        # Regression: the subtitle used to repeat base.title.
        html = _read_index_html()
        self.assertIn("headerSummary().subtitle", html)
        self.assertNotRegex(
            _js_method("headerSummary"),
            r":\s*base\.title\s*\)",
            "Expected headerSummary subtitle to not fallback to base.title",
        )

    def test_targets_placeholder_is_user_friendly(self):
        html = _portfolio_tab_html()
        self.assertIn(':placeholder="portfolioTargetsPlaceholder()"', html)
        # Ensure we don't show raw JSON examples in normal UI copy.
        self.assertNotIn('Targets JSON {"AAPL":40,"MSFT":30}', html)
        _assert_js_behavior(
            ("portfolioTargetsPlaceholder",),
            """
app.isDevMode = () => false;
assert.equal(
    app.portfolioTargetsPlaceholder(),
    'Target weights: AAPL 40% · MSFT 30%',
);
app.isDevMode = () => true;
assert.equal(app.portfolioTargetsPlaceholder(), 'Targets JSON (debug)');
""",
        )

    def test_var_wording(self):
        pf = _portfolio_tab_html()
        full = _read_index_html()
        self.assertIn("Estimated 1-day 95% VaR", pf)
        self.assertNotIn("VaR-95 (1d)", pf)
        self.assertNotIn("PARAM·EST", full)
        self.assertNotIn("PARAM·LIVE", full)
        self.assertIn("pfVar95MethodBadge()", pf)
        self.assertRegex(
            _js_method("pfVar95MethodBadge"), r"return\s+['\"]parametric['\"]"
        )
        _assert_js_behavior(
            ("pfVar95MethodBadge",),
            """
    app.pfRisk = () => ({var95Quality: 'estimate'});
    assert.equal(app.pfVar95MethodBadge(), 'parametric');
    app.pfRisk = () => ({var95Quality: 'position-vol'});
    assert.equal(app.pfVar95MethodBadge(), 'parametric · live vol');
    app.pfRisk = () => ({var95Quality: 'historical', var95Tier: 'HISTSIM'});
    assert.equal(app.pfVar95MethodBadge(), 'histsim');
    """,
        )

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
        button = re.search(
            r'<button\b[^>]*@click="portfolioOpenStopForTicker\(pos\.ticker\)"'
            r"[^>]*>Set stop</button>",
            html,
        )
        self.assertIsNotNone(button, "Missing in-card Set stop button")
        self.assertIn("background:transparent", button.group(0))
        self.assertIn("border:1px solid var(--red)", button.group(0))

    def test_no_stop_plan_warning_once_per_card(self):
        html = _portfolio_tab_html()
        binding = 'x-text="pfPosRisk(pos).anchorBadge"'
        self.assertEqual(html.count(binding), 1)
        warning_tags = [tag for tag in re.findall(r"<[^>]+>", html) if binding in tag]
        self.assertEqual(len(warning_tags), 1)
        self.assertIn('x-show="!pfPosRisk(pos).stopDefined"', warning_tags[0])
        self.assertNotIn("NO STOP PLAN", html)
        self.assertRegex(
            _js_method("pfPosRisk"),
            r"anchorBadge\s*:\s*['\"]NO STOP PLAN['\"]",
        )
        _assert_js_behavior(
            ("pfPosRisk",),
            """
app.pfDecision = null;
const base = {ticker: 'AAA', entry_price: 100, current_price: 110};
for (const stopFields of [{}, {stop_price: 0}, {stop_defined: false}]) {
    const risk = app.pfPosRisk({
        ...base, ...stopFields, risk_status: 'NO STOP PLAN', unrealized_r: 2,
    });
    assert.equal(risk.stopDefined, false);
    assert.equal(risk.anchorBadge, 'NO STOP PLAN');
    assert.equal(risk.riskStatus, '—');
    assert.equal(risk.initStopLabel, '—');
    assert.equal(risk.currStopLabel, '—');
    assert.equal(risk.unrealR, null);
    assert.equal(risk.unrealRLabel, '—');
    assert.equal(risk.nextAction, 'SET STOP');
}
const defined = app.pfPosRisk({...base, stop_price: 90});
assert.equal(defined.stopDefined, true);
assert.equal(defined.riskStatus, 'IN TRADE');
assert.equal(defined.nextAction, 'MONITOR');
assert.equal(defined.currStopLabel, '$90.00');
assert.equal(defined.unrealR, 1);
const breached = app.pfPosRisk({
    ...base, stop_defined: true, stop_price: 90, risk_status: 'STOP BREACHED',
});
assert.equal(breached.riskStatus, 'STOP BREACHED');
assert.equal(breached.riskStatusClass, 'text-red-400');
""",
        )

    def test_risk_status_raw_not_used(self):
        html = _portfolio_tab_html()
        self.assertIn('x-text="pfPosRisk(pos).riskStatus"', html)
        self.assertNotIn(
            "pos.risk_status",
            html,
            "Position-card bindings must use normalized pfPosRisk status",
        )


def _read_index_html() -> str:
    p = ROOT / "src/api/templates/index.html"
    return p.read_text(encoding="utf-8")


def _portfolio_tab_html() -> str:
    html = _read_index_html()
    start = html.find("<main x-show=\"tab==='portfolio'\"")
    assert start >= 0, "Missing portfolio main surface"
    end = html.find("<!-- ── Closed-Trade Ledger", start)
    assert end > start, "Missing portfolio position-card boundary"
    return html[start:end]


def _js_method(name: str) -> str:
    source = CC_APP.read_text(encoding="utf-8")
    match = re.search(
        rf"^[ \t]*{re.escape(name)}\s*\([^\n)]*\)\s*\{{" r".*?^[ \t]*\}[ \t]*,[ \t]*$",
        source,
        re.MULTILINE | re.DOTALL,
    )
    assert match is not None, f"Missing JavaScript method {name}"
    return match.group(0)


def _assert_js_behavior(names: tuple[str, ...], assertions: str) -> None:
    # Execute production methods, not copied implementations or launcher init.
    methods = "\n".join(_js_method(name) for name in names)
    script = (
        "const assert = require('node:assert/strict');\nconst app = {"
        + methods
        + "};\n"
        + assertions
    )
    result = subprocess.run(
        ["node", "-"],
        input=script,
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _read_portfolio_router_py() -> str:
    p = Path(__file__).resolve().parents[1] / "src" / "api" / "routers" / "portfolio.py"
    return p.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
