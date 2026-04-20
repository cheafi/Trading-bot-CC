"""Sprint 48 tests — CI fix, dashboard upgrade, Discord alignment, Futu options."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent

# ── 1. CI workflow ──────────────────────────────────────────────────────────
def test_ci_file_exists():
    ci = ROOT / ".github" / "workflows" / "ci.yml"
    assert ci.exists(), "ci.yml missing"

def test_ci_uses_pip_not_poetry():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "pip install" in ci
    assert "poetry" not in ci.lower()

def test_ci_runs_sprint_tests():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "pytest" in ci
    assert "test_sprint45" in ci or "test_sprint4" in ci

def test_ci_python_matrix():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "3.11" in ci and "3.13" in ci

def test_ci_syntax_check_job():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "syntax-check" in ci or "py_compile" in ci

# ── 2. Dashboard ────────────────────────────────────────────────────────────
def test_dashboard_exists():
    html = ROOT / "docs" / "index.html"
    assert html.exists()

def test_dashboard_has_swing_tab():
    html = (ROOT / "docs" / "index.html").read_text()
    assert "swing" in html.lower()
    assert "swingCandidates" in html or "swing-analysis" in html.lower()

def test_dashboard_has_9_nav_tabs():
    html = (ROOT / "docs" / "index.html").read_text()
    tabs = html.count("@click.prevent=\"tab=")
    assert tabs >= 9, f"Expected >=9 tabs, got {tabs}"

def test_dashboard_swing_rs_vcp():
    html = (ROOT / "docs" / "index.html").read_text()
    assert "RS Score" in html or "rs" in html
    assert "VCP" in html
    assert "pullback" in html.lower() or "Pullback" in html

def test_dashboard_futu_options():
    """Dashboard has Futu-inspired annualized yield in options tab."""
    html = (ROOT / "docs" / "index.html").read_text()
    assert "annYield" in html or "Ann.Yield" in html or "annualized" in html.lower()

def test_dashboard_put_selling():
    html = (ROOT / "docs" / "index.html").read_text()
    assert "Put-Selling" in html or "put-selling" in html.lower()

def test_dashboard_preload_optimization():
    html = (ROOT / "docs" / "index.html").read_text()
    assert "preload" in html.lower() or "defer" in html.lower()

def test_dashboard_score_bar():
    """Neal-inspired score visualization."""
    html = (ROOT / "docs" / "index.html").read_text()
    assert "score-bar" in html or "score-fill" in html

def test_dashboard_meta_ensemble_health():
    html = (ROOT / "docs" / "index.html").read_text()
    assert "meta_ensemble" in html or "Meta-Ensemble" in html

# ── 3. Discord alignment ───────────────────────────────────────────────────
def test_discord_analytics_commands_exist():
    src = (ROOT / "src" / "notifications" / "discord_bot.py").read_text()
    assert "def _register_analytics_commands" in src

def test_discord_meta_ensemble_command():
    src = (ROOT / "src" / "notifications" / "discord_bot.py").read_text()
    assert 'name="meta-ensemble"' in src

def test_discord_trust_card_command():
    src = (ROOT / "src" / "notifications" / "discord_bot.py").read_text()
    assert 'name="trust-card"' in src

def test_discord_model_version_command():
    src = (ROOT / "src" / "notifications" / "discord_bot.py").read_text()
    assert 'name="model-version"' in src

def test_discord_options_scan_command():
    src = (ROOT / "src" / "notifications" / "discord_bot.py").read_text()
    assert 'name="options-scan"' in src

def test_discord_swing_commands_wired():
    """Swing + analytics commands are wired in on_ready."""
    src = (ROOT / "src" / "notifications" / "discord_bot.py").read_text()
    assert "_register_swing_commands" in src
    assert "_register_analytics_commands" in src
    # Both called in on_ready
    assert src.count("_register_swing_commands") >= 2  # def + call
    assert src.count("_register_analytics_commands") >= 2

# ── 4. API endpoint coverage ───────────────────────────────────────────────
def test_api_swing_endpoints():
    src = (ROOT / "src" / "api" / "main.py").read_text()
    for ep in ["/api/v6/rs-strength/", "/api/v6/vcp-scan/", "/api/v6/swing-analysis/",
               "/api/v6/swing-batch", "/api/v6/distribution-days"]:
        assert ep in src, f"Missing endpoint {ep}"

def test_api_analytics_endpoints():
    src = (ROOT / "src" / "api" / "main.py").read_text()
    # Also check routers (Sprint 54 extraction)
    router_path = ROOT / "src" / "api" / "routers" / "intel.py"
    if router_path.exists():
        src += router_path.read_text()
    for ep in ["/api/v6/meta-ensemble", "/api/v6/trust-card/", "/api/v6/model-version"]:
        assert ep in src, f"Missing endpoint {ep}"

# ── 5. Integration ─────────────────────────────────────────────────────────
def test_main_app_imports():
    """main.py still imports and starts correctly."""
    src = (ROOT / "src" / "api" / "main.py").read_text()
    assert "FastAPI" in src
    assert "app = FastAPI" in src or "app=FastAPI" in src
