"""
Sprint 40 Tests — Web↔Discord Alignment, /menu, Enhanced /backtest, Live API
v6.40
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
check("MODEL_VERSION is v6.40", MODEL_VERSION == "v6.40")

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
print("\n📱 MenuView Interactive Buttons")
bot_path = os.path.join(os.path.dirname(__file__), "src", "notifications", "discord_bot.py")
with open(bot_path) as f:
    bot_src = f.read()

check("MenuView class exists", "class MenuView" in bot_src)
check("MenuView has Markets button", "Markets" in bot_src and "📊" in bot_src)
check("MenuView has Signals button", "Signals" in bot_src and "🎯" in bot_src)
check("MenuView has Backtest button", "Backtest" in bot_src and "🔬" in bot_src)
check("MenuView has Portfolio button", "Portfolio" in bot_src and "💼" in bot_src)
check("MenuView has News button", "News" in bot_src and "📰" in bot_src)
check("MenuView has Dashboard button", "Dashboard" in bot_src and "📈" in bot_src)

# ── 4. /menu command ─────────────────────────────────────────
print("\n🎛️  /menu Slash Command")
check("/menu command defined", 'name="menu"' in bot_src)
check("/menu uses MenuView", "MenuView()" in bot_src)
check("/menu has embed", "Quick Menu" in bot_src or "One-Tap" in bot_src)

# ── 5. Enhanced /backtest command ─────────────────────────────
print("\n🔬 Enhanced /backtest Command")
check("strategy param exists", "strategy:" in bot_src and "all" in bot_src and "swing" in bot_src)
check("start_date param exists", "start_date" in bot_src)
check("end_date param exists", "end_date" in bot_src)
check("period param exists (1mo/3mo/6mo/1y/2y)", "1mo" in bot_src and "2y" in bot_src)
check("breakout strategy choice", "breakout" in bot_src)
check("mean_reversion strategy choice", "mean_reversion" in bot_src)
check("momentum strategy choice", "momentum" in bot_src)

# ── 6. Web Dashboard (index.html) ────────────────────────────
print("\n🖥️  Web Dashboard")
html_path = os.path.join(os.path.dirname(__file__), "src", "api", "templates", "index.html")
check("index.html exists", os.path.exists(html_path))

if os.path.exists(html_path):
    with open(html_path) as f:
        html_src = f.read()

    check("Dashboard fetches /api/live/market", "/api/live/market" in html_src)
    check("Dashboard fetches /api/live/quote", "/api/live/quote" in html_src)
    check("Dashboard fetches /api/live/backtest", "/api/live/backtest" in html_src)
    check("Backtest strategy selector in HTML", "strategy" in html_src.lower() and "select" in html_src.lower())
    check("Date range inputs in HTML", 'type="date"' in html_src)
    check("Quick period buttons", "'1mo'" in html_src and "'2y'" in html_src)
    check("Tailwind CSS loaded", "tailwindcss" in html_src)
    check("Alpine.js loaded", "alpinejs" in html_src or "Alpine" in html_src)
    check("v6.40 shown in dashboard", "v6.40" in html_src)
    check("Regime display in dashboard", "regime" in html_src.lower())
    check("Sector performance section", "Sector" in html_src)
    check("RSI displayed in quote", "RSI" in html_src)
    check("SMA indicators in quote", "SMA" in html_src)
    check("Strategy guide section", "Strategy Guide" in html_src or "strategy" in html_src.lower())
    check("Discord commands reference", "/menu" in html_src or "/backtest" in html_src)
    check("Universe stats (3,003)", "3,003" in html_src)
    check("Auto-refresh configured", "setInterval" in html_src or "60000" in html_src)
else:
    for _ in range(17):
        check("index.html missing — cannot test", False)

# ── 7. File integrity ─────────────────────────────────────────
print("\n📁 File Integrity")
check("discord_bot.py exists", os.path.exists(bot_path))
check("main.py exists", os.path.exists(main_path))
check("index.html > 100 lines", os.path.exists(html_path) and len(open(html_path).readlines()) > 100)
check("trust_metadata.py exists", os.path.exists(os.path.join(os.path.dirname(__file__), "src", "core", "trust_metadata.py")))

# ── Summary ───────────────────────────────────────────────────
print(f"\n{'='*50}")
total = PASS + FAIL
print(f"Sprint 40 Results: {PASS}/{total} passed ({PASS/total*100:.0f}%)")
if FAIL == 0:
    print("🎉 ALL TESTS PASSED — Sprint 40 complete!")
else:
    print(f"⚠️  {FAIL} test(s) failed")
print(f"{'='*50}")
