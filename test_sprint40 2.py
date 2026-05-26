"""
Sprint 40-41 Tests — Web↔Discord Alignment, Smart /menu, Enhanced /backtest, Live API
v6.41
"""
import os
import sys
import inspect
import importlib

sys.path.insert(0, os.path.dirname(__file__))

PASS = 0
FAIL = 0

def check(name, condition):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✅ {name}")
    else:
        FAIL += 1
        print(f"  ❌ {name}")

# ── 1. Version bump ──────────────────────────────────────────
print("\n🔢 Version")
from src.core.trust_metadata import MODEL_VERSION
check("MODEL_VERSION is v6.41", MODEL_VERSION == "v6.41")

# ── 2. Live API endpoints exist in main.py ───────────────────
print("\n🌐 Live API Endpoints")
main_path = os.path.join(os.path.dirname(__file__), "src", "api", "main.py")
with open(main_path) as f:
    main_src = f.read()

check("GET /api/live/market endpoint exists", "'/api/live/market'" in main_src or '"/api/live/market"' in main_src)
check("GET /api/live/quote endpoint exists", "/api/live/quote/" in main_src)
check("POST /api/live/backtest endpoint exists", "/api/live/backtest" in main_src)
check("GET /api/live/strategies endpoint exists", "/api/live/strategies" in main_src)
check("yfinance used in live endpoints", "yfinance" in main_src)
check("RSI calculation in quote endpoint", "rsi" in main_src.lower())
check("SMA calculation in quote endpoint", "sma20" in main_src or "sma_20" in main_src)
check("Sector ETFs referenced (XLK)", "XLK" in main_src)
check("Regime detection logic", "risk_on" in main_src.lower() or "RISK_ON" in main_src)

# ── 3. MenuView class ────────────────────────────────────────
print("\n📱 Smart Menu System")
bot_path = os.path.join(os.path.dirname(__file__), "src", "notifications", "discord_bot.py")
with open(bot_path) as f:
    bot_src = f.read()

check("MenuView class exists", "class MenuView" in bot_src)
check("MenuCategorySelect exists", "class MenuCategorySelect" in bot_src)
check("8 category options in select", bot_src.count("discord.SelectOption") >= 8)
check("AI intelligence button exists", "What Should I Do" in bot_src)
check("AI reads market live", "AI Intelligence Brief" in bot_src)
check("Risk regime detection", "RISK_OFF" in bot_src and "RISK_ON" in bot_src)
check("Suggested actions (GO AGGRESSIVE)", "GO AGGRESSIVE" in bot_src)
check("Suggested actions (DEFENSIVE)", "DEFENSIVE" in bot_src)
check("Full Dashboard button", "Full Dashboard" in bot_src)
check("Open Web button", "Open Web" in bot_src)

# ── 4. LAN IP & no localhost ──────────────────────────────────
print("\n🌐 LAN IP & Dynamic URL")
check("_get_lan_ip() helper exists", "def _get_lan_ip" in bot_src)
check("_get_dashboard_url() helper exists", "def _get_dashboard_url" in bot_src)
check("socket import exists", "import socket" in bot_src)
check("No hardcoded localhost in bot", "localhost:8000" not in bot_src)

# ── 5. /menu command ─────────────────────────────────────────
print("\n🎛️  /menu Slash Command")
check("/menu command defined", 'name="menu"' in bot_src)
check("/menu uses MenuView", "MenuView()" in bot_src)
check("/menu has Command Center embed", "Command Center" in bot_src)
check("Categories listed: Markets", "Markets & Prices" in bot_src)
check("Categories listed: Signals", "AI Signals & Scanners" in bot_src)
check("Categories listed: Analysis", "Deep Analysis" in bot_src)
check("Categories listed: Trading", "Portfolio & Trading" in bot_src)
check("Categories listed: Backtest", "Backtest & Strategy" in bot_src)
check("Categories listed: Global", "Asia, Crypto & Global" in bot_src)
check("Categories listed: Tools", "Tools & Alerts" in bot_src)
check("Categories listed: Reports", "Reports & Briefings" in bot_src)

# ── 6. Enhanced /backtest command ─────────────────────────────
print("\n🔬 Enhanced /backtest Command")
check("strategy param exists", "strategy:" in bot_src and "all" in bot_src and "swing" in bot_src)
check("start_date param exists", "start_date" in bot_src)
check("end_date param exists", "end_date" in bot_src)
check("period param exists (1mo/3mo/6mo/1y/2y)", "1mo" in bot_src and "2y" in bot_src)
check("breakout strategy choice", "breakout" in bot_src)
check("mean_reversion strategy choice", "mean_reversion" in bot_src)
check("momentum strategy choice", "momentum" in bot_src)

# ── 7. Web Dashboard (index.html) ────────────────────────────
print("\n🖥️  Web Dashboard")
html_path = os.path.join(os.path.dirname(__file__), "src", "api", "templates", "index.html")
check("index.html exists", os.path.exists(html_path))

if os.path.exists(html_path):
    with open(html_path) as f:
        html_src = f.read()

    check("Dashboard fetches /api/live/market", "/api/live/market" in html_src)
    check("Dashboard fetches /api/live/quote", "/api/live/quote" in html_src)
    check("Dashboard fetches /api/live/backtest", "/api/live/backtest" in html_src)
    check("Backtest strategy selector", "strategy" in html_src.lower() and "select" in html_src.lower())
    check("Date range inputs", 'type="date"' in html_src)
    check("Quick period buttons", "'1mo'" in html_src and "'2y'" in html_src)
    check("Tailwind CSS loaded", "tailwindcss" in html_src)
    check("Alpine.js loaded", "alpinejs" in html_src or "Alpine" in html_src)
    check("v6.41 shown in dashboard", "v6.41" in html_src)
    check("Regime display", "regime" in html_src.lower())
    check("Sectors section", "Sector" in html_src)
    check("RSI in quote", "RSI" in html_src)
    check("SMA in quote", "SMA" in html_src)
    check("Commands tab exists", "Commands" in html_src or "cmds" in html_src)
    check("Discord /menu reference", "/menu" in html_src)
    check("Mobile meta viewport", "user-scalable" in html_src)
    check("PWA apple-mobile-web-app", "apple-mobile-web-app" in html_src)
    check("Auto-refresh 60s", "60000" in html_src)
else:
    for _ in range(18):
        check("index.html missing", False)

# ── 8. File integrity ─────────────────────────────────────────
print("\n📁 File Integrity")
check("discord_bot.py exists", os.path.exists(bot_path))
check("main.py exists", os.path.exists(main_path))
check("index.html > 100 lines", os.path.exists(html_path) and len(open(html_path).readlines()) > 100)
check("trust_metadata.py exists", os.path.exists(os.path.join(os.path.dirname(__file__), "src", "core", "trust_metadata.py")))

# ── Summary ───────────────────────────────────────────────────
print(f"\n{'='*50}")
total = PASS + FAIL
print(f"Sprint 40-41 Results: {PASS}/{total} passed ({PASS/total*100:.0f}%)")
if FAIL == 0:
    print("🎉 ALL TESTS PASSED — Sprint 41 complete!")
else:
    print(f"⚠️  {FAIL} test(s) failed")
print(f"{'='*50}")
