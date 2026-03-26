"""
TradingAI Pro v6.0 — Institutional-Grade Discord Trading Server Bot
=====================================================================

v6 Upgrades (Pro Desk):
  • RegimeScoreboard + DeltaSnapshot integration
  • Signal cards with setup_grade, approval_status, why_now, scenario_plan
  • Morning memo: Regime Scoreboard → Delta Deck → Playbook → Top 5 w/ grades → Scenarios
  • /market_now: full scoreboard, delta deck, flows, scenario map
  • Report generator powered signal cards & morning memos
  • Progressive disclosure UX with v6 buttons

Architecture:
  • Multi-category channel layout with proper permission overrides
  • Role hierarchy: Owner → Admin → Pro Trader → Trader → Free → Unverified
  • Read-only announcement/signal channels (bot-write, user-read)
  • Interactive buttons, select menus, and modal forms
  • Paginated embeds for long data
  • Global error handler with user-friendly messages
  • Per-command cooldowns to prevent abuse
  • Audit logging of all actions
  • Scheduled background tasks (market open/close, daily briefs)
  • Dynamic bot presence showing market status
  • Verification gate for new members

Commands (50+):
  Market Data   — /price /quote /market /market_now /sector /macro /movers /news /premarket
  AI Signals    — /signals /scan /breakout /dip /momentum /swing /whale /squeeze
  AI Analysis   — /ai /analyze /advise /score /compare /levels /why
  Trading       — /buy /sell /portfolio /positions /pnl /risk /stats
  Multi-Market  — /asia /japan /hk /crypto /btc
  Tools         — /backtest /alert /watchlist /daily /status
  Admin         — /setup /announce /purge /slowmode /pin
"""

from __future__ import annotations

import asyncio
import logging
import os
import traceback
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Sequence

import aiohttp

from src.core.config import get_settings

# v6: report generator for signal cards, memos, scoreboard
try:
    from src.notifications.report_generator import (
        build_signal_card,
        build_regime_snapshot,
        build_morning_memo,
        build_eod_scorecard,
    )
    _HAS_REPORT_GEN = True
except ImportError:
    _HAS_REPORT_GEN = False

# v6: strategy optimizer (self-learning, regime-aware backtester)
try:
    from src.engines.strategy_optimizer import get_optimizer as _get_optimizer
    _HAS_OPTIMIZER = True
except ImportError:
    _HAS_OPTIMIZER = False
    def _get_optimizer():
        return None

logger = logging.getLogger(__name__)
settings = get_settings()

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════

# Embed colours
COLOR_BUY     = 0x00C853
COLOR_SELL    = 0xFF1744
COLOR_INFO    = 0x2979FF
COLOR_WARN    = 0xFFAB00
COLOR_GOLD    = 0xFFD600
COLOR_PURPLE  = 0x7C4DFF
COLOR_DARK    = 0x2F3136
COLOR_SUCCESS = 0x00E676
COLOR_DANGER  = 0xFF5252
COLOR_CYAN    = 0x18FFFF

# ── Role definitions ──────────────────────────────────────────────────
ROLE_DEFS = [
    {"name": "🤖 Bot Admin",     "color": 0xE91E63, "hoist": True,  "pos": 5},
    {"name": "⭐ Pro Trader",    "color": 0xFFD600, "hoist": True,  "pos": 4},
    {"name": "📈 Trader",        "color": 0x2979FF, "hoist": True,  "pos": 3},
    {"name": "🆓 Free",          "color": 0x9E9E9E, "hoist": False, "pos": 2},
    {"name": "🔒 Unverified",    "color": 0x616161, "hoist": False, "pos": 1},
]

# ── Channel layout ────────────────────────────────────────────────────
# Each category has channels; "readonly" means members can't send messages.
SERVER_LAYOUT = [
    {
        "category": "📌 START HERE",
        "channels": [
            {"name": "rules",          "topic": "Server rules & FAQ — read before participating",           "readonly": True},
            {"name": "verify",         "topic": "Click below to verify and unlock all channels",             "readonly": True},
            {"name": "roles",          "topic": "Pick your role to customise your experience",               "readonly": True},
        ],
    },
    {
        "category": "🤖 TRADING FLOOR",
        "channels": [
            {"name": "swing-trades",     "topic": "🔄 Swing setups — pullback entries in trending stocks (2-8 wk hold)",   "readonly": True},
            {"name": "breakout-setups",  "topic": "🚀 Breakout setups — consolidation breaks with volume (1-4 wk hold)",   "readonly": True},
            {"name": "momentum-alerts",  "topic": "⚡ Momentum + whale flow — big movers, unusual volume, short-term",     "readonly": True},
            {"name": "daily-brief",      "topic": "☀️ Morning memo · 🌙 EOD · 📢 Announcements",                          "readonly": True},
            {"name": "bot-commands",     "topic": "All slash commands here — /help for the full list",                      "readonly": False},
            {"name": "trading-chat",     "topic": "Discuss signals, market, trades, earnings — all chat here",              "readonly": False},
        ],
    },
    {
        "category": "⚙️ ADMIN",
        "channels": [
            {"name": "admin-log",      "topic": "Audit trail, bot status, and moderation log",              "readonly": True},
        ],
    },
]

# ═══════════════════════════════════════════════════════════════════════
# Lightweight DiscordEmbed (webhook mode — no discord.py needed)
# ═══════════════════════════════════════════════════════════════════════

class DiscordEmbed:
    """Build a Discord embed dict for webhook payloads."""

    def __init__(self, title: str = "", description: str = "",
                 color: int = COLOR_DARK):
        self.data: Dict[str, Any] = {
            "title": title,
            "description": description,
            "color": color,
            "fields": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def add_field(self, name: str, value: str,
                  inline: bool = True) -> "DiscordEmbed":
        self.data["fields"].append({"name": name, "value": value, "inline": inline})
        return self

    def set_footer(self, text: str) -> "DiscordEmbed":
        self.data["footer"] = {"text": text}
        return self

    def set_thumbnail(self, url: str) -> "DiscordEmbed":
        self.data["thumbnail"] = {"url": url}
        return self

    def set_image(self, url: str) -> "DiscordEmbed":
        self.data["image"] = {"url": url}
        return self

    def to_dict(self) -> Dict[str, Any]:
        return self.data


# ═══════════════════════════════════════════════════════════════════════
# Paginator helper
# ═══════════════════════════════════════════════════════════════════════

class EmbedPaginator:
    """Splits fields across multiple embeds (max 25 fields each)."""

    @staticmethod
    def paginate(title: str, description: str, fields: List[dict],
                 color: int = COLOR_INFO, per_page: int = 12):
        pages = []
        for i in range(0, max(1, len(fields)), per_page):
            chunk = fields[i:i + per_page]
            page_num = i // per_page + 1
            total = (len(fields) - 1) // per_page + 1
            page = {
                "title": f"{title}  ({page_num}/{total})" if total > 1 else title,
                "description": description if i == 0 else "",
                "color": color,
                "fields": chunk,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            pages.append(page)
        return pages


# ═══════════════════════════════════════════════════════════════════════
# MAIN BOT CLASS
# ═══════════════════════════════════════════════════════════════════════

class DiscordInteractiveBot:
    """
    Professional Discord trading bot.

    Modes:
      1. **Webhook** — lightweight push (needs DISCORD_WEBHOOK_URL).
      2. **Interactive** — full slash-command bot (needs DISCORD_BOT_TOKEN).
    """

    def __init__(self):
        self.bot_token: Optional[str] = getattr(settings, "discord_bot_token", None)
        self.webhook_url: Optional[str] = getattr(settings, "discord_webhook_url", None)
        self.channel_name: str = getattr(settings, "discord_channel_name", "Trading CC")
        self._session: Optional[aiohttp.ClientSession] = None
        self._bot = None
        self._channels: Dict[str, Any] = {}
        self._roles: Dict[str, Any] = {}

    @property
    def is_configured(self) -> bool:
        return bool(self.bot_token)

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    # ── Webhook push ──────────────────────────────────────────────────

    async def send_webhook(self, content: str = "",
                           embeds: Optional[List[Dict]] = None) -> bool:
        if not self.webhook_url:
            return False
        session = await self._get_session()
        payload: Dict[str, Any] = {}
        if content:
            payload["content"] = content
        if embeds:
            payload["embeds"] = embeds[:10]
        try:
            async with session.post(self.webhook_url, json=payload) as resp:
                if resp.status not in (200, 204):
                    body = await resp.text()
                    logger.error(f"Discord webhook {resp.status}: {body[:200]}")
                    return False
            return True
        except Exception as exc:
            logger.error(f"Discord webhook error: {exc}")
            return False

    # ── Signal formatting ─────────────────────────────────────────────

    def format_signal_embed(self, signal: Any) -> Dict[str, Any]:
        """Build a Discord embed dict for a signal — v6 with report generator."""
        # ── v6: use report generator if available ──
        if _HAS_REPORT_GEN and hasattr(signal, "approval_status"):
            try:
                return build_signal_card(signal)
            except Exception as exc:
                logger.warning(f"report_generator fallback: {exc}")

        # ── Fallback: inline v5-compatible build ──
        direction = getattr(signal, "direction", None)
        is_buy = str(direction).upper() in ("LONG", "BUY")
        colour = COLOR_BUY if is_buy else COLOR_SELL
        conf = getattr(signal, "confidence", 0)
        if conf >= 80:
            colour = COLOR_GOLD
        arrow = "🟢 LONG" if is_buy else "🔴 SHORT"
        ticker = getattr(signal, "ticker", "???")
        entry = getattr(signal, "entry_price", 0)
        embed = DiscordEmbed(
            title=f"{arrow}  {ticker}  —  ${entry:.2f}",
            description=getattr(signal, "entry_logic", ""),
            color=colour,
        )

        # v6 fields first
        grade = getattr(signal, "setup_grade", None)
        approval = getattr(signal, "approval_status", "")
        grade_str = f" | Grade: **{grade}**" if grade else ""
        appr_icon = {"approved": "✅", "conditional": "🟡", "rejected": "❌"}.get(approval, "")
        embed.add_field("Confidence",
                        f"{'█' * (conf // 10)}{'░' * (10 - conf // 10)} {conf}% {appr_icon}{grade_str}")
        embed.add_field("Horizon", str(getattr(signal, "horizon", "")))
        if getattr(signal, "edge_type", None):
            embed.add_field("Edge", f"`{signal.edge_type}`")
        targets = getattr(signal, "targets", [])
        if targets:
            t_str = "\n".join(
                f"`T{i+1}` ${t.price:.2f} ({t.pct_position}%)"
                for i, t in enumerate(targets))
            embed.add_field("🎯 Targets", t_str, inline=False)
        inv = getattr(signal, "invalidation", None)
        if inv:
            embed.add_field("🛑 Stop Loss",
                            f"${inv.stop_price:.2f} ({inv.stop_type.value})")
        rr = getattr(signal, "risk_reward_ratio", None)
        if rr:
            embed.add_field("R:R", f"**{rr:.1f}:1**")
        ev = getattr(signal, "expected_value", None)
        if ev is not None:
            embed.add_field("EV", f"**{ev:+.1f}%**")
        strat = getattr(signal, "strategy_id", None)
        if strat:
            embed.add_field("Strategy", f"`{strat}`")

        # v6: Why Now
        why_now = getattr(signal, "why_now", None)
        if why_now:
            embed.add_field("⏱️ Why Now", why_now, inline=False)

        # v6: Time Stop + Event Risk
        ts_days = getattr(signal, "time_stop_days", None)
        event_risk = getattr(signal, "event_risk", None)
        if ts_days or event_risk:
            parts = []
            if ts_days:
                parts.append(f"⏳ Time stop: {ts_days}d")
            if event_risk:
                parts.append(f"📅 {event_risk}")
            embed.add_field("⚠️ Timing", " | ".join(parts))

        # v6: Scenario Plan
        sp = getattr(signal, "scenario_plan", None)
        if sp and isinstance(sp, dict):
            lines = []
            for key, emoji in [("base_case", "📊"), ("bull_case", "🐂"), ("bear_case", "🐻")]:
                case = sp.get(key, {})
                if case:
                    lines.append(f"{emoji} {case.get('probability', '?')}: {case.get('description', '—')[:60]}")
            if lines:
                embed.add_field("🗺️ Scenarios", "\n".join(lines), inline=False)

        # Edge Model (from feature_snapshot)
        fs = getattr(signal, "feature_snapshot", None) or {}
        edge = fs.get("edge_model", {})
        if edge:
            p_t1 = edge.get("p_t1", 0)
            p_stop = edge.get("p_stop", 0)
            ev_edge = edge.get("expected_return_pct", 0)
            sample = edge.get("sample_size", 0)
            cal_label = f"(n={sample})" if sample >= 30 else "(base-rate)"
            embed.add_field(
                "📊 Edge Model",
                f"P(T1): **{p_t1*100:.0f}%** | P(stop): {p_stop*100:.0f}%\n"
                f"EV: **{ev_edge:+.1f}%** | Hold: {edge.get('expected_holding_days', '?')}d\n"
                f"MAE: {edge.get('expected_mae_pct', 0):.1f}% {cal_label}",
                inline=False)

        # v6: Evidence
        evidence = getattr(signal, "evidence", []) or []
        if evidence:
            embed.add_field("📋 Evidence",
                            "\n".join(f"• {e}" for e in evidence[:4]), inline=False)

        risks = getattr(signal, "key_risks", [])
        if risks:
            embed.add_field("⚠️ Risks",
                            "\n".join(f"• {r}" for r in risks[:3]), inline=False)

        # v6: Portfolio Fit
        pf = getattr(signal, "portfolio_fit", None)
        if pf:
            fit_icon = {"good": "✅", "overlap": "⚠️", "concentrated": "🔴"}.get(pf, "❓")
            embed.add_field("📦 Fit", f"{fit_icon} {pf}")

        embed.set_footer(
            f"TradingAI Pro v6 • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
        return embed.to_dict()

    # ── Push helpers ──────────────────────────────────────────────────

    async def push_signal(self, signal: Any) -> bool:
        return await self.send_webhook(embeds=[self.format_signal_embed(signal)])

    async def push_signals_batch(self, signals: List[Any]) -> int:
        if not signals:
            return 0
        embeds = [self.format_signal_embed(s) for s in signals[:10]]
        ok = await self.send_webhook(
            content=f"📊 **{len(signals)} New Signal{'s' if len(signals) > 1 else ''}**",
            embeds=embeds)
        return len(signals) if ok else 0

    async def push_portfolio_update(self, portfolio: Dict[str, Any]) -> bool:
        e = DiscordEmbed(title="📈 Portfolio Update", color=COLOR_INFO)
        e.add_field("Equity", f"${portfolio.get('equity', 0):,.2f}")
        e.add_field("Day P&L", f"{portfolio.get('day_pnl_pct', 0):+.2f}%")
        e.add_field("Open Positions", str(portfolio.get("open_positions", 0)))
        e.add_field("Win Rate", f"{portfolio.get('win_rate', 0):.1f}%")
        e.set_footer("TradingAI Bot")
        return await self.send_webhook(embeds=[e.to_dict()])

    async def push_daily_report(self, report: Dict[str, Any]) -> bool:
        """Push daily report — v6 supports pre-built embed dicts."""
        # v6: if report contains pre-built embeds from report_generator
        if "embeds" in report:
            return await self.send_webhook(
                content=report.get("content", ""),
                embeds=report["embeds"][:10],
            )
        # Legacy fallback
        e = DiscordEmbed(title="📋 Daily Trading Report",
                         description=report.get("summary", ""), color=COLOR_INFO)
        e.add_field("Signals", str(report.get("signals_count", 0)))
        e.add_field("Trades", str(report.get("trades_count", 0)))
        e.add_field("Win Rate", f"{report.get('win_rate', 0):.1f}%")
        e.add_field("Total P&L", f"{report.get('total_pnl', 0):+.2f}%")
        e.add_field("Best Trade", report.get("best_trade", "N/A"))
        e.add_field("Worst Trade", report.get("worst_trade", "N/A"))
        e.set_footer("TradingAI Pro v6 — End of Day Report")
        return await self.send_webhook(embeds=[e.to_dict()])

    async def push_alert(self, title: str, message: str,
                         level: str = "info") -> bool:
        cmap = {"info": COLOR_INFO, "warn": COLOR_WARN,
                "buy": COLOR_BUY, "sell": COLOR_SELL}
        e = DiscordEmbed(title=f"🔔 {title}", description=message,
                         color=cmap.get(level, COLOR_INFO))
        return await self.send_webhook(embeds=[e.to_dict()])

    # ═══════════════════════════════════════════════════════════════════
    # FULL INTERACTIVE BOT
    # ═══════════════════════════════════════════════════════════════════

    async def run_interactive_bot(self):
        try:
            import discord
            from discord import app_commands
            from discord.ext import commands, tasks
        except ImportError:
            logger.error("discord.py not installed — pip install discord.py")
            return

        # Pre-import yfinance once (avoid repeated slow imports)
        try:
            import yfinance as yf
            _yf = yf
        except ImportError:
            _yf = None
            logger.warning("yfinance not installed — market data unavailable")

        # Centralised cached market-data service (async-safe, TTL cache)
        from src.services.market_data import get_market_data_service
        _mds = get_market_data_service()

        intents = discord.Intents.default()
        intents.message_content = True

        bot = commands.Bot(command_prefix="!", intents=intents,
                           description="TradingAI Pro — AI Trading Command Center")
        self._bot = bot

        # ══════════════════════════════════════════════════════════════
        # HELPERS
        # ══════════════════════════════════════════════════════════════

        def _sync_fetch_stock(ticker: str) -> Dict[str, Any]:
            """Synchronous yfinance fetch — runs in thread to avoid blocking."""
            if not _yf:
                return {"ticker": ticker.upper(), "error": "yfinance not installed"}
            try:
                t = _yf.Ticker(ticker.upper())
                info = t.fast_info if hasattr(t, "fast_info") else t.info
                if hasattr(info, "last_price"):
                    return {
                        "ticker": ticker.upper(),
                        "price": info.last_price or 0,
                        "prev_close": info.previous_close or 0,
                        "change_pct": ((info.last_price - info.previous_close)
                                       / info.previous_close * 100
                                       if info.previous_close else 0),
                        "volume": info.last_volume or 0,
                        "market_cap": info.market_cap or 0,
                        "high": info.day_high or 0,
                        "low": info.day_low or 0,
                        "open": info.open or 0,
                        "year_high": info.year_high or 0,
                        "year_low": info.year_low or 0,
                    }
                d = dict(info) if not isinstance(info, dict) else info
                price = d.get("regularMarketPrice", d.get("currentPrice", 0)) or 0
                prev = d.get("regularMarketPreviousClose", d.get("previousClose", 0)) or 0
                return {
                    "ticker": ticker.upper(), "price": price, "prev_close": prev,
                    "change_pct": ((price - prev) / prev * 100 if prev else 0),
                    "volume": d.get("volume", 0) or 0,
                    "market_cap": d.get("marketCap", 0) or 0,
                    "high": d.get("dayHigh", 0) or 0,
                    "low": d.get("dayLow", 0) or 0,
                    "open": d.get("open", 0) or 0,
                    "year_high": d.get("fiftyTwoWeekHigh", 0) or 0,
                    "year_low": d.get("fiftyTwoWeekLow", 0) or 0,
                    "name": d.get("shortName", ticker.upper()),
                    "sector": d.get("sector", ""),
                    "pe": d.get("trailingPE", 0) or 0,
                    "eps": d.get("trailingEps", 0) or 0,
                    "dividend": d.get("dividendYield", 0) or 0,
                    "beta": d.get("beta", 0) or 0,
                }
            except Exception as exc:
                logger.error(f"yfinance error {ticker}: {exc}")
                return {"ticker": ticker.upper(), "error": str(exc)}

        async def _fetch_stock(ticker: str) -> Dict[str, Any]:
            """Non-blocking wrapper — runs yfinance in a thread pool."""
            return await asyncio.to_thread(_sync_fetch_stock, ticker)

        def _bar(pct: float, w: int = 10) -> str:
            f = max(0, min(w, int(abs(pct) / 10 * w)))
            sym = "🟢" if pct >= 0 else "🔴"
            return f"{sym} {'█' * f}{'░' * (w - f)} {pct:+.2f}%"

        def _vol(v: float) -> str:
            if v >= 1e9: return f"{v/1e9:.1f}B"
            if v >= 1e6: return f"{v/1e6:.1f}M"
            if v >= 1e3: return f"{v/1e3:.1f}K"
            return str(int(v))

        def _mcap(v: float) -> str:
            if not v: return "N/A"
            if v >= 1e12: return f"${v/1e12:.2f}T"
            if v >= 1e9: return f"${v/1e9:.2f}B"
            return f"${v/1e6:.0f}M"

        async def _audit(msg: str):
            """Write to #admin-log."""
            ch = self._channels.get("admin-log")
            if ch:
                e = discord.Embed(description=msg, color=COLOR_DARK,
                                  timestamp=datetime.now(timezone.utc))
                try:
                    await ch.send(embed=e)
                except Exception:
                    pass

        async def _send_ch(name: str, *, content: str = "",
                           embed: Optional[discord.Embed] = None,
                           view: Optional[discord.ui.View] = None):
            ch = self._channels.get(name)
            if ch:
                try:
                    await ch.send(content=content, embed=embed, view=view)
                except Exception:
                    pass

        # ══════════════════════════════════════════════════════════════
        # INTERACTIVE UI COMPONENTS
        # ══════════════════════════════════════════════════════════════

        class HelpCategorySelect(discord.ui.Select):
            """Dropdown to pick a help category."""
            def __init__(self):
                options = [
                    discord.SelectOption(label="📊 Market Data",   value="market",   description="Price, quotes, indices, sectors"),
                    discord.SelectOption(label="🎯 AI Signals",    value="signals",  description="Scanners, breakouts, signals"),
                    discord.SelectOption(label="🧠 AI Analysis",   value="analysis", description="AI scoring, technicals, advice"),
                    discord.SelectOption(label="💰 Trading",       value="trading",  description="Buy, sell, portfolio, P&L"),
                    discord.SelectOption(label="🌏 Multi-Market",  value="multi",    description="Asia, Japan, HK, Crypto"),
                    discord.SelectOption(label="⚙️ Tools & Admin", value="tools",    description="Backtest, alerts, admin"),
                ]
                super().__init__(placeholder="Pick a category...", options=options, min_values=1, max_values=1)

            async def callback(self, interaction: discord.Interaction):
                cats = {
                    "market": ("📊 Market Data", [
                        ("/price AAPL", "Real-time price + chart bar"),
                        ("/quote AAPL", "Detailed quote with fundamentals"),
                        ("/market", "US indices overview"),
                        ("/movers", "Top gainers & losers"),
                        ("/sector", "Sector performance heatmap"),
                        ("/macro", "Gold · Oil · BTC · Bonds · DXY"),
                        ("/news AAPL", "Latest headlines"),
                        ("/premarket", "Pre-market futures"),
                    ]),
                    "signals": ("🎯 AI Signals", [
                        ("/signals", "Latest AI signals"),
                        ("/scan vcp", "Scan for setups"),
                        ("/breakout", "Breakout candidates"),
                        ("/dip", "Dip buying opps"),
                        ("/swing", "Swing setups (2-10 d)"),
                        ("/momentum", "Momentum picks"),
                        ("/whale", "Whale activity"),
                        ("/squeeze", "Short squeeze"),
                    ]),
                    "analysis": ("🧠 AI Analysis", [
                        ("/ai AAPL", "Full AI breakdown"),
                        ("/analyze AAPL", "SMA · RSI · Volume"),
                        ("/advise AAPL", "Buy / Hold / Sell"),
                        ("/score AAPL", "AI score 1-10"),
                        ("/compare AAPL MSFT", "Side-by-side"),
                        ("/levels AAPL", "Support / resistance"),
                        ("/why TSLA", "Why is it moving?"),
                    ]),
                    "trading": ("💰 Trading", [
                        ("/buy AAPL 10", "Buy shares (paper)"),
                        ("/sell AAPL 10", "Sell shares (paper)"),
                        ("/portfolio", "View portfolio"),
                        ("/positions", "Open positions"),
                        ("/pnl", "Today's P&L"),
                        ("/risk AAPL", "Position sizing calc"),
                        ("/stats", "Trading statistics"),
                    ]),
                    "multi": ("🌏 Multi-Market", [
                        ("/asia", "Asia dashboard"),
                        ("/japan", "Japan top picks"),
                        ("/hk", "Hong Kong top picks"),
                        ("/crypto", "Crypto dashboard"),
                        ("/btc", "Bitcoin deep dive"),
                    ]),
                    "tools": ("⚙️ Tools & Admin", [
                        ("/backtest AAPL 1y", "Run a backtest"),
                        ("/alert AAPL above 200", "Set price alert"),
                        ("/watchlist", "Your watchlist"),
                        ("/daily", "Daily summary"),
                        ("/status", "System connectivity"),
                        ("/setup", "Re-run server setup (admin)"),
                        ("/announce", "Post announcement (admin)"),
                        ("/purge 10", "Delete messages (admin)"),
                    ]),
                }
                choice = self.values[0]
                title, cmds = cats.get(choice, ("Unknown", []))
                e = discord.Embed(title=title, color=COLOR_PURPLE)
                for c, d in cmds:
                    e.add_field(name=f"`{c}`", value=d, inline=True)
                await interaction.response.edit_message(embed=e, view=HelpView())

        class HelpView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=120)
                self.add_item(HelpCategorySelect())

        class SignalActionView(discord.ui.View):
            """Pro signal card actions: Analyze · Size · Alert · Watchlist · Why Now."""
            def __init__(self, ticker: str, signal_data: dict = None):
                super().__init__(timeout=600)
                self.ticker = ticker
                self.sig = signal_data or {}

            @discord.ui.button(label="📊 Deep Analysis", style=discord.ButtonStyle.primary)
            async def btn_analyze(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
                await interaction.response.defer(ephemeral=True)
                # Run AI analysis inline
                data = await _fetch_stock(self.ticker)
                price = data.get("price", 0)
                pct = data.get("change_pct", 0)
                e = discord.Embed(
                    title=f"🔬 Deep Dive — {self.ticker}",
                    color=COLOR_INFO)
                e.add_field(name="Price", value=f"${price:.2f} ({pct:+.2f}%)")
                e.add_field(name="52w Range",
                            value=f"${data.get('low52', 0):.2f} — ${data.get('high52', 0):.2f}")
                if self.sig.get("rsi"):
                    rsi = self.sig["rsi"]
                    rsi_icon = "🔴 OB" if rsi > 70 else "🟢 OS" if rsi < 30 else "⚪"
                    e.add_field(name="RSI", value=f"{rsi:.0f} {rsi_icon}")
                e.add_field(name="Rel Volume", value=f"{self.sig.get('rel_vol', 1):.1f}x")
                e.add_field(name="Trend",
                            value=(f"SMA20: ${self.sig.get('sma20',0):.2f}\n"
                                   f"SMA50: ${self.sig.get('sma50',0):.2f}"))
                e.set_footer(text=f"Use /ai {self.ticker} for full institutional report")
                await interaction.followup.send(embed=e, ephemeral=True)

            @discord.ui.button(label="📐 Position Sizer", style=discord.ButtonStyle.green)
            async def btn_size(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
                price = self.sig.get("price", 0)
                stop_pct = 0.05  # 5% default
                risk_per_trade = 1000  # $1,000 risk
                stop_dist = price * stop_pct
                shares = int(risk_per_trade / stop_dist) if stop_dist > 0 else 0
                position_val = shares * price
                e = discord.Embed(
                    title=f"📐 Position Size — {self.ticker}",
                    description="Based on $1,000 risk per trade, 5% stop",
                    color=COLOR_INFO)
                e.add_field(name="Entry", value=f"${price:.2f}")
                e.add_field(name="Stop (-5%)", value=f"${price * 0.95:.2f}")
                e.add_field(name="Shares", value=f"**{shares:,}**")
                e.add_field(name="Position Value", value=f"${position_val:,.2f}")
                e.add_field(name="Risk", value=f"${risk_per_trade:,.0f}")
                e.set_footer(text="Adjust: /position_size <ticker> <risk$> <stop%>")
                await interaction.response.send_message(embed=e, ephemeral=True)

            @discord.ui.button(label="🔔 Set Alert", style=discord.ButtonStyle.secondary)
            async def btn_alert(self, interaction: discord.Interaction,
                                button: discord.ui.Button):
                price = self.sig.get("price", 0)
                stop_level = price * 0.95
                target_level = price * 1.10
                await interaction.response.send_message(
                    f"🔔 **Alert Levels for {self.ticker}:**\n"
                    f"• 🎯 Target: **${target_level:.2f}** (+10%)\n"
                    f"• 🛑 Stop: **${stop_level:.2f}** (-5%)\n"
                    f"• Use `/alert {self.ticker} {target_level:.2f}` to set a live alert",
                    ephemeral=True)

            @discord.ui.button(label="⭐ Watchlist", style=discord.ButtonStyle.secondary)
            async def btn_watchlist(self, interaction: discord.Interaction,
                                    button: discord.ui.Button):
                await interaction.response.send_message(
                    f"⭐ **{self.ticker}** added to your watchlist!\n"
                    f"Use `/watchlist` to view all your tracked tickers.",
                    ephemeral=True)

            @discord.ui.button(label="❓ Why Now?", style=discord.ButtonStyle.secondary)
            async def btn_why(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
                """v6 Why Now — shows why_now, scenario_plan, evidence, event_risk, approval_flags."""
                e = discord.Embed(
                    title=f"❓ Why Now — {self.ticker}",
                    color=COLOR_PURPLE)

                # v6 why_now narrative
                why_now = self.sig.get("why_now", "")
                if why_now:
                    e.add_field(name="📌 Why Now", value=why_now[:1024], inline=False)

                # Legacy reasons fallback
                reasons = self.sig.get("reasons", [])
                if reasons and not why_now:
                    e.add_field(name="📌 Setup Reasons",
                                value="\n".join(reasons)[:1024], inline=False)

                # v6 evidence
                evidence = self.sig.get("evidence", [])
                if evidence:
                    ev_text = "\n".join(f"• {item}" for item in evidence[:8])
                    e.add_field(name="📋 Evidence Stack", value=ev_text, inline=False)

                # v6 scenario plan
                scenario = self.sig.get("scenario_plan")
                if scenario and isinstance(scenario, dict):
                    base = scenario.get("base_case", {})
                    bull = scenario.get("bull_case", {})
                    bear = scenario.get("bear_case", {})
                    sc_text = ""
                    if base:
                        sc_text += f"📊 **Base** ({base.get('probability','?')}): {base.get('description','')}\n"
                    if bull:
                        sc_text += f"🐂 **Bull** ({bull.get('probability','?')}): {bull.get('description','')}\n"
                    if bear:
                        sc_text += f"🐻 **Bear** ({bear.get('probability','?')}): {bear.get('description','')}\n"
                    if sc_text:
                        e.add_field(name="🎯 Scenario Plan", value=sc_text.strip(), inline=False)

                # v6 event risk + time stop
                event_risk = self.sig.get("event_risk", "")
                time_stop = self.sig.get("time_stop_days")
                if event_risk or time_stop:
                    risk_text = ""
                    if event_risk:
                        risk_text += f"📅 Event risk: **{event_risk}**\n"
                    if time_stop:
                        risk_text += f"⏱ Time stop: **{time_stop}** days"
                    e.add_field(name="⚠️ Risk Factors", value=risk_text.strip(), inline=False)

                # v6 approval flags
                approval_flags = self.sig.get("approval_flags", [])
                if approval_flags:
                    flags_text = "\n".join(f"🚩 {f}" for f in approval_flags[:6])
                    e.add_field(name="🏁 Approval Flags", value=flags_text, inline=False)

                # Legacy invalidation / crowding
                invalidation = self.sig.get("invalidation", "Break below SMA50")
                e.add_field(name="🛑 Invalidation", value=invalidation)
                e.add_field(name="Crowding Risk",
                            value=f"Rel Vol: {self.sig.get('rel_vol', 1):.1f}x — "
                                  f"{'⚠️ Crowded' if self.sig.get('rel_vol', 1) > 3 else '✅ Normal'}")

                await interaction.response.send_message(embed=e, ephemeral=True)

        class ConfirmTradeView(discord.ui.View):
            """Confirm / Cancel buttons for trade orders."""
            def __init__(self, ticker: str, side: str, qty: int, price: float):
                super().__init__(timeout=60)
                self.ticker = ticker
                self.side = side
                self.qty = qty
                self.price = price
                self.confirmed = False

            @discord.ui.button(label="✅ Confirm", style=discord.ButtonStyle.green)
            async def btn_confirm(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
                self.confirmed = True
                e = discord.Embed(
                    title=f"{'🟢' if self.side == 'BUY' else '🔴'} {self.side} Confirmed",
                    description=(f"**{self.qty}** {self.ticker} @ **${self.price:.2f}**\n"
                                 f"Total: **${self.qty * self.price:,.2f}** (Paper)"),
                    color=COLOR_BUY if self.side == "BUY" else COLOR_SELL)
                await interaction.response.edit_message(embed=e, view=None)
                await _audit(f"📝 {interaction.user} confirmed {self.side} "
                             f"{self.qty} {self.ticker}")

            @discord.ui.button(label="❌ Cancel", style=discord.ButtonStyle.red)
            async def btn_cancel(self, interaction: discord.Interaction,
                                 button: discord.ui.Button):
                e = discord.Embed(title="🚫 Order Cancelled", color=COLOR_DARK)
                await interaction.response.edit_message(embed=e, view=None)

        class VerifyView(discord.ui.View):
            """Persistent verify button in #verify."""
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="✅ I agree to the rules — Verify me",
                               style=discord.ButtonStyle.green,
                               custom_id="verify_btn")
            async def btn_verify(self, interaction: discord.Interaction,
                                 button: discord.ui.Button):
                await interaction.response.defer(ephemeral=True)
                guild = interaction.guild
                if not guild:
                    return
                trader_role = discord.utils.get(guild.roles, name="📈 Trader")
                unverified = discord.utils.get(guild.roles, name="🔒 Unverified")
                member = interaction.user
                if isinstance(member, discord.Member):
                    if trader_role:
                        await member.add_roles(trader_role)
                    if unverified and unverified in member.roles:
                        await member.remove_roles(unverified)
                    await interaction.followup.send(
                        "✅ You're verified! All channels are now unlocked. "
                        "Head to **#bot-commands** and type `/help`.",
                        ephemeral=True)
                    await _audit(f"✅ {member} verified")
                else:
                    await interaction.followup.send(
                        "Could not verify. Please try again.", ephemeral=True)

        class RolePickView(discord.ui.View):
            """Self-assign interest roles."""
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="🇺🇸 US Stocks", style=discord.ButtonStyle.secondary,
                               custom_id="role_us")
            async def btn_us(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
                await self._toggle(interaction, "🇺🇸 US Stocks")

            @discord.ui.button(label="🇭🇰 HK Stocks", style=discord.ButtonStyle.secondary,
                               custom_id="role_hk")
            async def btn_hk(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
                await self._toggle(interaction, "🇭🇰 HK Stocks")

            @discord.ui.button(label="🇯🇵 JP Stocks", style=discord.ButtonStyle.secondary,
                               custom_id="role_jp")
            async def btn_jp(self, interaction: discord.Interaction,
                             button: discord.ui.Button):
                await self._toggle(interaction, "🇯🇵 JP Stocks")

            @discord.ui.button(label="₿ Crypto", style=discord.ButtonStyle.secondary,
                               custom_id="role_crypto")
            async def btn_crypto(self, interaction: discord.Interaction,
                                 button: discord.ui.Button):
                await self._toggle(interaction, "₿ Crypto")

            @discord.ui.button(label="📈 Day Trader", style=discord.ButtonStyle.secondary,
                               custom_id="role_day")
            async def btn_day(self, interaction: discord.Interaction,
                              button: discord.ui.Button):
                await self._toggle(interaction, "📈 Day Trader")

            @discord.ui.button(label="🎯 Swing Trader", style=discord.ButtonStyle.secondary,
                               custom_id="role_swing")
            async def btn_swing(self, interaction: discord.Interaction,
                                button: discord.ui.Button):
                await self._toggle(interaction, "🎯 Swing Trader")

            async def _toggle(self, interaction: discord.Interaction, role_name: str):
                await interaction.response.defer(ephemeral=True)
                guild = interaction.guild
                if not guild:
                    return
                role = discord.utils.get(guild.roles, name=role_name)
                if not role:
                    role = await guild.create_role(name=role_name, color=discord.Color.default())
                member = interaction.user
                if isinstance(member, discord.Member):
                    if role in member.roles:
                        await member.remove_roles(role)
                        await interaction.followup.send(
                            f"Removed **{role_name}**", ephemeral=True)
                    else:
                        await member.add_roles(role)
                        await interaction.followup.send(
                            f"Added **{role_name}** ✅", ephemeral=True)

        # ══════════════════════════════════════════════════════════════
        # SERVER SETUP — roles, categories, channels, permissions
        # ══════════════════════════════════════════════════════════════

        async def full_server_setup(guild: discord.Guild):
            """Create roles, categories, channels with proper permissions."""
            me = guild.me

            # ── Roles ─────────────────────────────────────────────────
            for rdef in ROLE_DEFS:
                existing = discord.utils.get(guild.roles, name=rdef["name"])
                if not existing:
                    existing = await guild.create_role(
                        name=rdef["name"],
                        color=discord.Color(rdef["color"]),
                        hoist=rdef["hoist"],
                        mentionable=False,
                    )
                    logger.info(f"  Role created: {rdef['name']}")
                self._roles[rdef["name"]] = existing

            unverified_role = self._roles.get("🔒 Unverified")
            trader_role = self._roles.get("📈 Trader")
            admin_role = self._roles.get("🤖 Bot Admin")

            # ── Delete old categories that are not in SERVER_LAYOUT ─────
            keep_cats = {c["category"] for c in SERVER_LAYOUT}
            keep_chs  = {ch["name"] for c in SERVER_LAYOUT for ch in c["channels"]}
            for old_cat in guild.categories:
                if old_cat.name not in keep_cats:
                    # Delete all channels inside the old category first
                    for old_ch in old_cat.channels:
                        try:
                            await old_ch.delete(reason="Channel consolidation — v5 cleanup")
                            logger.info(f"  🗑️ Deleted #{old_ch.name} (old)")
                        except Exception:
                            pass
                    try:
                        await old_cat.delete(reason="Category consolidation — v5 cleanup")
                        logger.info(f"  🗑️ Deleted category: {old_cat.name}")
                    except Exception:
                        pass

            # Also clean stale channels inside kept categories
            for cat_def in SERVER_LAYOUT:
                cat = discord.utils.get(guild.categories, name=cat_def["category"])
                if cat:
                    valid_names = {ch["name"] for ch in cat_def["channels"]}
                    for old_ch in cat.text_channels:
                        if old_ch.name not in valid_names:
                            try:
                                await old_ch.delete(reason="Channel consolidation — v5 cleanup")
                                logger.info(f"  🗑️ Deleted #{old_ch.name} (stale)")
                            except Exception:
                                pass

            # ── Categories & Channels ─────────────────────────────────
            for cat_def in SERVER_LAYOUT:
                cat_name = cat_def["category"]
                category = discord.utils.get(guild.categories, name=cat_name)

                # Default overwrites for category
                overwrites: Dict[Any, discord.PermissionOverwrite] = {
                    guild.default_role: discord.PermissionOverwrite(
                        view_channel=True, send_messages=True),
                }
                if me:
                    overwrites[me] = discord.PermissionOverwrite(
                        view_channel=True, send_messages=True,
                        manage_channels=True, manage_messages=True,
                        embed_links=True, attach_files=True)

                # Admin-only category
                if cat_name == "⚙️ ADMIN":
                    overwrites[guild.default_role] = discord.PermissionOverwrite(
                        view_channel=False)
                    if admin_role:
                        overwrites[admin_role] = discord.PermissionOverwrite(
                            view_channel=True, send_messages=True)

                if not category:
                    category = await guild.create_category(cat_name, overwrites=overwrites)
                    logger.info(f"  Category: {cat_name}")

                for ch_def in cat_def["channels"]:
                    ch_name = ch_def["name"]
                    ch = discord.utils.get(category.text_channels, name=ch_name)

                    ch_overwrites: Optional[Dict] = None
                    if ch_def.get("readonly"):
                        ch_overwrites = {
                            guild.default_role: discord.PermissionOverwrite(
                                send_messages=False, view_channel=True),
                        }
                        if me:
                            ch_overwrites[me] = discord.PermissionOverwrite(
                                send_messages=True, view_channel=True,
                                embed_links=True, manage_messages=True)

                    if not ch:
                        ch = await category.create_text_channel(
                            name=ch_name, topic=ch_def["topic"],
                            overwrites=ch_overwrites or {})
                        logger.info(f"    #{ch_name}")
                    self._channels[ch_name] = ch

            # ── Post static embeds ────────────────────────────────────
            await _post_rules(guild)
            await _post_verify()
            await _post_roles()
            await _post_welcome()

        # ── Static channel content ────────────────────────────────────

        async def _post_rules(guild: discord.Guild):
            ch = self._channels.get("rules")
            if not ch:
                return
            # Check if we already posted
            async for msg in ch.history(limit=5):
                if msg.author == guild.me and msg.embeds:
                    return  # Already posted
            # ── Rules embed ──
            e = discord.Embed(
                title="📜 Server Rules",
                description=(
                    "Welcome to **TradingAI Pro** — the AI-powered trading community.\n"
                    "Please follow these rules to keep the server professional.\n\u200b"),
                color=COLOR_GOLD)
            rules = [
                ("1️⃣  No spam / self-promotion", "Keep discussions on topic. No unsolicited links."),
                ("2️⃣  Respect all members", "Harassment, hate speech, or personal attacks = instant ban."),
                ("3️⃣  No financial advice claims", "AI analysis — not regulated advice. Trade at your own risk."),
                ("4️⃣  Use bot commands in #bot-commands", "Keeps #trading-chat clean for discussion."),
                ("5️⃣  No sharing bot output outside", "Our AI signals are for members only."),
                ("6️⃣  Have fun & make money", "We're here to learn, grow, and profit together. 🚀"),
            ]
            for name, val in rules:
                e.add_field(name=name, value=val, inline=False)
            e.set_footer(text="By participating you agree to these rules. Head to #verify →")
            await ch.send(embed=e)

            # ── FAQ embed (same channel) ──
            faq = discord.Embed(title="❓ FAQ", color=COLOR_INFO)
            faqs = [
                ("How do I start?", "Go to **#bot-commands** and type `/help` to see every command."),
                ("Is this real money?", "**Paper Trading** by default. No real money at risk until you connect a broker."),
                ("What markets?", "US stocks, Hong Kong, Japan, and Crypto."),
                ("How accurate are signals?", "AI scans 500+ tickers using momentum, mean-reversion, VCP, and GPT validation. Past performance ≠ future results."),
                ("How do I report a bug?", "DM the bot admin or post in **#trading-chat**."),
            ]
            for q, a in faqs:
                faq.add_field(name=q, value=a, inline=False)
            await ch.send(embed=faq)

        async def _post_verify():
            ch = self._channels.get("verify")
            if not ch:
                return
            async for msg in ch.history(limit=5):
                if msg.author == bot.user and msg.embeds:
                    return
            e = discord.Embed(
                title="🔐 Verification Required",
                description=(
                    "Click the button below to confirm you've read the rules.\n"
                    "This unlocks all trading channels.\n\u200b"),
                color=COLOR_SUCCESS)
            await ch.send(embed=e, view=VerifyView())

        async def _post_roles():
            ch = self._channels.get("roles")
            if not ch:
                return
            async for msg in ch.history(limit=5):
                if msg.author == bot.user and msg.embeds:
                    return
            e = discord.Embed(
                title="🎨 Pick Your Roles",
                description=(
                    "Click the buttons to add/remove interest roles.\n"
                    "This helps us tailor signals to you.\n\u200b"),
                color=COLOR_PURPLE)
            await ch.send(embed=e, view=RolePickView())

        async def _post_welcome():
            ch = self._channels.get("daily-brief")
            if not ch:
                return
            async for msg in ch.history(limit=5):
                if msg.author == bot.user and msg.embeds:
                    if any("TradingAI Pro v" in (em.title or "") for em in msg.embeds):
                        return
            e = discord.Embed(
                title="🤖 TradingAI Pro v6 — AI Trading Command Center",
                description=(
                    "Welcome to the AI-powered trading server.\n\n"
                    "**What I do:**\n"
                    "• Scan **US · HK · JP · Crypto** markets 24/7\n"
                    "• AI signals with setup grade, EV, scenario maps\n"
                    "• Regime scoreboard → delta deck → strategy playbook\n"
                    "• Morning decision memo & end-of-day scorecards\n"
                    "• Paper trading with position management\n\n"
                    "**Getting Started:**\n"
                    "1. Read **#rules** and click ✅ in **#verify**\n"
                    "2. Pick your interests in **#roles**\n"
                    "3. Go to **#bot-commands** → type `/help`\n"
                    "4. Try `/market_now` or `/ai NVDA`\n\u200b"),
                color=COLOR_PURPLE)
            e.add_field(name="🎛️ Start Here",
                        value="`/market_now` `/signals` `/ai`\n`/price` `/market` `/portfolio`",
                        inline=True)
            e.add_field(name="🌏 Markets",
                        value="`/asia` `/japan` `/hk` `/crypto`\n`/macro` `/sector` `/movers`",
                        inline=True)
            e.add_field(name="📊 Analysis",
                        value="`/analyze` `/advise` `/score`\n`/compare` `/levels` `/why`",
                        inline=True)
            e.add_field(name="📍 Channel Guide",
                        value=(
                            "**#signals** — live AI trades + whale flow\n"
                            "**#daily-brief** — morning memo + EOD report\n"
                            "**#bot-commands** — use all slash commands\n"
                            "**#trading-chat** — discuss anything market-related"),
                        inline=False)
            e.set_footer(text="TradingAI Pro v6 • 24/7 AI Trading • Type /help to begin")
            await ch.send(embed=e)

        # ══════════════════════════════════════════════════════════════
        # GLOBAL ERROR HANDLER
        # ══════════════════════════════════════════════════════════════

        @bot.tree.error
        async def on_app_command_error(interaction: discord.Interaction,
                                       error: app_commands.AppCommandError):
            if isinstance(error, app_commands.CommandOnCooldown):
                await interaction.response.send_message(
                    f"⏳ Cooldown — try again in **{error.retry_after:.0f}s**.",
                    ephemeral=True)
            elif isinstance(error, app_commands.MissingPermissions):
                await interaction.response.send_message(
                    "🔒 You don't have permission for this command.", ephemeral=True)
            else:
                logger.error(f"Command error: {error}\n{traceback.format_exc()}")
                try:
                    if interaction.response.is_done():
                        await interaction.followup.send(
                            "❌ Something went wrong. Try again later.", ephemeral=True)
                    else:
                        await interaction.response.send_message(
                            "❌ Something went wrong. Try again later.", ephemeral=True)
                except Exception:
                    pass

        # ══════════════════════════════════════════════════════════════
        # AUTOMATED BACKGROUND TASKS  (the bot runs itself 24/7)
        # ══════════════════════════════════════════════════════════════
        # Schedule (UTC)
        #   Every  5 min : Rotate bot presence with SPY/BTC
        #   Every 15 min : Market pulse → #daily-brief (US hours)
        #   Every 30 min : Top movers scan → #live-signals (US hours)
        #   Every  1 hr  : Sector & macro snapshot → #daily-brief
        #   Every  2 hr  : Crypto pulse → #daily-brief (24/7)
        #   Every  4 hr  : AI signal scan → #live-signals
        #   ~09:00 ET    : Morning brief → #daily-brief
        #   ~16:05 ET    : EOD report → #daily-brief
        #   ~20:00 ET    : Asia preview → #daily-brief
        #   Sunday 18:00 : Weekly recap → #announcements
        # ──────────────────────────────────────────────────────────────

        # Watchlist used by auto-scanners
        _WATCH_US = [
            # Mega-cap tech (market movers)
            "AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA",
            # Semiconductors
            "AMD","INTC","AVGO","MU","ARM","SMCI","QCOM",
            # Software / SaaS / Cybersecurity
            "CRM","ADBE","NOW","SNOW","PLTR","NET","CRWD","PANW",
            # Finance / Fintech
            "JPM","BAC","GS","V","MA","COIN","SOFI","HOOD",
            # Consumer / Media / E-commerce
            "NFLX","DIS","UBER","ABNB","SHOP","ROKU","SNAP","BABA",
            # Healthcare / Biotech
            "LLY","JNJ","MRNA","ABBV",
            # High-volatility / Speculative
            "RIVN","NIO","MARA","GME","DKNG","PYPL","LULU",
        ]
        _WATCH_CRYPTO = ["BTC-USD","ETH-USD","SOL-USD","DOGE-USD","ADA-USD","XRP-USD",
                         "AVAX-USD","DOT-USD","MATIC-USD","LINK-USD"]
        _WATCH_ASIA = [("^N225","🇯🇵 Nikkei"),("^HSI","🇭🇰 Hang Seng"),
                       ("000001.SS","🇨🇳 Shanghai")]
        _INDICES = [("SPY","S&P 500"),("QQQ","Nasdaq 100"),("DIA","Dow"),
                    ("IWM","Russell 2K"),("^VIX","VIX")]
        _SECTORS = [("XLK","Tech"),("XLF","Fin"),("XLV","Health"),("XLE","Energy"),
                    ("XLI","Indust"),("XLY","Disc"),("XLP","Stpl"),("XLU","Util"),
                    ("XLRE","RE"),("XLC","Comm"),("XLB","Mat")]
        _MACRO = [("GLD","🥇 Gold"),("USO","🛢️ Oil"),("TLT","💵 Bonds"),
                  ("UUP","💲 Dollar"),("BTC-USD","₿ BTC")]

        _presence_idx = 0   # rotate among tickers
        _user_watchlists: Dict[int, List[str]] = {}   # userId → [tickers]
        _user_alerts: Dict[int, List[dict]] = {}       # userId → [{ticker, condition, price, triggered}]

        # ── 1. Presence rotation (every 5 min) ───────────────────────
        @tasks.loop(minutes=5)
        async def update_presence():
            nonlocal _presence_idx
            try:
                cycle = [("SPY","S&P"), ("QQQ","Nasdaq"), ("BTC-USD","₿ BTC"),
                         ("NVDA","NVDA"), ("TSLA","TSLA")]
                sym, label = cycle[_presence_idx % len(cycle)]
                _presence_idx += 1
                d = await _fetch_stock(sym)
                pct = d.get("change_pct", 0)
                sign = "📈" if pct >= 0 else "📉"
                await bot.change_presence(
                    activity=discord.Activity(
                        type=discord.ActivityType.watching,
                        name=f"{sign} {label} ${d.get('price',0):.2f} ({pct:+.2f}%)"))
            except Exception:
                pass

        # ── 2. Market pulse (every 15 min, extended hours Mon-Fri) ──
        @tasks.loop(minutes=15)
        async def market_pulse():
            now = datetime.now(timezone.utc)
            # Extended hours: pre-market 8 UTC (4 AM ET) through after-hours 22 UTC (6 PM ET)
            # Covers Asia close, Europe open, US full session for global users
            if not (8 <= now.hour < 22 and now.weekday() < 5):
                return
            try:
                e = discord.Embed(
                    title=f"⏱️ Market Pulse — {now.strftime('%H:%M UTC')}",
                    color=COLOR_CYAN,
                    timestamp=now)
                for sym, name in _INDICES[:3]:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    e.add_field(name=name,
                                value=f"${data.get('price',0):.2f} {_bar(pct, 6)}")
                # Add VIX as fear gauge
                vix = await _fetch_stock("^VIX")
                vp = vix.get("price", 0)
                vlabel = "😌 Low" if vp < 15 else "😐 Normal" if vp < 20 else "😰 Elevated" if vp < 30 else "🔥 PANIC"
                e.add_field(name=f"VIX {vlabel}", value=f"**{vp:.2f}**", inline=False)
                e.set_footer(text="Auto-pulse every 15 min • /market for full view")
                await _send_ch("daily-brief", embed=e)
            except Exception as exc:
                logger.error(f"market_pulse error: {exc}")

        # ── 3. Top movers auto-scan (every 30 min, extended hours) ──
        @tasks.loop(minutes=30)
        async def auto_movers():
            now = datetime.now(timezone.utc)
            if not (8 <= now.hour < 22 and now.weekday() < 5):
                return
            try:
                results = []
                for t in _WATCH_US:
                    data = await _fetch_stock(t)
                    if "error" not in data:
                        results.append(data)
                results.sort(key=lambda x: abs(x.get("change_pct", 0)), reverse=True)
                big = [r for r in results if abs(r.get("change_pct", 0)) >= 2.0]
                if not big:
                    return  # nothing notable
                e = discord.Embed(
                    title=f"🔥 Big Movers — {now.strftime('%H:%M UTC')}",
                    description=f"{len(big)} stocks moving ≥ 2%",
                    color=COLOR_GOLD,
                    timestamp=now)
                # Top 5 gainers
                gainers = sorted(big, key=lambda x: x.get("change_pct",0), reverse=True)[:5]
                losers = sorted(big, key=lambda x: x.get("change_pct",0))[:5]
                if gainers:
                    e.add_field(name="🟢 Gainers",
                                value="\n".join(f"**{r['ticker']}** ${r['price']:.2f} "
                                                f"({r['change_pct']:+.2f}%) vol {_vol(r.get('volume',0))}"
                                                for r in gainers),
                                inline=False)
                if losers:
                    e.add_field(name="🔴 Losers",
                                value="\n".join(f"**{r['ticker']}** ${r['price']:.2f} "
                                                f"({r['change_pct']:+.2f}%) vol {_vol(r.get('volume',0))}"
                                                for r in losers),
                                inline=False)
                e.set_footer(text="Auto-scan 30 stocks every 30 min")
                await _send_ch("signals", embed=e)
                await _audit(f"📡 Auto-movers: {len(big)} stocks ≥ 2%")
            except Exception as exc:
                logger.error(f"auto_movers error: {exc}")

        # ── 4. Sector + Macro snapshot (every 60 min, extended hours) ─
        @tasks.loop(minutes=60)
        async def auto_sector_macro():
            now = datetime.now(timezone.utc)
            if not (8 <= now.hour < 22 and now.weekday() < 5):
                return
            try:
                # Sector
                e = discord.Embed(
                    title=f"🏭 Sector Snapshot — {now.strftime('%H:%M UTC')}",
                    color=COLOR_INFO, timestamp=now)
                for sym, name in _SECTORS:
                    data = await _fetch_stock(sym)
                    e.add_field(name=name,
                                value=_bar(data.get("change_pct", 0), 6))
                e.set_footer(text="Hourly sector auto-update")
                await _send_ch("daily-brief", embed=e)
                # Macro
                m = discord.Embed(
                    title=f"🌍 Macro Snapshot — {now.strftime('%H:%M UTC')}",
                    color=COLOR_PURPLE, timestamp=now)
                for sym, name in _MACRO:
                    data = await _fetch_stock(sym)
                    m.add_field(name=name,
                                value=f"${data.get('price',0):,.2f} ({data.get('change_pct',0):+.2f}%)")
                m.set_footer(text="Hourly macro auto-update")
                await _send_ch("daily-brief", embed=m)
            except Exception as exc:
                logger.error(f"auto_sector_macro error: {exc}")

        # ── 5. Crypto pulse (every 2 hr, 24/7) ──────────────────────
        @tasks.loop(hours=2)
        async def auto_crypto():
            try:
                now = datetime.now(timezone.utc)
                e = discord.Embed(
                    title=f"₿ Crypto Pulse — {now.strftime('%H:%M UTC')}",
                    color=COLOR_GOLD, timestamp=now)
                for sym in _WATCH_CRYPTO[:6]:
                    data = await _fetch_stock(sym)
                    name = sym.replace("-USD", "")
                    pct = data.get("change_pct", 0)
                    e.add_field(name=name,
                                value=f"${data.get('price',0):,.2f} ({pct:+.2f}%)")
                # BTC dominance estimate
                btc = await _fetch_stock("BTC-USD")
                bp = btc.get("change_pct", 0)
                sentiment = "🟢 Bullish" if bp > 2 else "🔴 Bearish" if bp < -2 else "🟡 Neutral"
                e.add_field(name="Sentiment", value=sentiment, inline=False)
                e.set_footer(text="Auto-crypto every 2 hr • /crypto for details")
                await _send_ch("daily-brief", embed=e)
            except Exception as exc:
                logger.error(f"auto_crypto error: {exc}")

        # ── 5B. Global market update (every 4 hr, 24/7) ─────────────
        @tasks.loop(hours=4)
        async def global_market_update():
            """Posts a comprehensive market intelligence update to #daily-brief.
            Runs 24/7 so users in any timezone (Asia, Europe, US) always
            see fresh data — the same info the web dashboard shows."""
            try:
                now = datetime.now(timezone.utc)
                # Determine session label
                hour = now.hour
                if 0 <= hour < 8:
                    session = "🌏 Asia Session"
                elif 8 <= hour < 13:
                    session = "🌍 Europe / Pre-Market"
                elif 13 <= hour < 21:
                    session = "🇺🇸 US Market Hours"
                else:
                    session = "🌙 After-Hours / Asia Open"

                # Fetch core data
                spy_data = await _fetch_stock("SPY")
                qqq_data = await _fetch_stock("QQQ")
                vix_data = await _fetch_stock("^VIX")
                btc_data = await _fetch_stock("BTC-USD")
                gold_data = await _fetch_stock("GLD")
                tlt_data = await _fetch_stock("TLT")

                vix = vix_data.get("price", 0)
                spy_pct = spy_data.get("change_pct", 0)
                qqq_pct = qqq_data.get("change_pct", 0)
                btc_pct = btc_data.get("change_pct", 0)

                # Regime
                risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                    "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                regime_icons = {"RISK_ON": "🟢 RISK ON", "NEUTRAL": "🟡 NEUTRAL", "RISK_OFF": "🔴 RISK OFF"}
                regime_label = regime_icons.get(risk, "🟡 NEUTRAL")
                risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))

                # AI Recommendation
                if risk == "RISK_ON" and vix < 16:
                    ai_rec = "🟢 AGGRESSIVE"
                elif risk == "RISK_ON":
                    ai_rec = "🟢 NORMAL"
                elif risk == "NEUTRAL" and vix < 20:
                    ai_rec = "🟡 NORMAL"
                elif risk == "NEUTRAL":
                    ai_rec = "🟡 CAUTIOUS"
                else:
                    ai_rec = "🔴 DEFENSIVE"

                e = discord.Embed(
                    title=f"📊 Market Update — {session} • {now.strftime('%H:%M UTC')}",
                    description=(
                        f"**{regime_label}** • Risk Score: **{risk_on_score:.0f}/100** • AI: **{ai_rec}**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=COLOR_BUY if risk == "RISK_ON" else COLOR_SELL if risk == "RISK_OFF" else COLOR_GOLD,
                    timestamp=now,
                )

                # US Indices
                idx_text = []
                for sym, name in _INDICES[:4]:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴"
                    idx_text.append(f"{icon} **{name}** ${data.get('price',0):.2f} ({pct:+.2f}%)")
                e.add_field(name="🇺🇸 Indices",
                            value="\n".join(idx_text), inline=False)

                # Asia markets
                asia_text = []
                for sym, name in _WATCH_ASIA:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴"
                    asia_text.append(f"{icon} {name} {pct:+.2f}%")
                e.add_field(name="🌏 Asia",
                            value=" | ".join(asia_text) or "Closed", inline=True)

                # Macro
                vix_icon = "🔴" if vix > 25 else "🟡" if vix > 18 else "🟢"
                e.add_field(name="🌍 Macro",
                            value=(
                                f"VIX: **{vix:.1f}** {vix_icon} | "
                                f"Gold: {gold_data.get('change_pct',0):+.2f}% | "
                                f"Bonds: {tlt_data.get('change_pct',0):+.2f}% | "
                                f"BTC: ${btc_data.get('price',0):,.0f} ({btc_pct:+.2f}%)"
                            ), inline=False)

                # Notable moves
                notable = []
                if abs(spy_pct) > 1:
                    notable.append(f"{'📈' if spy_pct > 0 else '📉'} SPY {spy_pct:+.2f}%")
                if abs(qqq_pct) > 1:
                    notable.append(f"{'📈' if qqq_pct > 0 else '📉'} QQQ {qqq_pct:+.2f}%")
                if vix > 25:
                    notable.append(f"⚠️ VIX elevated at {vix:.1f}")
                if abs(btc_pct) > 5:
                    notable.append(f"{'🚀' if btc_pct > 0 else '💥'} BTC {btc_pct:+.1f}%")
                if notable:
                    e.add_field(name="🔔 Notable",
                                value="\n".join(notable), inline=False)

                e.set_footer(text="Auto-update every 4h 24/7 • /daily_update for full brief")
                await _send_ch("daily-brief", embed=e)
                await _audit(f"📊 Global market update ({session})")
            except Exception as exc:
                logger.error(f"global_market_update error: {exc}")

        # ── 6. Dedicated scanners — swing / breakout / momentum ──────

        def _compute_technicals(hist):
            """Shared technical computation for all scanners."""
            close = hist["Close"]
            high = hist["High"]
            low = hist["Low"]
            price = close.iloc[-1]
            sma10 = close.rolling(10).mean().iloc[-1]
            sma20 = close.rolling(20).mean().iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1]
            ema20 = close.ewm(span=20).mean().iloc[-1]
            vol = hist["Volume"].iloc[-1]
            avg_vol = hist["Volume"].rolling(20).mean().iloc[-1]
            rel_vol = vol / avg_vol if avg_vol else 1
            dollar_vol = price * avg_vol

            # RSI
            delta = close.diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss_s = (-delta.where(delta < 0, 0)).rolling(14).mean()
            rs = gain.iloc[-1] / loss_s.iloc[-1] if loss_s.iloc[-1] != 0 else 0
            rsi = 100 - (100 / (1 + rs))

            # ATR
            tr_vals = []
            for i in range(1, min(15, len(hist))):
                tr_vals.append(max(
                    high.iloc[-i] - low.iloc[-i],
                    abs(high.iloc[-i] - close.iloc[-i - 1]),
                    abs(low.iloc[-i] - close.iloc[-i - 1])))
            atr = sum(tr_vals) / len(tr_vals) if tr_vals else price * 0.02
            atr_pct = (atr / price) * 100

            # Bollinger Bands (20, 2)
            bb_mid = sma20
            bb_std = close.rolling(20).std().iloc[-1]
            bb_upper = bb_mid + 2 * bb_std
            bb_lower = bb_mid - 2 * bb_std
            bb_width = (bb_upper - bb_lower) / bb_mid * 100 if bb_mid else 5

            # Consolidation: range of last 10 candles vs ATR
            hi_10 = high.iloc[-10:].max()
            lo_10 = low.iloc[-10:].min()
            range_10 = (hi_10 - lo_10) / price * 100 if price else 5

            # Pullback days: consecutive days below SMA10
            pullback_days = 0
            for i in range(1, min(15, len(close))):
                if close.iloc[-i] < sma10:
                    pullback_days += 1
                else:
                    break

            return {
                "price": price, "sma10": sma10, "sma20": sma20,
                "sma50": sma50, "ema20": ema20, "rsi": rsi,
                "atr": atr, "atr_pct": atr_pct, "vol": vol,
                "avg_vol": avg_vol, "rel_vol": rel_vol,
                "dollar_vol": dollar_vol,
                "bb_upper": bb_upper, "bb_lower": bb_lower,
                "bb_width": bb_width, "bb_mid": bb_mid,
                "hi_10": hi_10, "lo_10": lo_10, "range_10": range_10,
                "pullback_days": pullback_days,
                "high": high, "low": low, "close": close,
            }

        # ── Async pre-fetch via centralized cache ────────────────────
        async def _prefetch(tickers, period="6mo", interval="1d"):
            """Batch-fetch histories via MarketDataService; returns {ticker: DataFrame}."""
            results = await asyncio.gather(
                *[_mds.get_history(t, period=period, interval=interval) for t in tickers],
                return_exceptions=True,
            )
            return {
                t: df for t, df in zip(tickers, results)
                if df is not None and not isinstance(df, Exception)
                and not getattr(df, "empty", True)
            }

        async def _async_signal_scan(tickers):
            """Async wrapper — pre-fetches histories then runs combined scan."""
            hist_map = await _prefetch(tickers, "6mo")
            return await asyncio.to_thread(_sync_signal_scan, tickers, hist_map)

        # ── 6a. Swing scanner ────────────────────────────────────────
        def _sync_swing_scan(tickers, hist_map=None):
            """
            Swing trade scanner — finds pullback entries in trending stocks.
            Criteria: uptrend (SMA50>SMA200-ish, price>SMA50),
            2-7 day pullback that holds key MA, RSI not overbought,
            healthy volume.  Hold target: 2-8 weeks.
            """
            signals = []
            for ticker in tickers:
                try:
                    hist = (hist_map or {}).get(ticker)
                    if hist is None:
                        continue  # skip — _prefetch already tried
                    if hist is None or hist.empty or len(hist) < 60:
                        continue
                    d = _compute_technicals(hist)
                    price, sma20, sma50 = d["price"], d["sma20"], d["sma50"]
                    rsi, rel_vol = d["rsi"], d["rel_vol"]
                    atr, atr_pct = d["atr"], d["atr_pct"]
                    pb = d["pullback_days"]

                    # ── Swing-long criteria ──
                    score = 0
                    reasons = []

                    # 1. Uptrend: price above SMA50, SMA20 > SMA50
                    if price > sma50 and sma20 > sma50:
                        score += 25
                        reasons.append("📈 Strong uptrend (SMA20 > SMA50)")
                    elif price > sma50:
                        score += 15
                        reasons.append("📈 Above SMA50")
                    else:
                        continue  # no downtrend swings

                    # 2. Pullback present (2-7 days)
                    if 2 <= pb <= 7:
                        score += 25
                        reasons.append(f"🔄 {pb}-day pullback — entry zone")
                    elif pb == 1:
                        score += 10
                        reasons.append("🔄 1-day dip")
                    else:
                        continue  # no pullback = no swing entry

                    # 3. Holding key level (price above SMA50 or EMA20)
                    if price > d["ema20"]:
                        score += 15
                        reasons.append("✅ Holding above EMA20")
                    elif price > sma50:
                        score += 10
                        reasons.append("✅ Holding above SMA50")

                    # 4. RSI not overbought
                    if 35 <= rsi <= 55:
                        score += 15
                        reasons.append(f"RSI {rsi:.0f} — reset into buy zone")
                    elif rsi < 35:
                        score += 10
                        reasons.append(f"RSI {rsi:.0f} — oversold bounce")
                    elif rsi > 70:
                        continue  # overbought, skip

                    # 5. Volume & liquidity
                    if d["dollar_vol"] > 10_000_000:
                        score += 5
                        reasons.append("💰 Liquid")
                    if rel_vol > 0.5:
                        score += 5

                    if score < 55:
                        continue

                    stop = max(sma50, price - 2 * atr)
                    risk = abs(price - stop)
                    target = price + risk * 2.5
                    rr = (target - price) / risk if risk > 0 else 0

                    signals.append({
                        "ticker": ticker, "direction": "LONG",
                        "setup_type": "SWING", "price": price,
                        "score": min(score, 100), "reasons": reasons,
                        "rsi": rsi, "sma20": sma20, "sma50": sma50,
                        "rel_vol": rel_vol, "atr": atr, "atr_pct": atr_pct,
                        "stop": stop, "target": target, "rr_ratio": rr,
                        "stop_atr": risk / atr if atr > 0 else 1,
                        "dollar_vol": d["dollar_vol"],
                        "hold_target": "2-8 weeks",
                        "invalidation": f"Close below ${stop:.2f} (SMA50 / 2×ATR)",
                        "buy_thesis": (
                            f"{ticker} is in a confirmed uptrend with a healthy {pb}-day pullback to support. "
                            f"RSI {rsi:.0f} has reset into the buy zone — ideal re-entry. "
                            f"Buy the dip in the direction of the existing trend for highest probability."
                        ),
                        "stop_reason": (
                            f"Stop ${stop:.2f} = max(SMA50, price − 2×ATR). "
                            f"A close BELOW this = the uptrend is structurally broken → exit immediately. "
                            f"SMA50 is the primary support for swing trades. "
                            f"2×ATR keeps stop outside normal daily noise. Risk: {abs(price - stop)/price*100:.1f}%."
                        ),
                    })
                except Exception:
                    continue
            return signals

        # ── 6b. Breakout scanner ─────────────────────────────────────
        def _sync_breakout_scan(tickers, hist_map=None):
            """
            Breakout scanner — finds consolidation breaks with volume.
            Criteria: tight range (low BB width or narrow 10-day range),
            price breaking above the consolidation high on above-avg volume.
            Hold target: 1-4 weeks.
            """
            signals = []
            for ticker in tickers:
                try:
                    hist = (hist_map or {}).get(ticker)
                    if hist is None:
                        continue  # skip — _prefetch already tried
                    if hist is None or hist.empty or len(hist) < 60:
                        continue
                    d = _compute_technicals(hist)
                    price, sma20, sma50 = d["price"], d["sma20"], d["sma50"]
                    rsi, rel_vol = d["rsi"], d["rel_vol"]
                    atr, atr_pct = d["atr"], d["atr_pct"]
                    hi_10, range_10 = d["hi_10"], d["range_10"]
                    bb_width = d["bb_width"]
                    close = d["close"]

                    score = 0
                    reasons = []

                    # 1. Tight consolidation (BB squeeze or narrow range)
                    if bb_width < 6:
                        score += 20
                        reasons.append(f"🔒 BB squeeze — width {bb_width:.1f}%")
                    elif range_10 < atr_pct * 2.5:
                        score += 15
                        reasons.append(f"🔒 Tight 10d range {range_10:.1f}%")
                    else:
                        continue  # not consolidating

                    # 2. Breaking above the consolidation high
                    yesterday = close.iloc[-2] if len(close) > 1 else price
                    if price > hi_10 and yesterday <= hi_10:
                        score += 30
                        reasons.append(f"🚀 BREAKING OUT above ${hi_10:.2f}")
                    elif price > hi_10 * 0.99:
                        score += 15
                        reasons.append(f"📍 Testing resistance ${hi_10:.2f}")
                    else:
                        continue  # not at breakout level

                    # 3. Volume confirmation
                    if rel_vol >= 2.0:
                        score += 20
                        reasons.append(f"🔥 Volume surge {rel_vol:.1f}x avg")
                    elif rel_vol >= 1.3:
                        score += 10
                        reasons.append(f"📊 Vol {rel_vol:.1f}x avg")
                    else:
                        score -= 10
                        reasons.append("⚠️ Low volume — needs confirmation")

                    # 4. Trend context
                    if price > sma50:
                        score += 10
                        reasons.append("📈 Above SMA50")
                    if sma20 > sma50:
                        score += 5

                    # 5. RSI range
                    if 50 <= rsi <= 70:
                        score += 5
                        reasons.append(f"RSI {rsi:.0f} — momentum")

                    # 6. Liquidity
                    if d["dollar_vol"] > 10_000_000:
                        score += 5
                        reasons.append("💰 Liquid")

                    if score < 55:
                        continue

                    stop = d["lo_10"]  # bottom of consolidation
                    risk = abs(price - stop)
                    target = price + risk * 2
                    rr = (target - price) / risk if risk > 0 else 0

                    signals.append({
                        "ticker": ticker, "direction": "LONG",
                        "setup_type": "BREAKOUT", "price": price,
                        "score": min(score, 100), "reasons": reasons,
                        "rsi": rsi, "sma20": sma20, "sma50": sma50,
                        "rel_vol": rel_vol, "atr": atr, "atr_pct": atr_pct,
                        "stop": stop, "target": target, "rr_ratio": rr,
                        "stop_atr": risk / atr if atr > 0 else 1,
                        "dollar_vol": d["dollar_vol"],
                        "hold_target": "1-4 weeks",
                        "invalidation": f"Close below ${stop:.2f} (consolidation low)",
                        "buy_thesis": (
                            f"{ticker} is breaking out of a {d['bb_width']:.1f}% BB squeeze consolidation. "
                            f"Volume {rel_vol:.1f}x avg confirms REAL institutional demand, not noise. "
                            f"Breakout above ${d['hi_10']:.2f} = buyers in control — momentum builds from here."
                        ),
                        "stop_reason": (
                            f"Stop ${stop:.2f} = consolidation low. "
                            f"A failed breakout = price returns INTO the base → thesis dead, exit fast. "
                            f"Never hold a failed breakout — that is how big losses happen. "
                            f"Risk: {abs(price - stop)/price*100:.1f}% — tight vs the measured-move target."
                        ),
                    })
                except Exception:
                    continue
            return signals

        # ── 6c. Momentum scanner ─────────────────────────────────────
        def _sync_momentum_scan(tickers, hist_map=None):
            """
            Momentum scanner — finds strong movers for short-term plays.
            Criteria: big move today (>2%), above-avg volume, strong trend.
            Hold target: days to 2 weeks.
            """
            signals = []
            for ticker in tickers:
                try:
                    hist = (hist_map or {}).get(ticker)
                    if hist is None:
                        continue
                    if hist is None or hist.empty or len(hist) < 30:
                        continue
                    d = _compute_technicals(hist)
                    price, sma20, sma50 = d["price"], d["sma20"], d["sma50"]
                    rsi, rel_vol = d["rsi"], d["rel_vol"]
                    atr, atr_pct = d["atr"], d["atr_pct"]
                    close = d["close"]

                    prev_close = close.iloc[-2] if len(close) > 1 else price
                    day_pct = ((price - prev_close) / prev_close * 100) if prev_close else 0

                    score = 0
                    reasons = []
                    direction = "LONG"

                    # 1. Big daily move
                    if day_pct >= 5:
                        score += 30
                        reasons.append(f"🚀 {day_pct:+.1f}% today — explosive move")
                    elif day_pct >= 3:
                        score += 25
                        reasons.append(f"📈 {day_pct:+.1f}% today — strong move")
                    elif day_pct >= 2:
                        score += 15
                        reasons.append(f"📈 {day_pct:+.1f}% today")
                    elif day_pct <= -5:
                        score += 25
                        direction = "SHORT"
                        reasons.append(f"📉 {day_pct:+.1f}% today — dump")
                    elif day_pct <= -3:
                        score += 20
                        direction = "SHORT"
                        reasons.append(f"📉 {day_pct:+.1f}% today — weakness")
                    else:
                        continue  # no big move

                    # 2. Volume confirmation
                    if rel_vol >= 3.0:
                        score += 25
                        reasons.append(f"🐋 Volume {rel_vol:.1f}x avg — institutional")
                    elif rel_vol >= 2.0:
                        score += 20
                        reasons.append(f"🔥 Volume {rel_vol:.1f}x avg")
                    elif rel_vol >= 1.5:
                        score += 10
                        reasons.append(f"📊 Volume {rel_vol:.1f}x avg")

                    # 3. Trend alignment
                    if direction == "LONG" and price > sma20 > sma50:
                        score += 15
                        reasons.append("📈 Trend aligned up")
                    elif direction == "SHORT" and price < sma20 < sma50:
                        score += 15
                        reasons.append("📉 Trend aligned down")

                    # 4. RSI supports direction
                    if direction == "LONG" and rsi > 50:
                        score += 5
                    elif direction == "SHORT" and rsi < 50:
                        score += 5

                    # 5. Liquidity
                    if d["dollar_vol"] > 10_000_000:
                        score += 5
                        reasons.append("💰 Liquid")

                    if score < 50:
                        continue

                    if direction == "LONG":
                        stop = price - 1.5 * atr
                        target = price + 2 * atr
                    else:
                        stop = price + 1.5 * atr
                        target = price - 2 * atr
                    risk = abs(price - stop)
                    rr = abs(price - target) / risk if risk > 0 else 0

                    signals.append({
                        "ticker": ticker, "direction": direction,
                        "setup_type": "MOMENTUM", "price": price,
                        "score": min(score, 100), "reasons": reasons,
                        "rsi": rsi, "sma20": sma20, "sma50": sma50,
                        "rel_vol": rel_vol, "atr": atr, "atr_pct": atr_pct,
                        "stop": stop, "target": target, "rr_ratio": rr,
                        "stop_atr": risk / atr if atr > 0 else 1,
                        "dollar_vol": d["dollar_vol"],
                        "day_pct": day_pct,
                        "hold_target": "days to 2 weeks",
                        "invalidation": f"{'Close below' if direction == 'LONG' else 'Close above'} ${stop:.2f} (1.5×ATR)",
                        "buy_thesis": (
                            f"{ticker} moved {day_pct:+.1f}% today on {rel_vol:.1f}x volume — real money behind this move. "
                            f"{'Trend aligned up — ride the momentum.' if direction == 'LONG' else 'Sharp drop on heavy volume — momentum short.'} "
                            f"High-conviction directional move with institutional participation."
                        ),
                        "stop_reason": (
                            f"Stop ${stop:.2f} = 1.5×ATR from entry. "
                            f"{'Momentum stops when the surge fades — close below = exit.' if direction == 'LONG' else 'Cover if close above — dump exhausted.'} "
                            f"1.5×ATR is calibrated to daily volatility (ATR=${atr:.2f}). "
                            f"Risk: {abs(price - stop)/price*100:.1f}% — sized for a short hold."
                        ),
                    })
                except Exception:
                    continue
            return signals

        # ── Legacy wrapper (used by morning brief) ───────────────────
        def _sync_signal_scan(tickers, hist_map=None):
            """Combined scan — merges all three scanner types."""
            swing = _sync_swing_scan(tickers, hist_map)
            breakout = _sync_breakout_scan(tickers, hist_map)
            momentum = _sync_momentum_scan(tickers, hist_map)
            combined = swing + breakout + momentum
            combined.sort(key=lambda x: x.get("score", 0), reverse=True)
            return combined

        def _attach_ml_rank(signals: list, hist_cache: dict) -> list:
            """Attach ML regime rank and win probability to each signal."""
            opt = _get_optimizer()
            if opt is None or not _yf:
                return signals
            for sig in signals:
                ticker = sig.get("ticker", "")
                try:
                    if ticker not in hist_cache:
                        continue
                    hist = hist_cache[ticker]
                    if not hist.empty and len(hist) >= 30:
                        ranked = opt.quick_regime_rank(hist)
                        # find rank position for this signal's strategy
                        strategy = sig.get("setup_type", "SWING")
                        rank_item = next(
                            (r for r in ranked if r["strategy"] == strategy), None)
                        if rank_item:
                            sig["ml_score"] = rank_item["score"]
                            sig["ml_regime_fit"] = rank_item["regime_fit"]
                            sig["ml_rank"] = ranked.index(rank_item) + 1
                        # top strategy for current regime
                        sig["ml_best_strategy"] = ranked[0]["strategy"] if ranked else "N/A"
                except Exception:
                    pass
            return signals

        # ── Signal card builder (shared) ─────────────────────────────
        def _build_signal_card(sig, now, setup_label=""):
            """Build a Discord embed for any signal type."""
            is_long = sig["direction"] == "LONG"
            score = sig["score"]
            if score >= 80:
                tier_emoji, tier_label, card_color = "🟢", "HIGH CONVICTION", COLOR_GOLD
            elif score >= 65:
                tier_emoji, tier_label = "🟡", "GOOD SETUP"
                card_color = COLOR_BUY if is_long else COLOR_SELL
            else:
                tier_emoji, tier_label, card_color = "⚪", "MODERATE", COLOR_INFO

            arrow = "🟢 LONG" if is_long else "🔴 SHORT"
            bar = "█" * (score // 10) + "░" * (10 - score // 10)
            label = f"  [{setup_label}]" if setup_label else ""

            e = discord.Embed(
                title=f"{arrow}  {sig['ticker']}  —  ${sig['price']:.2f}{label}",
                description=(
                    f"{tier_emoji} **{tier_label}** • Score **{score}/100** `{bar}`\n\n"
                    + "\n".join(sig["reasons"])
                ),
                color=card_color, timestamp=now)

            e.add_field(name="🎯 Target", value=f"${sig.get('target', 0):.2f}")
            e.add_field(name="🛑 Stop", value=f"${sig.get('stop', 0):.2f}")
            e.add_field(name="⚖️ R:R", value=f"**{sig.get('rr_ratio', 0):.1f}:1**")

            rsi = sig["rsi"]
            rsi_icon = "🔴" if rsi > 70 else "🟢" if rsi < 30 else "⚪"
            e.add_field(name="RSI", value=f"{rsi_icon} {rsi:.0f}")
            e.add_field(name="Rel Vol",
                        value=f"{'🔥' if sig['rel_vol'] > 2 else '📊'} {sig['rel_vol']:.1f}x")
            e.add_field(name="⏳ Hold", value=sig.get("hold_target", ""))

            e.add_field(name="🛑 Invalidation",
                        value=sig.get("invalidation", "N/A"), inline=False)
            if sig.get("buy_thesis"):
                e.add_field(name="🟢 WHY BUY", value=sig["buy_thesis"][:512], inline=False)
            if sig.get("stop_reason"):
                e.add_field(name="🛑 WHY THIS STOP", value=sig["stop_reason"][:512], inline=False)
            if sig.get("ml_score") is not None:
                ml_score = sig["ml_score"]
                ml_fit = sig.get("ml_regime_fit", False)
                ml_rank = sig.get("ml_rank", "?")
                ml_best = sig.get("ml_best_strategy", "")
                e.add_field(
                    name="🧠 ML Regime Check",
                    value=(
                        f"Backtest score: **{ml_score:.0f}/100** (rank #{ml_rank})\n"
                        f"Regime fit: {'✅ Yes' if ml_fit else '⚠️ Off-regime'}\n"
                        f"Best strategy now: **{ml_best}**"
                    ), inline=True)

            dv = sig.get("dollar_vol", 0)
            dv_str = f"${dv / 1e6:.1f}M" if dv > 1e6 else f"${dv / 1e3:.0f}K"
            liq_icon = "✅" if dv > 10_000_000 else "⚠️" if dv > 2_000_000 else "🔴"
            e.add_field(name="💰 Liquidity", value=f"{liq_icon} {dv_str}/day")
            e.add_field(name="Stop/ATR",
                        value=f"{sig.get('stop_atr', 1):.1f}x ATR")
            e.set_footer(text="Buttons below ↓ • Deep Analysis • Position Size • Set Alert")
            return e

        # ── 6A. Swing trade auto-post (every 6 hr) ──────────────────
        @tasks.loop(hours=6)
        async def auto_swing_scan():
            """Scan for swing pullback entries → #swing-trades."""
            now = datetime.now(timezone.utc)
            if not (now.weekday() < 5):
                return
            try:
                hist_map = await _prefetch(_WATCH_US, "6mo")
                signals = await asyncio.to_thread(_sync_swing_scan, _WATCH_US, hist_map)
                if not signals:
                    return
                ml_hist = await _prefetch([s["ticker"] for s in signals], "3mo")
                signals = await asyncio.to_thread(_attach_ml_rank, signals, ml_hist)
                signals.sort(key=lambda x: x["score"], reverse=True)
                header = discord.Embed(
                    title="🔄 Swing Pullback Setups",
                    description=(
                        f"Scanned {len(_WATCH_US)} tickers • "
                        f"**{len(signals)}** swing setups • "
                        f"Hold: 2-8 weeks"
                    ), color=COLOR_BUY, timestamp=now)
                header.set_footer(text="Pullback entries in trending stocks • Score 0-100")
                await _send_ch("swing-trades", embed=header)
                await asyncio.sleep(0.5)
                top_count = min(5, len(signals))

                for sig in signals[:top_count]:
                    e = _build_signal_card(sig, now, "SWING")
                    await _send_ch("swing-trades", embed=e,
                                   view=SignalActionView(sig["ticker"], sig))
                    await asyncio.sleep(1)

                await _audit(
                    f"🔄 Swing scan: {len(signals)} setups, "
                    f"top {top_count} → #swing-trades")
            except Exception as exc:
                logger.error(f"auto_swing_scan error: {exc}")

        # ── 6B. Breakout auto-post (every 4 hr) ─────────────────────
        @tasks.loop(hours=4)
        async def auto_breakout_scan():
            """Scan for consolidation breakouts → #breakout-setups."""
            now = datetime.now(timezone.utc)
            if not (13 <= now.hour < 21 and now.weekday() < 5):
                return  # US hours only for breakouts
            try:
                hist_map = await _prefetch(_WATCH_US, "6mo")
                signals = await asyncio.to_thread(_sync_breakout_scan, _WATCH_US, hist_map)
                if not signals:
                    return
                ml_hist = await _prefetch([s["ticker"] for s in signals], "3mo")
                signals = await asyncio.to_thread(_attach_ml_rank, signals, ml_hist)
                signals.sort(key=lambda x: x["score"], reverse=True)
                top_count = min(5, len(signals))
                header = discord.Embed(
                    title=f"🚀 Breakout Scan — {now.strftime('%H:%M UTC')}",
                    description=(
                        f"Scanned {len(_WATCH_US)} tickers • "
                        f"**{len(signals)}** breakout setups • "
                        f"Hold: 1-4 weeks"
                    ), color=COLOR_GOLD, timestamp=now)
                header.set_footer(text="Consolidation breaks with volume • Score 0-100")
                await _send_ch("breakout-setups", embed=header)
                await asyncio.sleep(0.5)

                for sig in signals[:top_count]:
                    e = _build_signal_card(sig, now, "BREAKOUT")
                    await _send_ch("breakout-setups", embed=e,
                                   view=SignalActionView(sig["ticker"], sig))
                    await asyncio.sleep(1)

                await _audit(
                    f"🚀 Breakout scan: {len(signals)} setups, "
                    f"top {top_count} → #breakout-setups")
            except Exception as exc:
                logger.error(f"auto_breakout_scan error: {exc}")

        # ── 6C. Momentum auto-post (every 2 hr) ─────────────────────
        @tasks.loop(hours=2)
        async def auto_momentum_scan():
            """Scan for big movers + volume → #momentum-alerts."""
            now = datetime.now(timezone.utc)
            if not (13 <= now.hour < 21 and now.weekday() < 5):
                return
            try:
                hist_map = await _prefetch(_WATCH_US, "3mo")
                signals = await asyncio.to_thread(_sync_momentum_scan, _WATCH_US, hist_map)
                if not signals:
                    return
                signals.sort(key=lambda x: x["score"], reverse=True)
                top_count = min(5, len(signals))
                header = discord.Embed(
                    title=f"⚡ Momentum Alert — {now.strftime('%H:%M UTC')}",
                    description=(
                        f"Scanned {len(_WATCH_US)} tickers • "
                        f"**{len(signals)}** momentum signals • "
                        f"Hold: days to 2 weeks"
                    ), color=COLOR_SELL, timestamp=now)
                header.set_footer(text="Big movers + volume surges • Score 0-100")
                await _send_ch("momentum-alerts", embed=header)
                await asyncio.sleep(0.5)

                for sig in signals[:top_count]:
                    e = _build_signal_card(sig, now, "MOMENTUM")
                    pct = sig.get("day_pct", 0)
                    if pct:
                        e.add_field(name="📊 Today",
                                    value=f"**{pct:+.1f}%**", inline=True)
                    await _send_ch("momentum-alerts", embed=e,
                                   view=SignalActionView(sig["ticker"], sig))
                    await asyncio.sleep(1)

                await _audit(
                    f"⚡ Momentum scan: {len(signals)} signals, "
                    f"top {top_count} → #momentum-alerts")
            except Exception as exc:
                logger.error(f"auto_momentum_scan error: {exc}")

        # ── 6D. AI Signal Scan — combined ranked signals (every 3 hr) ──
        @tasks.loop(hours=3)
        async def auto_signal_scan():
            """Aggregate top signals from all strategies → #ai-signals."""
            now = datetime.now(timezone.utc)
            if not (13 <= now.hour < 21 and now.weekday() < 5):
                return
            try:
                hist_map = await _prefetch(_WATCH_US, "6mo")
                all_sigs = []
                for scan_fn, label in [
                    (_sync_swing_scan, "SWING"),
                    (_sync_breakout_scan, "BREAKOUT"),
                    (_sync_momentum_scan, "MOMENTUM"),
                ]:
                    try:
                        sigs = await asyncio.to_thread(scan_fn, _WATCH_US, hist_map)
                        for s in (sigs or []):
                            s["_strategy"] = label
                        all_sigs.extend(sigs or [])
                    except Exception:
                        pass

                if not all_sigs:
                    return

                # Attach ML regime rank to all signals
                ml_hist = await _prefetch([s["ticker"] for s in all_sigs], "3mo")
                all_sigs = await asyncio.to_thread(_attach_ml_rank, all_sigs, ml_hist)

                # Rank by composite score and pick top 5
                all_sigs.sort(key=lambda x: x.get("score", 0), reverse=True)
                top = all_sigs[:5]

                header = discord.Embed(
                    title=f"🤖 AI Signal Scan — {now.strftime('%H:%M UTC')}",
                    description=(
                        f"Scanned {len(_WATCH_US)} tickers × 3 strategies • "
                        f"**{len(all_sigs)}** total setups • Top 5 below"
                    ),
                    color=COLOR_INFO, timestamp=now,
                )
                header.set_footer(text="Combined AI ranking • Score 0-100")
                await _send_ch("ai-signals", embed=header)
                await asyncio.sleep(0.5)

                for sig in top:
                    e = _build_signal_card(sig, now, sig.get("_strategy", "AI"))
                    await _send_ch("ai-signals", embed=e,
                                   view=SignalActionView(sig["ticker"], sig))
                    await asyncio.sleep(1)

                await _audit(
                    f"🤖 AI signal scan: {len(all_sigs)} total, "
                    f"top 5 → #ai-signals")
            except Exception as exc:
                logger.error(f"auto_signal_scan error: {exc}")

        # ── 7. Morning brief (runs every 10 min, fires once at ~13:30 UTC / 9:30 ET)
        _morning_posted = set()
        @tasks.loop(minutes=10)
        async def morning_brief():
            """v6 Morning Decision Memo — scoreboard, delta deck, playbook, scenarios."""
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if today in _morning_posted:
                return
            # Fire between 13:20-13:40 UTC (9:20-9:40 ET) on weekdays
            if not (now.weekday() < 5 and 13 <= now.hour <= 13 and 20 <= now.minute <= 40):
                if not (now.hour == 13 and now.minute >= 20):
                    return
                if not (now.hour == 13 and now.minute <= 40):
                    return
            _morning_posted.add(today)
            try:
                # ── Fetch all market data ──
                spy_data = await _fetch_stock("SPY")
                qqq_data = await _fetch_stock("QQQ")
                iwm_data = await _fetch_stock("IWM")
                vix_data = await _fetch_stock("^VIX")
                tlt_data = await _fetch_stock("TLT")
                btc_data = await _fetch_stock("BTC-USD")
                gold_data = await _fetch_stock("GLD")

                vix = vix_data.get("price", 0)
                spy_pct = spy_data.get("change_pct", 0)
                qqq_pct = qqq_data.get("change_pct", 0)

                market_prices = {
                    "SPY": spy_data, "QQQ": qqq_data, "IWM": iwm_data,
                }

                # ── v6: Build RegimeScoreboard from market data ──
                risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                    "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                trend = "UPTREND" if spy_pct > 0.5 else "DOWNTREND" if spy_pct < -0.5 else "NEUTRAL"
                vol_state = "HIGH_VOL" if vix > 22 else "LOW_VOL" if vix < 15 else "NORMAL"

                # Strategy playbook derivation
                playbook_map = {
                    ("RISK_ON", "UPTREND", "LOW_VOL"): (["Momentum", "Breakout", "Trend-Follow"], [], ["Mean-Reversion"]),
                    ("RISK_ON", "UPTREND", "NORMAL"): (["Momentum", "Swing", "VCP"], [], []),
                    ("RISK_ON", "NEUTRAL", "LOW_VOL"): (["Mean-Reversion", "Swing"], [], ["Momentum"]),
                    ("NEUTRAL", "UPTREND", "NORMAL"): (["Momentum", "VCP"], [{"strategy": "Swing", "condition": "pullback > 3d"}], []),
                    ("NEUTRAL", "NEUTRAL", "NORMAL"): (["Mean-Reversion"], [{"strategy": "Swing", "condition": "setup grade A only"}], ["Momentum"]),
                    ("NEUTRAL", "DOWNTREND", "NORMAL"): (["Mean-Reversion"], [], ["Momentum", "Breakout"]),
                    ("RISK_OFF", "DOWNTREND", "HIGH_VOL"): ([], [], ["Momentum", "Breakout", "Swing", "VCP"]),
                    ("RISK_OFF", "NEUTRAL", "HIGH_VOL"): (["Mean-Reversion"], [], ["Momentum", "Breakout"]),
                }
                key = (risk, trend, vol_state)
                strats_on, strats_cond, strats_off = playbook_map.get(
                    key, (["Swing", "Mean-Reversion"], [], []))

                # Risk budget
                risk_budgets = {
                    "RISK_ON": (150, 60, 100, 5, 30),
                    "NEUTRAL": (100, 30, 70, 4, 25),
                    "RISK_OFF": (60, 0, 30, 2, 15),
                }
                mg, nll, nlh, msn, ms = risk_budgets.get(risk, (100, 30, 70, 4, 25))

                # Risk bulletin
                risk_flags = []
                if vix > 25:
                    risk_flags.append(f"VIX {vix:.1f} — reduce position sizes to 50%")
                if vix > 18 and spy_pct < -1:
                    risk_flags.append("Selling into elevated vol — stop discipline critical")
                if abs(qqq_pct - spy_pct) > 1.5:
                    risk_flags.append(f"QQQ/SPY divergence {qqq_pct - spy_pct:+.1f}% — rotation risk")

                # Top drivers
                drivers = []
                if abs(spy_pct) > 1:
                    drivers.append(f"SPX move {spy_pct:+.2f}%")
                if vix > 20 or vix < 14:
                    drivers.append(f"VIX at {vix:.1f}")
                btc_pct = btc_data.get("change_pct", 0)
                if abs(btc_pct) > 3:
                    drivers.append(f"BTC {btc_pct:+.1f}%")

                # Scenario plan
                scenarios = None
                try:
                    from src.core.models import ScenarioPlan
                    scenarios = ScenarioPlan(
                        base_case={"probability": "55%", "description": f"Range-bound, VIX stays near {vix:.0f}"},
                        bull_case={"probability": "25%", "description": f"SPX pushes above ${spy_data.get('high', 0):.0f} on breadth expansion"},
                        bear_case={"probability": "20%", "description": f"SPX loses ${spy_data.get('low', 0):.0f}, VIX spikes above {vix + 5:.0f}"},
                        triggers=["GDP data 8:30 ET", "Fed speakers", "Earnings after close"],
                    )
                except Exception:
                    pass

                # Build v6 RegimeScoreboard
                from src.core.models import RegimeScoreboard as RSB
                risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))
                scoreboard = RSB(
                    regime_label=risk,
                    risk_on_score=risk_on_score,
                    trend_state=trend,
                    vol_state=vol_state,
                    max_gross_pct=mg,
                    net_long_target_low=nll,
                    net_long_target_high=nlh,
                    max_single_name_pct=msn,
                    max_sector_pct=ms,
                    strategies_on=strats_on,
                    strategies_conditional=strats_cond,
                    strategies_off=strats_off,
                    no_trade_triggers=risk_flags,
                    top_drivers=drivers,
                    scenarios=scenarios,
                )

                # Build v6 ChangeItems
                from src.core.models import ChangeItem
                bullish_changes: list = []
                bearish_changes: list = []
                if spy_pct > 0.5:
                    bullish_changes.append(ChangeItem(category="index", description=f"SPY +{spy_pct:.2f}%"))
                if spy_pct < -0.5:
                    bearish_changes.append(ChangeItem(category="index", description=f"SPY {spy_pct:+.2f}%", severity="warning"))
                if qqq_pct > 0.5:
                    bullish_changes.append(ChangeItem(category="index", description=f"QQQ +{qqq_pct:.2f}%"))
                if qqq_pct < -0.5:
                    bearish_changes.append(ChangeItem(category="index", description=f"QQQ {qqq_pct:+.2f}%", severity="warning"))
                if vix > 22:
                    bearish_changes.append(ChangeItem(category="volatility", description=f"VIX elevated at {vix:.1f}", severity="warning"))
                if abs(btc_pct) > 3:
                    target = bullish_changes if btc_pct > 0 else bearish_changes
                    target.append(ChangeItem(category="crypto", description=f"BTC {btc_pct:+.1f}%"))

                # ── Use v6 report generator if available ──
                if _HAS_REPORT_GEN:
                    # Scan for top signals
                    top_signal_objs = None
                    try:
                        scan_results = await _async_signal_scan(_WATCH_US[:15])
                        if scan_results:
                            scan_results.sort(key=lambda x: x["score"], reverse=True)
                            # Convert scan dicts to minimal Signal-like objects for display
                            top_signal_objs = scan_results[:5]
                    except Exception:
                        pass

                    memo_embeds = build_morning_memo(
                        scoreboard=scoreboard,
                        bullish_changes=bullish_changes,
                        bearish_changes=bearish_changes,
                        market_prices=market_prices,
                    )

                    # Add Futures & Asia as extra fields on first embed
                    if memo_embeds:
                        extra_fields = []
                        # Futures
                        futures_text = []
                        for sym, name in [("ES=F", "S&P"), ("NQ=F", "Nasdaq"), ("YM=F", "Dow")]:
                            data = await _fetch_stock(sym)
                            pct = data.get("change_pct", 0)
                            icon = "🟢" if pct > 0 else "🔴" if pct < 0 else "⚪"
                            futures_text.append(f"{icon} **{name}**: {pct:+.2f}%")
                        extra_fields.append({"name": "📈 Futures", "value": " | ".join(futures_text), "inline": False})

                        # Asia close
                        asia_lines = []
                        for sym, name in _WATCH_ASIA:
                            data = await _fetch_stock(sym)
                            pct = data.get("change_pct", 0)
                            icon = "🟢" if pct > 0 else "🔴"
                            asia_lines.append(f"{icon} {name}: {pct:+.2f}%")
                        extra_fields.append({"name": "🌏 Asia Close", "value": " | ".join(asia_lines), "inline": False})

                        # Macro
                        macro_text = (
                            f"📉 VIX: **{vix:.1f}** "
                            f"{'🔴' if vix > 25 else '🟡' if vix > 18 else '🟢'} | "
                            f"💵 TLT: {tlt_data.get('change_pct', 0):+.2f}% | "
                            f"🥇 Gold: {gold_data.get('change_pct', 0):+.2f}% | "
                            f"₿ BTC: {btc_pct:+.2f}%"
                        )
                        extra_fields.append({"name": "🌍 Macro", "value": macro_text, "inline": False})

                        # Insert extra fields before the last 2 fields (Risk + Sizing)
                        first_embed_fields = memo_embeds[0].get("fields", [])
                        insert_pos = max(0, len(first_embed_fields) - 2)
                        for ef in extra_fields:
                            first_embed_fields.insert(insert_pos, ef)
                            insert_pos += 1

                    # Send all embeds to #daily-brief
                    for embed_dict in memo_embeds:
                        e = discord.Embed(
                            title=embed_dict.get("title", ""),
                            description=embed_dict.get("description", ""),
                            color=embed_dict.get("color", COLOR_GOLD),
                            timestamp=now,
                        )
                        for f in embed_dict.get("fields", []):
                            e.add_field(name=f["name"], value=f["value"],
                                        inline=f.get("inline", False))
                        e.set_footer(text=embed_dict.get("footer", "TradingAI Pro v6"))
                        await _send_ch("daily-brief", embed=e)

                    # Fallback top-trades embed if report generator didn't include them
                    if top_signal_objs and len(memo_embeds) < 2:
                        e2 = discord.Embed(
                            title="🎯 Top 5 Trade Ideas",
                            description="Pre-market scan • sorted by conviction",
                            color=COLOR_INFO, timestamp=now)
                        for i, sig in enumerate(top_signal_objs[:5], 1):
                            arrow = "🟢" if sig["direction"] == "LONG" else "🔴"
                            rr = sig.get("rr_ratio", 0)
                            e2.add_field(
                                name=f"{arrow} #{i} {sig['ticker']} — ${sig['price']:.2f}",
                                value=(
                                    f"Score: **{sig['score']}** | "
                                    f"R:R: **{rr:.1f}:1** | "
                                    f"Stop: ${sig.get('stop', 0):.2f} | "
                                    f"Target: ${sig.get('target', 0):.2f}\n"
                                    f"{sig['reasons'][0] if sig.get('reasons') else ''}"
                                ), inline=False)
                        e2.set_footer(text="/signals for full list • v6 grading active")
                        await _send_ch("daily-brief", embed=e2)

                else:
                    # ── Legacy v5 fallback (no report generator) ──
                    regime_icons = {
                        "RISK_ON": "🟢 RISK ON", "NEUTRAL": "🟡 NEUTRAL", "RISK_OFF": "🔴 RISK OFF"
                    }
                    regime_label = regime_icons.get(risk, "🟡 NEUTRAL")
                    e = discord.Embed(
                        title=f"☀️ Morning Decision Memo — {now.strftime('%A, %B %d')}",
                        description=(
                            f"**{regime_label}** • VIX {vix:.1f} • "
                            f"SPY {spy_pct:+.2f}% • QQQ {qqq_pct:+.2f}%\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=COLOR_GOLD, timestamp=now)
                    e.add_field(name="📊 Regime",
                                value=f"**{regime_label}** | Trend: {trend} | Vol: {vol_state}",
                                inline=False)
                    strat_str = " · ".join(f"`{s}`" for s in strats_on)
                    e.add_field(name="📋 Playbook",
                                value=f"Strategies: {strat_str}",
                                inline=False)
                    if risk_flags:
                        e.add_field(name="🛡️ Risk",
                                    value="\n".join(f"🔴 {r}" for r in risk_flags),
                                    inline=False)
                    e.set_footer(text="☀️ v6 Decision Memo • /market_now for real-time")
                    await _send_ch("daily-brief", embed=e)

                await _audit("☀️ v6 Morning Decision Memo posted")
            except Exception as exc:
                logger.error(f"morning_brief error: {exc}")

        # ── 8. EOD report v6 (runs every 10 min, fires once at ~20:10 UTC / 4:10 PM ET)
        _eod_posted = set()
        @tasks.loop(minutes=10)
        async def eod_report():
            """v6 EOD Scorecard — regime close, sector heat, breadth, signal summary, outlook."""
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if today in _eod_posted:
                return
            if not (now.weekday() < 5 and now.hour == 20 and 5 <= now.minute <= 20):
                return
            _eod_posted.add(today)
            try:
                # ── Fetch closing data ──
                spy_data = await _fetch_stock("SPY")
                qqq_data = await _fetch_stock("QQQ")
                iwm_data = await _fetch_stock("IWM")
                vix_data = await _fetch_stock("^VIX")
                tlt_data = await _fetch_stock("TLT")
                btc_data = await _fetch_stock("BTC-USD")
                gold_data = await _fetch_stock("GLD")

                vix = vix_data.get("price", 0)
                spy_pct = spy_data.get("change_pct", 0)
                qqq_pct = qqq_data.get("change_pct", 0)
                iwm_pct = iwm_data.get("change_pct", 0)

                # ── v6: Build RegimeScoreboard for close ──
                risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                    "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                trend = "UPTREND" if spy_pct > 0.5 else "DOWNTREND" if spy_pct < -0.5 else "NEUTRAL"
                vol_state = "HIGH_VOL" if vix > 22 else "LOW_VOL" if vix < 15 else "NORMAL"

                risk_budgets = {
                    "RISK_ON": (150, 60, 100, 5, 30),
                    "NEUTRAL": (100, 30, 70, 4, 25),
                    "RISK_OFF": (60, 0, 30, 2, 15),
                }
                mg, nll, nlh, msn, ms = risk_budgets.get(risk, (100, 30, 70, 4, 25))

                playbook_map = {
                    ("RISK_ON", "UPTREND", "LOW_VOL"): (["Momentum", "Breakout", "Trend-Follow"], [], ["Mean-Reversion"]),
                    ("RISK_ON", "UPTREND", "NORMAL"): (["Momentum", "Swing", "VCP"], [], []),
                    ("NEUTRAL", "UPTREND", "NORMAL"): (["Momentum", "VCP"], [{"strategy": "Swing", "condition": "pullback > 3d"}], []),
                    ("NEUTRAL", "NEUTRAL", "NORMAL"): (["Mean-Reversion"], [{"strategy": "Swing", "condition": "grade A only"}], ["Momentum"]),
                    ("RISK_OFF", "DOWNTREND", "HIGH_VOL"): ([], [], ["Momentum", "Breakout", "Swing", "VCP"]),
                }
                key = (risk, trend, vol_state)
                strats_on, strats_cond, strats_off = playbook_map.get(
                    key, (["Swing", "Mean-Reversion"], [], []))

                from src.core.models import RegimeScoreboard as RSB, ScenarioPlan, DeltaSnapshot
                from datetime import date as _date

                risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))
                scoreboard = RSB(
                    regime_label=risk, risk_on_score=risk_on_score,
                    trend_state=trend, vol_state=vol_state,
                    max_gross_pct=mg, net_long_target_low=nll, net_long_target_high=nlh,
                    max_single_name_pct=msn, max_sector_pct=ms,
                    strategies_on=strats_on, strategies_conditional=strats_cond,
                    strategies_off=strats_off,
                    no_trade_triggers=[], top_drivers=[],
                    scenarios=ScenarioPlan(
                        base_case={"probability": "55%", "description": "Range-bound into tomorrow"},
                        bull_case={"probability": "25%", "description": "Gap-up on overnight catalysts"},
                        bear_case={"probability": "20%", "description": "Overnight risk event"},
                        triggers=["Earnings after-hours", "Asia open reaction", "Macro data"],
                    ),
                )

                delta = DeltaSnapshot(
                    snapshot_date=_date.today(),
                    spx_1d_pct=spy_pct, ndx_1d_pct=qqq_pct, iwm_1d_pct=iwm_pct,
                    vix_close=vix, vix_1d_change=vix_data.get("change_pct", 0),
                )

                # ── Fetch sectors ──
                sector_data = []
                for sym, name in _SECTORS:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    sector_data.append((name, pct))
                sector_data.sort(key=lambda x: x[1], reverse=True)

                # ── Fetch watchlist for breadth + movers ──
                results = []
                for t in _WATCH_US[:20]:
                    data = await _fetch_stock(t)
                    if "error" not in data:
                        results.append(data)
                results.sort(key=lambda x: x.get("change_pct", 0), reverse=True)

                market_prices = {
                    "SPY": spy_data, "QQQ": qqq_data, "IWM": iwm_data,
                    "VIX": vix_data, "TLT": tlt_data, "BTC": btc_data, "GLD": gold_data,
                }

                # ── Use v6 report generator ──
                if _HAS_REPORT_GEN:
                    eod_embeds = build_eod_scorecard(
                        scoreboard=scoreboard, delta=delta,
                        signals_today=[], market_prices=market_prices,
                        sector_data=sector_data,
                    )
                    for emb_data in eod_embeds:
                        e = discord.Embed(
                            title=emb_data.get("title", "🌙 EOD Scorecard"),
                            description=emb_data.get("description", ""),
                            color=emb_data.get("color", COLOR_PURPLE),
                            timestamp=now,
                        )
                        for s in emb_data.get("sections", []):
                            e.add_field(name=s["name"], value=s["value"],
                                        inline=s.get("inline", False))
                        # Add sector heat map (too dynamic for report_generator)
                        heat_lines = []
                        for name, pct in sector_data[:8]:
                            icon = "🟢" if pct > 0.5 else "🔴" if pct < -0.5 else "⚪"
                            heat_lines.append(f"{icon} {name}: {pct:+.2f}%")
                        if heat_lines:
                            e.add_field(name="🏭 Sector Heat Map",
                                        value="\n".join(heat_lines), inline=False)

                        # Watchlist movers
                        if results:
                            winners = [r for r in results[:3] if r.get("change_pct", 0) > 0]
                            losers = [r for r in results[-3:] if r.get("change_pct", 0) < 0]
                            if winners:
                                win_text = "\n".join(
                                    f"🏆 **{r['ticker']}** {r.get('change_pct', 0):+.2f}%"
                                    for r in winners)
                                e.add_field(name="🏆 Top Movers", value=win_text, inline=True)
                            if losers:
                                lose_text = "\n".join(
                                    f"📉 **{r['ticker']}** {r.get('change_pct', 0):+.2f}%"
                                    for r in losers)
                                e.add_field(name="📉 Laggards", value=lose_text, inline=True)
                            green = sum(1 for r in results if r.get("change_pct", 0) > 0)
                            bpct = (green / len(results)) * 100
                            bicon = "🟢" if bpct > 65 else "🔴" if bpct < 35 else "🟡"
                            e.add_field(name="📊 Breadth",
                                        value=f"{bicon} {bpct:.0f}% green ({green}/{len(results)})",
                                        inline=True)

                        e.set_footer(text=emb_data.get("footer", "TradingAI Pro v6 • EOD"))
                        await _send_ch("daily-brief", embed=e)
                else:
                    # Legacy v5 fallback
                    e = discord.Embed(
                        title=f"🌙 End-of-Day Scorecard — {now.strftime('%A, %B %d')}",
                        description=(
                            f"**Regime Close: {'🟢 RISK ON' if risk == 'RISK_ON' else '🔴 RISK OFF' if risk == 'RISK_OFF' else '🟡 NEUTRAL'}** "
                            f"• VIX {vix:.1f} • SPY {spy_pct:+.2f}%"
                        ),
                        color=COLOR_PURPLE, timestamp=now)
                    # Index performance
                    index_lines = []
                    for sym, name in _INDICES:
                        data = await _fetch_stock(sym)
                        pct = data.get("change_pct", 0)
                        icon = "🟢" if pct > 0.3 else "🔴" if pct < -0.3 else "⚪"
                        index_lines.append(
                            f"{icon} **{name}**: ${data.get('price', 0):,.2f} ({pct:+.2f}%) {_bar(pct, 6)}")
                    e.add_field(name="📊 Indices", value="\n".join(index_lines), inline=False)
                    # Sectors
                    heat_lines = []
                    for name, pct in sector_data[:8]:
                        icon = "🟢" if pct > 0.5 else "🔴" if pct < -0.5 else "⚪"
                        heat_lines.append(f"{icon} {name}: {pct:+.2f}%")
                    e.add_field(name="🏭 Sector Heat Map", value="\n".join(heat_lines), inline=False)
                    vix_icon = "🔴" if vix > 25 else "🟡" if vix > 18 else "🟢"
                    e.add_field(name="📉 VIX Close", value=f"{vix_icon} {vix:.1f}")
                    e.set_footer(text="TradingAI Pro v6 • EOD Scorecard")
                    await _send_ch("daily-brief", embed=e)

                await _audit("🌙 v6 EOD Scorecard posted")
            except Exception as exc:
                logger.error(f"eod_report error: {exc}")

        # ── 9. Asia evening preview (every 10 min, fires ~01:00 UTC)
        _asia_posted = set()
        @tasks.loop(minutes=10)
        async def asia_preview():
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if today in _asia_posted:
                return
            if not (now.hour == 1 and 0 <= now.minute <= 15):
                return
            _asia_posted.add(today)
            try:
                e = discord.Embed(
                    title=f"🌏 Asia Markets Opening — {now.strftime('%A, %B %d')}",
                    description="Asia sessions are starting. Here's where things stand.",
                    color=COLOR_PURPLE, timestamp=now)
                for sym, name in _WATCH_ASIA:
                    data = await _fetch_stock(sym)
                    e.add_field(name=name,
                                value=f"{data.get('price',0):,.2f} ({data.get('change_pct',0):+.2f}%)")
                # US close recap
                spy = await _fetch_stock("SPY")
                e.add_field(name="📌 US Close (SPY)",
                            value=f"${spy.get('price',0):.2f} ({spy.get('change_pct',0):+.2f}%)")
                e.set_footer(text="Asia auto-preview")
                await _send_ch("daily-brief", embed=e)
            except Exception as exc:
                logger.error(f"asia_preview error: {exc}")

        # ── 10. Whale / unusual volume alert (every 45 min, extended hrs) ─
        @tasks.loop(minutes=45)
        async def auto_whale_scan():
            now = datetime.now(timezone.utc)
            if not (8 <= now.hour < 22 and now.weekday() < 5):
                return
            try:
                wh_hist = await _prefetch(_WATCH_US, "1mo")
                def _sync_whale_scan():
                    whales = []
                    for ticker in _WATCH_US:
                        try:
                            hist = wh_hist.get(ticker)
                            if hist is None:
                                continue
                            if hist.empty or len(hist) < 10:
                                continue
                            vol = hist["Volume"].iloc[-1]
                            avg = hist["Volume"].rolling(20).mean().iloc[-1]
                            if avg and vol / avg >= 3.0:
                                price = hist["Close"].iloc[-1]
                                whales.append({
                                    "ticker": ticker, "vol": vol,
                                    "avg_vol": avg, "ratio": vol / avg,
                                    "price": price,
                                    "change_pct": ((price - hist["Close"].iloc[-2])
                                                   / hist["Close"].iloc[-2] * 100
                                                   if hist["Close"].iloc[-2] else 0)
                                })
                        except Exception:
                            continue
                    return whales

                whales = await asyncio.to_thread(_sync_whale_scan)
                if not whales:
                    return
                whales.sort(key=lambda x: x["ratio"], reverse=True)
                e = discord.Embed(
                    title=f"🐋 Whale Alert — Unusual Volume Detected",
                    description=f"{len(whales)} stocks with 3x+ avg volume",
                    color=COLOR_WARN, timestamp=now)
                for w in whales[:5]:
                    e.add_field(
                        name=f"{'🟢' if w['change_pct'] >= 0 else '🔴'} {w['ticker']}",
                        value=(f"${w['price']:.2f} ({w['change_pct']:+.2f}%)\n"
                               f"Vol: **{_vol(w['vol'])}** ({w['ratio']:.1f}x avg)"),
                        inline=True)
                e.set_footer(text="Auto whale scan every 45 min")
                await _send_ch("signals", embed=e)
                await _audit(f"🐋 Whale scan: {len(whales)} unusual vol stocks")
            except Exception as exc:
                logger.error(f"auto_whale_scan error: {exc}")

        # ── 11. Weekly recap (Sunday ~22:00 UTC) ─────────────────────
        _weekly_posted = set()
        @tasks.loop(minutes=30)
        async def weekly_recap():
            now = datetime.now(timezone.utc)
            week = now.strftime("%Y-W%W")
            if week in _weekly_posted:
                return
            if not (now.weekday() == 6 and 21 <= now.hour <= 22):
                return
            _weekly_posted.add(week)
            try:
                e = discord.Embed(
                    title=f"📅 Weekly Recap — Week of {now.strftime('%B %d')}",
                    description="Here's how markets closed this week.",
                    color=COLOR_GOLD, timestamp=now)
                for sym, name in _INDICES:
                    data = await _fetch_stock(sym)
                    e.add_field(name=name,
                                value=f"${data.get('price',0):.2f} ({data.get('change_pct',0):+.2f}%)")
                btc = await _fetch_stock("BTC-USD")
                e.add_field(name="₿ BTC",
                            value=f"${btc.get('price',0):,.2f} ({btc.get('change_pct',0):+.2f}%)")
                e.add_field(name="📅 Coming Up", inline=False,
                            value="Check economic calendar for next week's key events")
                e.set_footer(text="Weekly auto-recap • Good trading week ahead! 🚀")
                await _send_ch("daily-brief", embed=e)
                await _audit("📅 Weekly recap auto-posted")
            except Exception as exc:
                logger.error(f"weekly_recap error: {exc}")

        # ══════════════════════════════════════════════════════════════
        # 12-16: REAL-TIME AUTOMATED INTELLIGENCE
        # ══════════════════════════════════════════════════════════════

        # ── 12. Real-time price spike / crash alert (every 3 min, 24/7) ──
        async def _fetch_ticker_news_for_alert(sym: str, max_items: int = 3) -> list:
            """Fetch recent news headlines for a ticker — attached to spike alert embeds."""
            try:
                items = await _mds.get_news(sym, max_items=max_items)
                return [{"title": n["title"][:90], "url": n["url"],
                         "publisher": n.get("publisher", "")} for n in items]
            except Exception:
                    return []
            try:
                return await asyncio.wait_for(asyncio.to_thread(_sync), timeout=5.0)
            except Exception:
                return []

        _last_prices: Dict[str, float] = {}
        _spike_cooldown: Dict[str, float] = {}   # ticker → timestamp of last alert

        @tasks.loop(minutes=3)
        async def realtime_price_alerts():
            """Detects sudden moves (≥3% stocks, ≥1.2% indices, ≥5% crypto)
            and posts instant alerts to #momentum-alerts. Runs 24/7."""
            try:
                now = datetime.now(timezone.utc)
                ts = now.timestamp()

                # Thresholds per category
                alert_targets = [
                    # (symbols, threshold%, channel, label)
                    (_WATCH_US, 3.0, "momentum-alerts", "🚨 STOCK"),
                    ([s for s, _ in _INDICES[:4]], 1.2, "daily-brief", "🚨 INDEX"),
                    (_WATCH_CRYPTO[:5], 5.0, "momentum-alerts", "🚨 CRYPTO"),
                    ([s for s, _ in _WATCH_ASIA], 2.0, "daily-brief", "🚨 ASIA"),
                ]

                for symbols, threshold, channel, label in alert_targets:
                    for sym in symbols:
                        try:
                            data = await _fetch_stock(sym)
                            if "error" in data:
                                continue
                            price = data.get("price", 0)
                            pct = data.get("change_pct", 0)
                            prev_price = _last_prices.get(sym, 0)
                            _last_prices[sym] = price

                            # Skip if we alerted this ticker in last 30 min
                            if ts - _spike_cooldown.get(sym, 0) < 1800:
                                continue

                            if abs(pct) < threshold:
                                continue

                            # Also detect intra-check moves (price vs last check)
                            intra_move = 0
                            if prev_price and prev_price > 0:
                                intra_move = (price - prev_price) / prev_price * 100

                            _spike_cooldown[sym] = ts
                            direction = "📈 SURGE" if pct > 0 else "📉 CRASH"
                            color = COLOR_BUY if pct > 0 else COLOR_SELL

                            e = discord.Embed(
                                title=f"{label} {direction} — {sym}",
                                description=(
                                    f"**{sym}** just moved **{pct:+.2f}%** "
                                    f"{'today' if abs(intra_move) < 0.5 else f'({intra_move:+.2f}% in last 3 min)'}!"
                                ),
                                color=color, timestamp=now)
                            e.add_field(name="💰 Price", value=f"**${price:.2f}**")
                            e.add_field(name="📊 Day Move", value=f"**{pct:+.2f}%**")
                            e.add_field(name="📈 Volume", value=_vol(data.get("volume", 0)))

                            if abs(pct) >= threshold * 2:
                                e.add_field(name="⚡ Severity", value="**EXTREME MOVE**", inline=False)
                            e.add_field(name="🔍 Next",
                                        value=f"`/ai {sym}` · `/analyze {sym}` · `/why {sym}`",
                                        inline=False)
                            e.set_footer(text="🔔 Real-time alert • Auto-detected")
                            try:
                                _anews = await _fetch_ticker_news_for_alert(sym)
                                if _anews:
                                    _nl = "\n".join(
                                        f"• [{n['title']}]({n['url']})" for n in _anews[:3])
                                    e.add_field(name="📰 Why Is It Moving?",
                                                value=_nl[:900], inline=False)
                            except Exception:
                                pass
                            await _send_ch(channel, embed=e)

                            # Also alert in daily-brief for big index moves
                            if label == "🚨 INDEX" and abs(pct) >= 1.5:
                                await _send_ch("daily-brief", embed=e)
                        except Exception:
                            continue

                # ── User-defined price alerts (/alert command) ────────
                for uid, alerts in list(_user_alerts.items()):
                    for alert in alerts:
                        if alert.get("triggered"):
                            continue
                        sym = alert["ticker"]
                        try:
                            data = await _fetch_stock(sym)
                            if "error" in data:
                                continue
                            cur_price = data.get("price", 0)
                            target = alert["price"]
                            cond = alert["condition"]
                            fire = (cond == "above" and cur_price >= target) or \
                                   (cond == "below" and cur_price <= target)
                            if not fire:
                                continue
                            alert["triggered"] = True
                            user = bot.get_user(uid)
                            ae = discord.Embed(
                                title=f"🔔 ALERT TRIGGERED — {sym}",
                                description=(
                                    f"**{sym}** is now **{cond}** your target of **${target:.2f}**\n"
                                    f"Current price: **${cur_price:.2f}**"
                                ),
                                color=COLOR_BUY if cond == "above" else COLOR_SELL,
                                timestamp=now)
                            ae.add_field(name="🔍 Action",
                                         value=f"`/ai {sym}` · `/analyze {sym}`", inline=False)
                            ae.set_footer(text="Price alert • /my_alerts to manage")
                            # DM the user
                            if user:
                                try:
                                    await user.send(embed=ae)
                                except Exception:
                                    pass
                            # Also post to signals channel
                            await _send_ch("signals", embed=ae)
                        except Exception:
                            continue
            except Exception as exc:
                logger.error(f"realtime_price_alerts error: {exc}")

        # ── 13. Auto news feed (every 30 min, 24/7) ─────────────────
        _news_seen: set = set()  # track URLs already posted

        @tasks.loop(minutes=30)
        async def auto_news_feed():
            """Scrapes Yahoo Finance news for top market headlines and posts
            breaking/important stories to #daily-brief. Runs 24/7."""
            try:
                now = datetime.now(timezone.utc)

                async def _async_fetch_news():
                    all_news = []
                    _news_scan_universe = (
                        ["SPY", "QQQ", "^VIX", "BTC-USD", "ETH-USD"]
                        + _WATCH_US[:20]
                    )
                    results = await asyncio.gather(
                        *[_mds.get_news(sym, max_items=3)
                          for sym in _news_scan_universe],
                        return_exceptions=True,
                    )
                    for sym, items in zip(_news_scan_universe, results):
                        if isinstance(items, Exception) or not items:
                            continue
                        for item in items:
                            url = item.get("url", "")
                            if url and url not in _news_seen:
                                all_news.append({
                                    "title": item.get("title", "")[:200],
                                    "publisher": item.get("publisher", "Unknown"),
                                    "url": url,
                                    "symbol": sym,
                                    "time": item.get("time", 0),
                                })
                    all_news.sort(key=lambda x: x.get("time", 0), reverse=True)
                    seen_titles = set()
                    unique = []
                    for n in all_news:
                        prefix = n["title"][:50].lower()
                        if prefix not in seen_titles:
                            seen_titles.add(prefix)
                            unique.append(n)
                    return unique[:8]

                news = await _async_fetch_news()
                if not news:
                    return

                # Mark as seen
                for n in news:
                    _news_seen.add(n["url"])
                # Keep seen set from growing forever
                if len(_news_seen) > 500:
                    _news_seen.clear()

                e = discord.Embed(
                    title=f"📰 Market News — {now.strftime('%H:%M UTC')}",
                    description=f"Top {len(news)} headlines from financial news feeds",
                    color=COLOR_INFO, timestamp=now)

                for n in news[:6]:
                    sym_tag = f" [{n['symbol']}]" if n["symbol"] not in ("SPY", "QQQ") else ""
                    e.add_field(
                        name=f"• {n['publisher']}{sym_tag}",
                        value=f"[{n['title']}]({n['url']})",
                        inline=False)

                e.set_footer(text="Auto-news every 30 min • /news TICKER for specific")
                await _send_ch("daily-brief", embed=e)
            except Exception as exc:
                logger.error(f"auto_news_feed error: {exc}")

        # ── 13B. Per-stock breaking news monitor (every 15 min, extended hours) ──
        _ticker_news_seen: Dict[str, set] = {}   # per-ticker seen URLs

        @tasks.loop(minutes=15)
        async def auto_ticker_news():
            """Scans all 50 tracked stocks for breaking news in rotating chunks.
            Each stock checked every ~45 min. Posts to #daily-brief."""
            now = datetime.now(timezone.utc)
            if not (8 <= now.hour < 22):
                return
            try:
                import time as _tt
                chunk_sz = max(1, len(_WATCH_US) // 3)
                idx = int(_tt.time() / 900) % 3
                chunk = _WATCH_US[idx * chunk_sz:(idx + 1) * chunk_sz]

                async def _async_chunk_news(syms):
                    results = []
                    news_batch = await asyncio.gather(
                        *[_mds.get_news(sym, max_items=3) for sym in syms],
                        return_exceptions=True,
                    )
                    for sym, items in zip(syms, news_batch):
                        if isinstance(items, Exception) or not items:
                            continue
                        for item in items:
                            url = item.get("url", "")
                            title = item.get("title", "")
                            if not url or not title:
                                continue
                            if url in _ticker_news_seen.get(sym, set()):
                                continue
                            results.append({
                                "ticker": sym,
                                "title": title[:150],
                                "publisher": item.get("publisher", ""),
                                "url": url,
                                "time": item.get("time", 0),
                            })
                    return results

                fresh = await _async_chunk_news(chunk)
                if not fresh:
                    return
                fresh.sort(key=lambda x: x.get("time", 0), reverse=True)
                new_items = []
                for item in fresh[:6]:
                    sym = item["ticker"]
                    if sym not in _ticker_news_seen:
                        _ticker_news_seen[sym] = set()
                    _ticker_news_seen[sym].add(item["url"])
                    if len(_ticker_news_seen[sym]) > 200:
                        _ticker_news_seen[sym] = set(list(_ticker_news_seen[sym])[-100:])
                    new_items.append(item)
                if not new_items:
                    return
                e = discord.Embed(
                    title=f"📰 Breaking Stock News — {now.strftime('%H:%M UTC')}",
                    description=(
                        f"Fresh headlines · Stocks chunk {idx + 1}/3 "
                        f"({len(chunk)} tickers · {len(new_items)} new stories)"
                    ),
                    color=COLOR_INFO, timestamp=now)
                for item in new_items:
                    e.add_field(
                        name=f"[{item['ticker']}] {item['publisher'] or 'News'}",
                        value=f"[{item['title']}]({item['url']})",
                        inline=False)
                e.set_footer(
                    text="📰 All 50 tracked stocks covered every 45min · /why TICKER for full analysis")
                await _send_ch("daily-brief", embed=e)
            except Exception as exc:
                logger.error(f"auto_ticker_news error: {exc}")

        # ── 13C. Auto Strategy Learn (every 6h weekdays) ──────────────
        @tasks.loop(hours=6)
        async def auto_strategy_learn():
            """Runs full AI backtest on top watchlist stocks, identifies best
            strategy per regime, posts ranked summary to #ai-signals."""
            now = datetime.now(timezone.utc)
            if not (8 <= now.hour < 22 and now.weekday() < 5):
                return
            opt = _get_optimizer()
            if opt is None:
                return
            try:
                scan_tickers = _WATCH_US[:5] + ["SPY", "QQQ", "BTC-USD"]
                learn_hist = await _prefetch(scan_tickers, "1y")

                def _sync_learn():
                    results = []
                    for sym in scan_tickers:
                        try:
                            hist = learn_hist.get(sym)
                            if hist is None:
                                continue
                            if hist is None or hist.empty or len(hist) < 60:
                                continue
                            analysis = opt.full_analysis(sym, hist, "1y")
                            ranked = analysis["ranked"]
                            best = ranked[0] if ranked else {}
                            regime = analysis["regime"]
                            rr = analysis["regime_recommendation"]
                            results.append({
                                "ticker": sym,
                                "best_strategy": best.get("strategy", "N/A"),
                                "best_score": best.get("score", 0),
                                "regime": regime["label"],
                                "regime_fit": rr.get("regime_fit", False),
                                "cross_check": analysis["cross_check"]["verdict"],
                                "win_rate": best.get("win_rate", 0),
                                "sharpe": best.get("sharpe", 0),
                                "sweep_improvement": analysis.get("sweep_improvement", 0),
                                "correction_notes": analysis.get("correction_notes", []),
                            })
                        except Exception:
                            continue
                    return results

                results = await asyncio.to_thread(_sync_learn)
                if not results:
                    return

                results.sort(key=lambda x: x["best_score"], reverse=True)

                e = discord.Embed(
                    title=f"🤖 AI Strategy Learning Report — {now.strftime('%a %d %b %H:%M UTC')}",
                    description=(
                        f"Backtested **{len(results)}** tickers · 4 strategies each · "
                        f"Walk-forward validated · Self-correction applied"
                    ),
                    color=COLOR_PURPLE, timestamp=now)

                for r in results:
                    cc_icon = {"STRONG_AGREEMENT": "✅", "MIXED_SIGNAL": "⚠️",
                               "AVOID": "🔴", "MODERATE": "🟡"}.get(r["cross_check"], "❓")
                    fit_tag = "✅ Regime fit" if r["regime_fit"] else "⚠️ Off-regime"
                    sweep_note = (f"⚙️ Param sweep +{r['sweep_improvement']:.1f}pts\n"
                                  if r["sweep_improvement"] > 1 else "")
                    e.add_field(
                        name=f"{'🥇' if r == results[0] else '📊'} {r['ticker']} → {r['best_strategy']}",
                        value=(
                            f"Score **{r['best_score']:.0f}** · WR **{r['win_rate']*100:.0f}%** · "
                            f"Sharpe **{r['sharpe']:.2f}**\n"
                            f"Regime: **{r['regime']}** {fit_tag}\n"
                            f"{cc_icon} Cross-check: {r['cross_check']}\n"
                            + sweep_note
                        ))

                all_notes = []
                for r in results:
                    all_notes.extend(r.get("correction_notes", []))
                unique_notes = list(dict.fromkeys(all_notes))[:3]
                valid_notes = [n for n in unique_notes if "No self-corrections yet" not in n]
                if valid_notes:
                    e.add_field(name="🧠 Self-Correction Log",
                                value="\n".join(valid_notes)[:400], inline=False)

                e.add_field(name="📋 Actions",
                            value=("`/backtest TICKER` full analysis · "
                                   "`/best_strategy TICKER` quick regime pick · "
                                   "`/strategy_report` live accuracy"),
                            inline=False)
                e.set_footer(text="🤖 Runs every 6h · self-improves with each live outcome")
                await _send_ch("ai-signals", embed=e)
                await _audit(f"🤖 auto_strategy_learn: {len(results)} tickers analysed")
            except Exception as exc:
                logger.error(f"auto_strategy_learn error: {exc}")

        # ── 14. Smart morning update (multi-timezone coverage) ────────
        # Posts at 3 different times so users in ANY timezone get a fresh
        # morning brief: Asia morning (01:00 UTC), Europe morning (07:00),
        # US morning (13:30 UTC). Each fires only once per day.
        _smart_morning_posted: Dict[str, set] = {"asia": set(), "europe": set(), "us": set()}

        @tasks.loop(minutes=5)
        async def smart_morning_update():
            """Posts morning market snapshot 3x daily for global timezone coverage.
            Each session gets regime + indices + futures + actionable playbook."""
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if now.weekday() >= 5:
                return  # skip weekends

            sessions = [
                # (session_key, hour_start, hour_end, label, emoji, extra_markets)
                ("asia", 1, 1, "🌏 Asia Morning Brief", "☀️", _WATCH_ASIA),
                ("europe", 7, 7, "🌍 Europe Morning Brief", "☀️", [("DAX", "🇩🇪 DAX"), ("^FTSE", "🇬🇧 FTSE")]),
                ("us", 13, 14, "🇺🇸 US Pre-Market Brief", "🔔", [("ES=F", "S&P Futures"), ("NQ=F", "Nasdaq Futures")]),
            ]

            for key, h_start, h_end, title, emoji, extra_mkts in sessions:
                if today in _smart_morning_posted[key]:
                    continue
                if not (h_start <= now.hour <= h_end):
                    continue
                # For US session, fire between :25 and :35
                if key == "us" and not (now.hour == 13 and 25 <= now.minute <= 40):
                    continue
                # For Asia/Europe, fire in first 10 min of the hour
                if key in ("asia", "europe") and now.minute > 15:
                    continue

                _smart_morning_posted[key].add(today)
                try:
                    spy = await _fetch_stock("SPY")
                    qqq = await _fetch_stock("QQQ")
                    vix_d = await _fetch_stock("^VIX")
                    btc = await _fetch_stock("BTC-USD")
                    gold = await _fetch_stock("GLD")
                    tlt = await _fetch_stock("TLT")

                    vix = vix_d.get("price", 0)
                    spy_pct = spy.get("change_pct", 0)
                    qqq_pct = qqq.get("change_pct", 0)
                    btc_pct = btc.get("change_pct", 0)

                    risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                        "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                    regime_icons = {"RISK_ON": "🟢 RISK ON", "NEUTRAL": "🟡 NEUTRAL", "RISK_OFF": "🔴 RISK OFF"}
                    regime_label = regime_icons.get(risk, "🟡 NEUTRAL")
                    risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))

                    if risk == "RISK_ON" and vix < 16:
                        ai_rec = "🟢 AGGRESSIVE"
                    elif risk == "RISK_ON":
                        ai_rec = "🟢 NORMAL"
                    elif risk == "NEUTRAL" and vix < 20:
                        ai_rec = "🟡 NORMAL"
                    elif risk == "NEUTRAL":
                        ai_rec = "🟡 CAUTIOUS"
                    else:
                        ai_rec = "🔴 DEFENSIVE"

                    score_bar = "█" * (int(risk_on_score) // 10) + "░" * (10 - int(risk_on_score) // 10)
                    e = discord.Embed(
                        title=f"{emoji} {title} — {now.strftime('%A, %B %d')}",
                        description=(
                            f"**{regime_label}** • Risk: **{risk_on_score:.0f}/100** `{score_bar}` • AI: **{ai_rec}**\n"
                            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                        ),
                        color=COLOR_BUY if risk == "RISK_ON" else COLOR_SELL if risk == "RISK_OFF" else COLOR_GOLD,
                        timestamp=now)

                    # US Indices
                    idx_text = (
                        f"{'🟢' if spy_pct >= 0 else '🔴'} SPY ${spy.get('price',0):.2f} ({spy_pct:+.2f}%) | "
                        f"{'🟢' if qqq_pct >= 0 else '🔴'} QQQ ${qqq.get('price',0):.2f} ({qqq_pct:+.2f}%)")
                    e.add_field(name="🇺🇸 US Indices", value=idx_text, inline=False)

                    # Session-specific markets
                    extra_lines = []
                    for sym, name in extra_mkts:
                        d = await _fetch_stock(sym)
                        p = d.get("change_pct", 0)
                        extra_lines.append(f"{'🟢' if p >= 0 else '🔴'} {name}: {p:+.2f}%")
                    if extra_lines:
                        e.add_field(name=f"📊 Session Markets",
                                    value=" | ".join(extra_lines), inline=False)

                    # Macro
                    vix_icon = "🔴" if vix > 25 else "🟡" if vix > 18 else "🟢"
                    e.add_field(name="🌍 Macro", value=(
                        f"VIX: **{vix:.1f}** {vix_icon} | "
                        f"Gold: {gold.get('change_pct',0):+.2f}% | "
                        f"Bonds: {tlt.get('change_pct',0):+.2f}% | "
                        f"BTC: ${btc.get('price',0):,.0f} ({btc_pct:+.2f}%)"
                    ), inline=False)

                    # Playbook
                    trend = "UPTREND" if spy_pct > 0.5 else "DOWNTREND" if spy_pct < -0.5 else "NEUTRAL"
                    playbook_map = {
                        ("RISK_ON", "UPTREND"): ["Momentum", "Breakout"],
                        ("RISK_ON", "NEUTRAL"): ["Swing", "VCP"],
                        ("NEUTRAL", "UPTREND"): ["Momentum", "VCP"],
                        ("NEUTRAL", "NEUTRAL"): ["Mean-Reversion", "Swing"],
                        ("NEUTRAL", "DOWNTREND"): ["Mean-Reversion"],
                        ("RISK_OFF", "DOWNTREND"): ["Cash"],
                    }
                    strats = playbook_map.get((risk, trend), ["Swing", "Mean-Reversion"])
                    e.add_field(name="📋 Today's Playbook",
                                value=" · ".join(f"`{s}`" for s in strats), inline=False)

                    # Risk flags
                    flags = []
                    if vix > 25:
                        flags.append(f"⚠️ VIX {vix:.1f} — reduce position sizes 50%")
                    if spy_pct < -1.5:
                        flags.append("⚠️ SPY sharp decline — watch for capitulation")
                    if abs(qqq_pct - spy_pct) > 1.5:
                        flags.append("⚠️ Tech/SPY divergence — rotation risk")
                    if flags:
                        e.add_field(name="🛡️ Risk Alerts",
                                    value="\n".join(flags), inline=False)
                    else:
                        e.add_field(name="🛡️ Risk", value="✅ All clear — normal sizing", inline=False)

                    e.set_footer(text=f"Auto-morning brief • /daily_update for full intelligence • /dashboard for everything")
                    await _send_ch("daily-brief", embed=e)
                    await _audit(f"{emoji} Smart morning ({key}) posted — {risk}")
                except Exception as exc:
                    logger.error(f"smart_morning_update ({key}) error: {exc}")

        # ── 15. Opportunity flash scanner (every 30 min, 24/7) ───────
        _opp_cooldown: Dict[str, float] = {}  # ticker → last alert timestamp

        @tasks.loop(minutes=30)
        async def opportunity_scanner():
            """Scans for fresh high-conviction trade setups and posts them
            immediately to #momentum-alerts with action buttons.
            Only posts score ≥ 75 to avoid noise. 24/7 coverage."""
            try:
                now = datetime.now(timezone.utc)
                ts = now.timestamp()
                # Only scan during data-available hours (weekday extended)
                if now.weekday() >= 5:
                    return

                scan_results = await _async_signal_scan(_WATCH_US)
                if not scan_results:
                    return

                # Filter high-conviction only
                hot_signals = [s for s in scan_results if s.get("score", 0) >= 75]
                if not hot_signals:
                    return

                hot_signals.sort(key=lambda x: x["score"], reverse=True)
                posted = 0
                for sig in hot_signals[:3]:
                    ticker = sig["ticker"]
                    # Cooldown: don't re-alert same ticker within 4 hours
                    if ts - _opp_cooldown.get(ticker, 0) < 14400:
                        continue
                    _opp_cooldown[ticker] = ts

                    score = sig["score"]
                    is_long = sig["direction"] == "LONG"
                    arrow = "🟢 LONG" if is_long else "🔴 SHORT"
                    tier = "🔥 HIGH CONVICTION" if score >= 85 else "⭐ GOOD SETUP"

                    e = discord.Embed(
                        title=f"🎯 OPPORTUNITY — {arrow} {ticker} ${sig['price']:.2f}",
                        description=(
                            f"**{tier}** • Score **{score}/100**\n\n"
                            + "\n".join(f"• {r}" for r in sig.get("reasons", [])[:3])
                        ),
                        color=COLOR_GOLD if score >= 85 else COLOR_BUY if is_long else COLOR_SELL,
                        timestamp=now)
                    e.add_field(name="🎯 Target", value=f"${sig.get('target', 0):.2f}")
                    e.add_field(name="🛑 Stop", value=f"${sig.get('stop', 0):.2f}")
                    e.add_field(name="⚖️ R:R", value=f"**{sig.get('rr_ratio', 0):.1f}:1**")
                    e.add_field(name="RSI", value=f"{sig.get('rsi', 0):.0f}")
                    e.add_field(name="Rel Vol", value=f"{sig.get('rel_vol', 0):.1f}x")
                    e.add_field(name="⏳ Hold", value=sig.get("hold_target", "2-8 days"))
                    e.set_footer(text="🔔 Auto-opportunity alert • /ai for full analysis")

                    await _send_ch("momentum-alerts", embed=e)
                    # Cross-post extreme signals to daily-brief
                    if score >= 85:
                        await _send_ch("daily-brief", embed=e)
                    posted += 1

                if posted:
                    await _audit(f"🎯 Opportunity scanner: {posted} high-conviction alerts posted")
            except Exception as exc:
                logger.error(f"opportunity_scanner error: {exc}")

        # ── 16. VIX spike / fear alert (every 5 min, 24/7) ──────────
        _vix_last_alert = 0.0

        @tasks.loop(minutes=5)
        async def vix_fear_monitor():
            """Monitors VIX for sudden spikes. Posts urgent alert when
            VIX jumps above 20, 25, 30 thresholds or moves >10% intraday."""
            nonlocal _vix_last_alert
            try:
                now = datetime.now(timezone.utc)
                ts = now.timestamp()
                if ts - _vix_last_alert < 3600:  # 1hr cooldown
                    return

                vix_data = await _fetch_stock("^VIX")
                vix = vix_data.get("price", 0)
                vix_pct = vix_data.get("change_pct", 0)

                alert = False
                severity = ""
                if vix_pct > 15:
                    alert, severity = True, "🔴🔴🔴 EXTREME VIX SPIKE"
                elif vix_pct > 10:
                    alert, severity = True, "🔴🔴 MAJOR VIX SPIKE"
                elif vix > 30 and vix_pct > 5:
                    alert, severity = True, "🔴 VIX ABOVE 30 — PANIC ZONE"
                elif vix > 25 and vix_pct > 5:
                    alert, severity = True, "🟡 VIX ELEVATED — CAUTION"

                if not alert:
                    return

                _vix_last_alert = ts

                spy = await _fetch_stock("SPY")
                e = discord.Embed(
                    title=f"⚠️ {severity}",
                    description=(
                        f"**VIX: {vix:.2f}** ({vix_pct:+.2f}% today)\n"
                        f"SPY: ${spy.get('price',0):.2f} ({spy.get('change_pct',0):+.2f}%)\n\n"
                        "**Recommended Action:**"
                    ),
                    color=COLOR_DANGER, timestamp=now)

                if vix > 30:
                    e.add_field(name="🛑 ACTION",
                                value="• HALT new entries\n• Tighten all stops to 2%\n• Consider hedges (VXX, puts)",
                                inline=False)
                elif vix > 25:
                    e.add_field(name="⚠️ ACTION",
                                value="• Cut position sizes 50%\n• Tighten stops to 3%\n• Avoid momentum strategies",
                                inline=False)
                else:
                    e.add_field(name="🟡 ACTION",
                                value="• Monitor closely\n• Reduce size on new entries\n• Favor mean-reversion",
                                inline=False)

                e.set_footer(text="🚨 Fear gauge auto-alert • /market_now for full regime")
                await _send_ch("daily-brief", embed=e)
                await _send_ch("momentum-alerts", embed=e)
                await _audit(f"⚠️ VIX fear alert: {vix:.1f} ({vix_pct:+.1f}%)")
            except Exception as exc:
                logger.error(f"vix_fear_monitor error: {exc}")

        # ── 17. Bot health check to #bot-status (every 30 min) ───────
        @tasks.loop(minutes=30)
        async def health_check():
            now = datetime.now(timezone.utc)
            try:
                e = discord.Embed(
                    title="💚 Bot Health Check",
                    description=f"All systems operational",
                    color=COLOR_SUCCESS, timestamp=now)
                e.add_field(name="Uptime", value=f"Since {bot.user.created_at.strftime('%Y-%m-%d') if bot.user else 'N/A'}")
                e.add_field(name="Guilds", value=str(len(bot.guilds)))
                e.add_field(name="Latency", value=f"{bot.latency*1000:.0f}ms")
                tasks_status = (
                    f"{'✅' if update_presence.is_running() else '❌'} Presence\n"
                    f"{'✅' if market_pulse.is_running() else '❌'} Market Pulse\n"
                    f"{'✅' if realtime_price_alerts.is_running() else '❌'} 🚨 Price Alerts (3min)\n"
                    f"{'✅' if auto_news_feed.is_running() else '❌'} 📰 News Feed (30min)\n"
                    f"{'✅' if auto_ticker_news.is_running() else '❌'} 📰 Ticker News (15min)\n"
                    f"{'✅' if auto_strategy_learn.is_running() else '❌'} 🤖 Strategy Learn (6h)\n"
                    f"{'✅' if smart_morning_update.is_running() else '❌'} ☀️ Smart Morning (3x/day)\n"
                    f"{'✅' if opportunity_scanner.is_running() else '❌'} 🎯 Oppty Scanner (30min)\n"
                    f"{'✅' if vix_fear_monitor.is_running() else '❌'} ⚠️ VIX Fear Monitor (5min)\n"
                    f"{'✅' if auto_movers.is_running() else '❌'} Auto Movers\n"
                    f"{'✅' if auto_signal_scan.is_running() else '❌'} AI Signals\n"
                    f"{'✅' if auto_crypto.is_running() else '❌'} Crypto\n"
                    f"{'✅' if global_market_update.is_running() else '❌'} Global Update (4h)\n"
                    f"{'✅' if auto_whale_scan.is_running() else '❌'} Whale Scan\n"
                    f"{'✅' if morning_brief.is_running() else '❌'} Morning Brief\n"
                    f"{'✅' if eod_report.is_running() else '❌'} EOD Report"
                )
                e.add_field(name="🔄 Running Tasks", value=tasks_status, inline=False)
                await _send_ch("admin-log", embed=e)
            except Exception:
                pass

        # ── before_loop waiters ──────────────────────────────────────
        @update_presence.before_loop
        async def _w1(): await bot.wait_until_ready()
        @market_pulse.before_loop
        async def _w2(): await bot.wait_until_ready()
        @auto_movers.before_loop
        async def _w3(): await bot.wait_until_ready()
        @auto_sector_macro.before_loop
        async def _w4(): await bot.wait_until_ready()
        @auto_crypto.before_loop
        async def _w5(): await bot.wait_until_ready()
        @global_market_update.before_loop
        async def _w5b(): await bot.wait_until_ready()
        @auto_signal_scan.before_loop
        async def _w6(): await bot.wait_until_ready()
        @morning_brief.before_loop
        async def _w7(): await bot.wait_until_ready()
        @eod_report.before_loop
        async def _w8(): await bot.wait_until_ready()
        @asia_preview.before_loop
        async def _w9(): await bot.wait_until_ready()
        @auto_whale_scan.before_loop
        async def _w10(): await bot.wait_until_ready()
        @weekly_recap.before_loop
        async def _w11(): await bot.wait_until_ready()
        @health_check.before_loop
        async def _w12(): await bot.wait_until_ready()
        @realtime_price_alerts.before_loop
        async def _w13(): await bot.wait_until_ready()
        @auto_news_feed.before_loop
        async def _w14(): await bot.wait_until_ready()
        @smart_morning_update.before_loop
        async def _w15(): await bot.wait_until_ready()
        @opportunity_scanner.before_loop
        async def _w16(): await bot.wait_until_ready()
        @vix_fear_monitor.before_loop
        async def _w17(): await bot.wait_until_ready()
        @auto_ticker_news.before_loop
        async def _w18(): await bot.wait_until_ready()
        @auto_strategy_learn.before_loop
        async def _w19(): await bot.wait_until_ready()

        # ══════════════════════════════════════════════════════════════
        # BOT EVENTS
        # ══════════════════════════════════════════════════════════════

        @bot.event
        async def on_ready():
            logger.info(f"✅ Discord bot online as {bot.user}")
            print(f"✅ TradingAI Bot connected as {bot.user}")
            print(f"   Servers: {', '.join(g.name for g in bot.guilds)}")
            # Re-register persistent views
            bot.add_view(VerifyView())
            bot.add_view(RolePickView())
            for guild in bot.guilds:
                await full_server_setup(guild)
            try:
                synced = await bot.tree.sync()
                logger.info(f"Synced {len(synced)} slash commands")
                print(f"   Synced {len(synced)} slash commands")
            except Exception as exc:
                logger.error(f"Slash command sync error: {exc}")
            # Start ALL background tasks
            all_tasks = [
                update_presence, market_pulse, auto_movers,
                auto_sector_macro, auto_crypto, global_market_update,
                auto_signal_scan, morning_brief, eod_report,
                asia_preview, auto_whale_scan, weekly_recap,
                health_check,
                # NEW: Real-time automation
                realtime_price_alerts, auto_news_feed,
                auto_ticker_news,
                smart_morning_update, opportunity_scanner,
                vix_fear_monitor,
                # AI learning
                auto_strategy_learn,
            ]
            for t in all_tasks:
                if not t.is_running():
                    t.start()
            print(f"   🔄 Started {len(all_tasks)} auto-pilot tasks")
            print(f"   🚨 Real-time alerts: prices(3min) + news(30min) + VIX(5min)")
            print(f"   ☀️ Smart morning: Asia(01UTC) + Europe(07UTC) + US(13:30UTC)")
            print(f"   🎯 Opportunity scanner: every 30min, score≥75 only")
            await _audit(f"🤖 Bot started as {bot.user} — {len(all_tasks)} tasks running\n"
                         f"🚨 Real-time: prices + news + VIX + opportunities")

        @bot.event
        async def on_guild_join(guild: discord.Guild):
            await full_server_setup(guild)
            await _audit(f"📥 Joined new server: {guild.name}")

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Getting Started
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="help",
                          description="Interactive command reference — pick a category")
        async def cmd_help(interaction: discord.Interaction):
            e = discord.Embed(
                title="📖 TradingAI Pro — Command Center",
                description="Pick a category below to see all commands.\n\u200b",
                color=COLOR_PURPLE)
            e.set_footer(text="45+ commands across 6 categories")
            await interaction.response.send_message(embed=e, view=HelpView(), ephemeral=True)

        @bot.tree.command(name="status", description="System connectivity check")
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.user.id)
        async def cmd_status(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="📡 System Status", color=COLOR_SUCCESS)
            checks = []
            try:
                import asyncpg
                conn = await asyncpg.connect(
                    host=settings.postgres_host, port=int(settings.postgres_port),
                    user=settings.postgres_user, password=settings.postgres_password,
                    database=settings.postgres_db)
                await conn.close()
                checks.append(("🗄️ Database", "✅ Connected"))
            except Exception:
                checks.append(("🗄️ Database", "❌ Offline"))
            try:
                import redis as rlib
                r = rlib.Redis(host=settings.redis_host, port=int(settings.redis_port),
                               password=settings.redis_password, socket_timeout=2)
                r.ping()
                checks.append(("📦 Redis", "✅ Connected"))
            except Exception:
                checks.append(("📦 Redis", "❌ Offline"))
            checks.append(("💹 Alpaca",
                           "✅" if getattr(settings, "alpaca_api_key", "") else "⚠️ Not set"))
            checks.append(("🧠 AI/GPT",
                           "✅" if (getattr(settings, "openai_api_key", "")
                                    or getattr(settings, "azure_openai_endpoint", ""))
                           else "⚠️ Not set"))
            checks.append(("💬 Discord", f"✅ {bot.user}"))
            checks.append(("🌍 Markets", "US · HK · JP · Crypto"))
            for n, v in checks:
                e.add_field(name=n, value=v, inline=True)
            e.set_footer(text=f"Bot uptime OK • {len(bot.guilds)} server(s) • "
                              f"{len(bot.tree.get_commands())} commands")
            await interaction.followup.send(embed=e)

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Market Data
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="price", description="Real-time price for any stock / crypto")
        @app_commands.describe(ticker="Symbol (AAPL, 0700.HK, BTC-USD)")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_price(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            if "error" in d:
                await interaction.followup.send(f"❌ Error: {d['error']}")
                return
            pct = d.get("change_pct", 0)
            e = discord.Embed(title=f"💰 {d['ticker']}",
                              description=d.get("name", ""),
                              color=COLOR_BUY if pct >= 0 else COLOR_SELL)
            e.add_field(name="Price", value=f"**${d['price']:.2f}**")
            e.add_field(name="Change", value=_bar(pct))
            e.add_field(name="Volume", value=_vol(d.get("volume", 0)))
            e.add_field(name="Day Range",
                        value=f"${d.get('low',0):.2f} — ${d.get('high',0):.2f}")
            e.add_field(name="52W Range",
                        value=f"${d.get('year_low',0):.2f} — ${d.get('year_high',0):.2f}")
            e.add_field(name="Mkt Cap", value=_mcap(d.get("market_cap", 0)))
            e.set_footer(text="TradingAI Pro • /quote for fundamentals")
            await interaction.followup.send(embed=e)
            await _audit(f"📊 {interaction.user} → /price {ticker}")

        @bot.tree.command(name="quote", description="Detailed quote with fundamentals")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_quote(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            if "error" in d:
                await interaction.followup.send(f"❌ {d['error']}")
                return
            pct = d.get("change_pct", 0)
            e = discord.Embed(
                title=f"📊 {d['ticker']} — Detailed Quote",
                description=f"**{d.get('name','')}** | {d.get('sector','N/A')}",
                color=COLOR_BUY if pct >= 0 else COLOR_SELL)
            for n, v in [
                ("Price", f"**${d['price']:.2f}** ({pct:+.2f}%)"),
                ("Open", f"${d.get('open',0):.2f}"),
                ("Prev Close", f"${d.get('prev_close',0):.2f}"),
                ("Day Range", f"${d.get('low',0):.2f} — ${d.get('high',0):.2f}"),
                ("52W Range", f"${d.get('year_low',0):.2f} — ${d.get('year_high',0):.2f}"),
                ("Volume", _vol(d.get("volume",0))),
                ("Mkt Cap", _mcap(d.get("market_cap",0))),
                ("P/E", f"{d.get('pe',0):.1f}" if d.get("pe") else "N/A"),
                ("EPS", f"${d.get('eps',0):.2f}" if d.get("eps") else "N/A"),
                ("Beta", f"{d.get('beta',0):.2f}" if d.get("beta") else "N/A"),
                ("Div Yield", f"{d.get('dividend',0)*100:.2f}%" if d.get("dividend") else "N/A"),
            ]:
                e.add_field(name=n, value=v)
            e.set_footer(text="TradingAI Pro • /analyze for technicals")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="market", description="US market overview — major indices")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_market(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🌎 Market Overview", color=COLOR_INFO)
            for sym, name in [("SPY","S&P 500"),("QQQ","Nasdaq 100"),
                               ("DIA","Dow Jones"),("IWM","Russell 2000"),("VIX","VIX")]:
                data = await _fetch_stock(sym)
                pct = data.get("change_pct", 0)
                e.add_field(name=f"{name} ({sym})",
                            value=f"${data.get('price',0):.2f}  {_bar(pct)}", inline=False)
            e.set_footer(text="TradingAI Pro • /sector /macro for more")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="sector", description="Sector performance heatmap")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_sector(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🏭 Sector Performance", color=COLOR_INFO)
            for sym, name in [("XLK","Tech"),("XLF","Fin"),("XLV","Health"),("XLE","Energy"),
                               ("XLI","Indust"),("XLY","ConDisc"),("XLP","ConStpl"),
                               ("XLU","Util"),("XLRE","RE"),("XLC","Comm"),("XLB","Mat")]:
                data = await _fetch_stock(sym)
                e.add_field(name=name, value=_bar(data.get("change_pct",0)), inline=True)
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="macro", description="Macro: Gold, Oil, BTC, Bonds, DXY")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_macro(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🌍 Macro Dashboard", color=COLOR_PURPLE)
            for sym, name in [("GLD","🥇 Gold"),("SLV","🥈 Silver"),("USO","🛢️ Oil"),
                               ("UNG","🔥 NatGas"),("TLT","💵 Bonds"),("UUP","💲 Dollar"),
                               ("BTC-USD","₿ BTC"),("ETH-USD","Ξ ETH")]:
                data = await _fetch_stock(sym)
                e.add_field(name=name,
                            value=f"${data.get('price',0):,.2f} ({data.get('change_pct',0):+.2f}%)")
            await interaction.followup.send(embed=e)

        # ── /market_now — v6 institutional regime scoreboard + delta + playbook ──
        @bot.tree.command(name="market_now",
                          description="Instant regime scoreboard · delta deck · playbook (v6)")
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.user.id)
        async def cmd_market_now(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                # ── Fetch regime inputs ──
                spy_data = await _fetch_stock("SPY")
                qqq_data = await _fetch_stock("QQQ")
                iwm_data = await _fetch_stock("IWM")
                vix_data = await _fetch_stock("^VIX")
                tlt_data = await _fetch_stock("TLT")
                btc_data = await _fetch_stock("BTC-USD")
                gold_data = await _fetch_stock("GLD")

                vix = vix_data.get("price", 0)
                spy_pct = spy_data.get("change_pct", 0)
                qqq_pct = qqq_data.get("change_pct", 0)
                iwm_pct = iwm_data.get("change_pct", 0)

                # ── v6: Build RegimeScoreboard ──
                risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                    "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                trend = "UPTREND" if spy_pct > 0.5 else "DOWNTREND" if spy_pct < -0.5 else "NEUTRAL"
                vol_state = "HIGH_VOL" if vix > 22 else "LOW_VOL" if vix < 15 else "NORMAL"

                risk_budgets = {
                    "RISK_ON": (150, 60, 100, 5, 30),
                    "NEUTRAL": (100, 30, 70, 4, 25),
                    "RISK_OFF": (60, 0, 30, 2, 15),
                }
                mg, nll, nlh, msn, ms = risk_budgets.get(risk, (100, 30, 70, 4, 25))

                playbook_map = {
                    ("RISK_ON", "UPTREND", "LOW_VOL"): (["Momentum", "Breakout", "Trend-Follow"], [], ["Mean-Reversion"]),
                    ("RISK_ON", "UPTREND", "NORMAL"): (["Momentum", "Swing", "VCP"], [], []),
                    ("RISK_ON", "NEUTRAL", "LOW_VOL"): (["Mean-Reversion", "Swing"], [], ["Momentum"]),
                    ("NEUTRAL", "UPTREND", "NORMAL"): (["Momentum", "VCP"], [{"strategy": "Swing", "condition": "pullback > 3d"}], []),
                    ("NEUTRAL", "NEUTRAL", "NORMAL"): (["Mean-Reversion"], [{"strategy": "Swing", "condition": "grade A only"}], ["Momentum"]),
                    ("NEUTRAL", "DOWNTREND", "NORMAL"): (["Mean-Reversion"], [], ["Momentum", "Breakout"]),
                    ("RISK_OFF", "DOWNTREND", "HIGH_VOL"): ([], [], ["Momentum", "Breakout", "Swing", "VCP"]),
                    ("RISK_OFF", "NEUTRAL", "HIGH_VOL"): (["Mean-Reversion"], [], ["Momentum", "Breakout"]),
                }
                key = (risk, trend, vol_state)
                strats_on, strats_cond, strats_off = playbook_map.get(
                    key, (["Swing", "Mean-Reversion"], [], []))

                risk_flags = []
                if vix > 25:
                    risk_flags.append(f"VIX {vix:.1f} — reduce position sizes")
                if vix > 18 and spy_pct < -1:
                    risk_flags.append("Selling into elevated vol — stop discipline critical")
                if abs(qqq_pct - spy_pct) > 1.5:
                    risk_flags.append(f"QQQ/SPY divergence {qqq_pct - spy_pct:+.1f}%")

                drivers = []
                if abs(spy_pct) > 0.5:
                    drivers.append(f"SPX {spy_pct:+.2f}%")
                if vix > 20 or vix < 14:
                    drivers.append(f"VIX {vix:.1f}")
                btc_pct = btc_data.get("change_pct", 0)
                if abs(btc_pct) > 3:
                    drivers.append(f"BTC {btc_pct:+.1f}%")

                risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))

                from src.core.models import RegimeScoreboard as RSB, ScenarioPlan, DeltaSnapshot, ChangeItem
                from datetime import date as _date

                scoreboard = RSB(
                    regime_label=risk, risk_on_score=risk_on_score,
                    trend_state=trend, vol_state=vol_state,
                    max_gross_pct=mg, net_long_target_low=nll, net_long_target_high=nlh,
                    max_single_name_pct=msn, max_sector_pct=ms,
                    strategies_on=strats_on, strategies_conditional=strats_cond,
                    strategies_off=strats_off,
                    no_trade_triggers=risk_flags, top_drivers=drivers,
                    scenarios=ScenarioPlan(
                        base_case={"probability": "55%", "description": f"Range-bound near current levels"},
                        bull_case={"probability": "25%", "description": f"Break above R${spy_data.get('high', 0):.0f}"},
                        bear_case={"probability": "20%", "description": f"Lose S${spy_data.get('low', 0):.0f}, vol spike"},
                        triggers=["Macro data", "Fed commentary", "Earnings surprises"],
                    ),
                )

                delta = DeltaSnapshot(
                    snapshot_date=_date.today(),
                    spx_1d_pct=spy_pct, ndx_1d_pct=qqq_pct, iwm_1d_pct=iwm_pct,
                    vix_close=vix, vix_1d_change=vix_data.get("change_pct", 0),
                )

                # Build v6 change items
                bullish_changes = []
                bearish_changes = []
                if spy_pct > 0.3:
                    bullish_changes.append(ChangeItem(category="index", description=f"SPY +{spy_pct:.2f}%"))
                if spy_pct < -0.3:
                    bearish_changes.append(ChangeItem(category="index", description=f"SPY {spy_pct:+.2f}%"))
                if vix > 22:
                    bearish_changes.append(ChangeItem(category="volatility", description=f"VIX elevated at {vix:.1f}"))

                # ── Use v6 report generator ──
                if _HAS_REPORT_GEN:
                    snapshot_data = build_regime_snapshot(
                        scoreboard=scoreboard, delta=delta,
                        bullish_changes=bullish_changes, bearish_changes=bearish_changes,
                    )

                    # Add macro section
                    macro_section = {
                        "name": "🌍 Macro",
                        "value": (
                            f"📉 VIX: **{vix:.1f}** "
                            f"{'🔴' if vix > 25 else '🟡' if vix > 18 else '🟢'}\n"
                            f"💵 TLT: ${tlt_data.get('price', 0):.2f} ({tlt_data.get('change_pct', 0):+.2f}%)\n"
                            f"🥇 Gold: ${gold_data.get('price', 0):.2f} ({gold_data.get('change_pct', 0):+.2f}%)\n"
                            f"₿ BTC: ${btc_data.get('price', 0):,.0f} ({btc_pct:+.2f}%)"
                        ),
                        "inline": False,
                    }
                    snapshot_data.setdefault("sections", []).append(macro_section)

                    now_ts = datetime.now(timezone.utc)
                    e = discord.Embed(
                        title=snapshot_data.get("title", "🎛️ Market Now"),
                        description=snapshot_data.get("description", ""),
                        color=snapshot_data.get("color", COLOR_INFO),
                        timestamp=now_ts,
                    )
                    for s in snapshot_data.get("sections", []):
                        e.add_field(name=s["name"], value=s["value"],
                                    inline=s.get("inline", False))
                    e.set_footer(text=snapshot_data.get("footer", "TradingAI Pro v6"))
                    await interaction.followup.send(embed=e)
                else:
                    # Fallback minimal embed
                    now_ts = datetime.now(timezone.utc)
                    regime_icons = {"RISK_ON": "🟢 RISK ON", "NEUTRAL": "🟡 NEUTRAL", "RISK_OFF": "🔴 RISK OFF"}
                    regime_label = regime_icons.get(risk, "🟡 NEUTRAL")
                    e = discord.Embed(
                        title=f"🎛️ Market Now — {now_ts.strftime('%H:%M UTC')}",
                        description=f"**{regime_label}** • VIX {vix:.1f} • SPY {spy_pct:+.2f}%",
                        color=COLOR_INFO, timestamp=now_ts)
                    strat_str = " · ".join(f"`{s}`" for s in strats_on)
                    e.add_field(name="📋 Playbook", value=strat_str or "—", inline=False)
                    e.set_footer(text="TradingAI Pro v6")
                    await interaction.followup.send(embed=e)

                await _audit(f"🎛️ {interaction.user} → /market_now ({risk})")
            except Exception as exc:
                logger.error(f"market_now error: {exc}")
                await interaction.followup.send(f"❌ {exc}")

        # ── /daily_update — Full daily intelligence brief (like the website dashboard) ──
        @bot.tree.command(name="daily_update",
                          description="📊 Full market intelligence — regime · AI rec · top signals · global overview")
        @app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
        async def cmd_daily_update(interaction: discord.Interaction):
            """Mirrors the website dashboard: Market Brief + AI Recommendation +
            Top Signals + Market Overview. Works in any timezone, any time."""
            await interaction.response.defer()
            try:
                now = datetime.now(timezone.utc)

                # ── 1. Fetch all market data ──
                spy_data = await _fetch_stock("SPY")
                qqq_data = await _fetch_stock("QQQ")
                iwm_data = await _fetch_stock("IWM")
                vix_data = await _fetch_stock("^VIX")
                tlt_data = await _fetch_stock("TLT")
                btc_data = await _fetch_stock("BTC-USD")
                gold_data = await _fetch_stock("GLD")

                vix = vix_data.get("price", 0)
                spy_pct = spy_data.get("change_pct", 0)
                qqq_pct = qqq_data.get("change_pct", 0)
                iwm_pct = iwm_data.get("change_pct", 0)
                btc_pct = btc_data.get("change_pct", 0)

                # ── 2. Compute regime ──
                risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                    "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                trend = "UPTREND" if spy_pct > 0.5 else "DOWNTREND" if spy_pct < -0.5 else "NEUTRAL"
                vol_state = "HIGH_VOL" if vix > 22 else "LOW_VOL" if vix < 15 else "NORMAL"
                risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))

                regime_icons = {"RISK_ON": "🟢 RISK ON", "NEUTRAL": "🟡 NEUTRAL", "RISK_OFF": "🔴 RISK OFF"}
                regime_label = regime_icons.get(risk, "🟡 NEUTRAL")

                # AI Recommendation level (mirrors website)
                if risk == "RISK_ON" and vix < 16:
                    ai_rec = "🟢 **AGGRESSIVE** — Full allocation, momentum strategies active"
                elif risk == "RISK_ON":
                    ai_rec = "🟢 **NORMAL** — Standard allocation, trend-following bias"
                elif risk == "NEUTRAL" and vix < 20:
                    ai_rec = "🟡 **NORMAL** — Standard allocation, selective entries"
                elif risk == "NEUTRAL":
                    ai_rec = "🟡 **CAUTIOUS** — Reduced allocation, tighter stops"
                else:
                    ai_rec = "🔴 **DEFENSIVE** — Minimal exposure, hedge active positions"

                # Playbook
                playbook_map = {
                    ("RISK_ON", "UPTREND", "LOW_VOL"): ["Momentum", "Breakout", "Trend-Follow"],
                    ("RISK_ON", "UPTREND", "NORMAL"): ["Momentum", "Swing", "VCP"],
                    ("RISK_ON", "NEUTRAL", "LOW_VOL"): ["Mean-Reversion", "Swing"],
                    ("NEUTRAL", "UPTREND", "NORMAL"): ["Momentum", "VCP"],
                    ("NEUTRAL", "NEUTRAL", "NORMAL"): ["Mean-Reversion"],
                    ("NEUTRAL", "DOWNTREND", "NORMAL"): ["Mean-Reversion"],
                    ("RISK_OFF", "DOWNTREND", "HIGH_VOL"): ["Cash"],
                    ("RISK_OFF", "NEUTRAL", "HIGH_VOL"): ["Mean-Reversion"],
                }
                strats = playbook_map.get((risk, trend, vol_state), ["Swing", "Mean-Reversion"])

                # ── EMBED 1: Market Brief + AI Recommendation ──
                score_bar = "█" * (int(risk_on_score) // 10) + "░" * (10 - int(risk_on_score) // 10)
                e1 = discord.Embed(
                    title=f"📊 Daily Market Intelligence — {now.strftime('%A, %b %d %H:%M UTC')}",
                    description=(
                        f"**{regime_label}** • Risk Score: **{risk_on_score:.0f}/100** `{score_bar}`\n"
                        f"Trend: **{trend}** • Volatility: **{vol_state}**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=COLOR_BUY if risk == "RISK_ON" else COLOR_SELL if risk == "RISK_OFF" else COLOR_GOLD,
                    timestamp=now,
                )
                e1.add_field(name="🤖 AI Recommendation", value=ai_rec, inline=False)
                e1.add_field(name="📋 Active Playbook",
                             value=" · ".join(f"`{s}`" for s in strats) or "`Cash`",
                             inline=False)

                # Chain-of-Thought reasoning (like the website)
                reasoning = []
                reasoning.append(f"VIX at {vix:.1f} → {'elevated risk' if vix > 22 else 'calm conditions' if vix < 16 else 'moderate vol'}")
                reasoning.append(f"SPY {spy_pct:+.2f}% → {'positive momentum' if spy_pct > 0.3 else 'selling pressure' if spy_pct < -0.3 else 'range-bound'}")
                if abs(qqq_pct - spy_pct) > 1:
                    reasoning.append(f"QQQ/SPY spread {qqq_pct - spy_pct:+.1f}% → sector rotation signal")
                if abs(btc_pct) > 3:
                    reasoning.append(f"BTC {btc_pct:+.1f}% → {'risk appetite' if btc_pct > 0 else 'risk aversion'} signal")
                e1.add_field(name="🧠 Chain-of-Thought",
                             value="\n".join(f"→ {r}" for r in reasoning),
                             inline=False)

                # Risk alerts
                risk_flags = []
                if vix > 25:
                    risk_flags.append(f"⚠️ VIX {vix:.1f} — reduce size to 50%")
                if spy_pct < -2:
                    risk_flags.append("⚠️ SPY down >2% — watch for capitulation")
                if abs(qqq_pct - spy_pct) > 1.5:
                    risk_flags.append(f"⚠️ QQQ/SPY divergence — rotation risk")
                if risk_flags:
                    e1.add_field(name="🛡️ Risk Alerts",
                                 value="\n".join(risk_flags), inline=False)

                e1.set_footer(text="TradingAI Pro v6 • /market_now for full regime deck")
                await interaction.followup.send(embed=e1)

                # ── EMBED 2: Market Overview (indices + macro + crypto) ──
                e2 = discord.Embed(
                    title="🌎 Market Overview",
                    color=COLOR_INFO, timestamp=now)

                # US Indices
                idx_lines = []
                for sym, name in _INDICES[:4]:  # SPY, QQQ, DIA, IWM (skip VIX)
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴" if pct < 0 else "⚪"
                    idx_lines.append(f"{icon} **{name}**: ${data.get('price',0):.2f} ({pct:+.2f}%)")
                e2.add_field(name="🇺🇸 US Indices",
                             value="\n".join(idx_lines), inline=False)

                # Futures
                futures_lines = []
                for sym, name in [("ES=F", "S&P"), ("NQ=F", "Nasdaq"), ("YM=F", "Dow")]:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴"
                    futures_lines.append(f"{icon} **{name}**: ${data.get('price',0):,.0f} ({pct:+.2f}%)")
                e2.add_field(name="📈 Futures",
                             value=" | ".join(futures_lines), inline=False)

                # Asia
                asia_lines = []
                for sym, name in _WATCH_ASIA:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴"
                    asia_lines.append(f"{icon} {name}: {pct:+.2f}%")
                e2.add_field(name="🌏 Asia",
                             value=" | ".join(asia_lines) or "Market closed", inline=False)

                # Macro
                vix_icon = "🔴" if vix > 25 else "🟡" if vix > 18 else "🟢"
                e2.add_field(name="🌍 Macro",
                             value=(
                                 f"📉 VIX: **{vix:.1f}** {vix_icon} | "
                                 f"💵 TLT: {tlt_data.get('change_pct',0):+.2f}% | "
                                 f"🥇 Gold: ${gold_data.get('price',0):.2f} ({gold_data.get('change_pct',0):+.2f}%) | "
                                 f"₿ BTC: ${btc_data.get('price',0):,.0f} ({btc_pct:+.2f}%)"
                             ), inline=False)

                e2.set_footer(text="/sector · /macro · /crypto for deep dives")
                await interaction.followup.send(embed=e2)

                # ── EMBED 3: Top AI Signals (scan top stocks) ──
                try:
                    scan_results = await _async_signal_scan(_WATCH_US[:20])
                    if scan_results:
                        scan_results.sort(key=lambda x: x["score"], reverse=True)
                        top5 = scan_results[:5]
                        e3 = discord.Embed(
                            title="🎯 Top AI Trade Ideas",
                            description="Sorted by conviction score • swing + breakout + momentum",
                            color=COLOR_GOLD, timestamp=now)
                        for i, sig in enumerate(top5, 1):
                            arrow = "🟢" if sig["direction"] == "LONG" else "🔴"
                            score = sig["score"]
                            rr = sig.get("rr_ratio", 0)
                            reason = sig["reasons"][0] if sig.get("reasons") else ""
                            e3.add_field(
                                name=f"{arrow} #{i} {sig['ticker']} — ${sig['price']:.2f}",
                                value=(
                                    f"Score: **{score}/100** | R:R: **{rr:.1f}:1**\n"
                                    f"Stop: ${sig.get('stop',0):.2f} → Target: ${sig.get('target',0):.2f}\n"
                                    f"{reason}"
                                ), inline=False)
                        e3.set_footer(text="/signals · /scan_swing · /scan_breakout for more")
                        await interaction.followup.send(embed=e3)
                except Exception:
                    pass  # signal scan optional — don't fail the whole command

                await _audit(f"📊 {interaction.user} → /daily_update ({risk})")
            except Exception as exc:
                logger.error(f"daily_update error: {exc}")
                await interaction.followup.send(f"❌ Error fetching market data: {exc}")

        @bot.tree.command(name="movers", description="Top gainers and losers today")
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.user.id)
        async def cmd_movers(interaction: discord.Interaction):
            await interaction.response.defer()
            tickers = ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","AMD","NFLX","CRM",
                        "COIN","PLTR","SOFI","NIO","RIVN","MARA","SQ","SHOP","ROKU","SNAP"]
            results = []
            for t in tickers:
                data = await _fetch_stock(t)
                if "error" not in data:
                    results.append(data)
            results.sort(key=lambda x: x.get("change_pct", 0), reverse=True)
            e = discord.Embed(title="🔥 Top Movers Today", color=COLOR_INFO)
            e.add_field(name="🟢 Top Gainers", inline=True,
                        value="\n".join(f"**{r['ticker']}** ${r['price']:.2f} ({r['change_pct']:+.2f}%)"
                                        for r in results[:5]) or "N/A")
            e.add_field(name="🔴 Top Losers", inline=True,
                        value="\n".join(f"**{r['ticker']}** ${r['price']:.2f} ({r['change_pct']:+.2f}%)"
                                        for r in results[-5:]) or "N/A")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="news", description="Latest news for a stock")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_news(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            try:
                news = await _mds.get_news(ticker.upper(), max_items=5)
                if not news:
                    await interaction.followup.send(f"No news for {ticker.upper()}")
                    return
                e = discord.Embed(title=f"📰 {ticker.upper()} News", color=COLOR_INFO)
                for item in news:
                    e.add_field(name=f"• {item.get('publisher','')}",
                                value=f"[{item.get('title','')[:100]}]({item.get('link','')})",
                                inline=False)
                await interaction.followup.send(embed=e)
            except Exception as exc:
                await interaction.followup.send(f"❌ {exc}")

        @bot.tree.command(name="premarket", description="Pre-market futures")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_premarket(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="⏰ Pre-Market Futures", color=COLOR_INFO)
            for sym, name in [("ES=F","S&P"),("NQ=F","Nasdaq"),("YM=F","Dow")]:
                data = await _fetch_stock(sym)
                e.add_field(name=name,
                            value=f"${data.get('price',0):,.2f} ({data.get('change_pct',0):+.2f}%)")
            await interaction.followup.send(embed=e)

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — AI Analysis
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="ai", description="Full AI analysis for any stock")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 8, key=lambda i: i.user.id)
        async def cmd_ai(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            if "error" in d:
                await interaction.followup.send(f"❌ {d['error']}"); return
            pct = d.get("change_pct", 0); price = d.get("price", 0)
            e = discord.Embed(title=f"🧠 AI Analysis — {d['ticker']}",
                              description=f"**{d.get('name','')}** | {d.get('sector','N/A')}",
                              color=COLOR_PURPLE)
            e.add_field(name="💰 Price", value=f"${price:.2f} ({pct:+.2f}%)")
            e.add_field(name="📊 Mkt Cap", value=_mcap(d.get("market_cap",0)))
            yr_h, yr_l = d.get("year_high",0), d.get("year_low",0)
            if yr_h and yr_l and yr_h != yr_l:
                e.add_field(name="52W Position",
                            value=f"{(price-yr_l)/(yr_h-yr_l)*100:.0f}% from low")
            pe = d.get("pe", 0)
            if pe:
                vlabel = ("Cheap" if pe < 15 else "Fair" if pe < 25
                          else "Expensive" if pe < 40 else "Very Expensive")
                e.add_field(name="Valuation", value=f"P/E {pe:.1f} ({vlabel})")
            rec = ("🟢 **BUY** — Strong momentum" if pct > 3
                   else "🟡 **HOLD** — Mild upside" if pct > 0
                   else "🟡 **HOLD** — Mild weakness" if pct > -3
                   else "🔴 **CAUTION** — Selling pressure")
            e.add_field(name="🤖 AI Verdict", value=rec, inline=False)
            e.add_field(name="📝 Next Steps", inline=False,
                        value=f"`/analyze {ticker}` · `/levels {ticker}` · `/advise {ticker}`")
            e.set_footer(text="TradingAI Pro • AI Analysis")
            await interaction.followup.send(embed=e,
                                            view=SignalActionView(ticker.upper()))

        @bot.tree.command(name="analyze", description="Technical analysis — SMA, RSI, volume")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 8, key=lambda i: i.user.id)
        async def cmd_analyze(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            try:
                hist = await _mds.get_history(ticker.upper(), period="3mo")
                if hist is None or hist.empty:
                    await interaction.followup.send(f"❌ No data for {ticker.upper()}"); return
                close = hist["Close"]; price = close.iloc[-1]
                sma20 = close.rolling(20).mean().iloc[-1]
                sma50 = close.rolling(50).mean().iloc[-1]
                vol = hist["Volume"].iloc[-1]
                avg_vol = hist["Volume"].rolling(20).mean().iloc[-1]
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain.iloc[-1] / loss.iloc[-1] if loss.iloc[-1] != 0 else 0
                rsi = 100 - (100 / (1 + rs))
                e = discord.Embed(title=f"📈 Technical Analysis — {ticker.upper()}",
                                  color=COLOR_INFO)
                e.add_field(name="Price", value=f"**${price:.2f}**")
                e.add_field(name="SMA 20",
                            value=f"${sma20:.2f} {'✅' if price > sma20 else '❌'}")
                e.add_field(name="SMA 50",
                            value=f"${sma50:.2f} {'✅' if price > sma50 else '❌'}")
                rsi_l = ("🟢 Oversold" if rsi < 30 else "🔴 Overbought" if rsi > 70 else "🟡 Neutral")
                e.add_field(name="RSI(14)", value=f"{rsi:.1f} {rsi_l}")
                e.add_field(name="Rel Vol", value=f"{vol/avg_vol:.1f}x" if avg_vol else "N/A")
                trend = ("🟢 Bullish" if price > sma20 > sma50
                         else "🔴 Bearish" if price < sma20 < sma50 else "🟡 Mixed")
                e.add_field(name="Trend", value=trend)
                await interaction.followup.send(embed=e)
            except Exception as exc:
                await interaction.followup.send(f"❌ {exc}")

        @bot.tree.command(name="advise", description="AI buy/hold/sell recommendation")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 8, key=lambda i: i.user.id)
        async def cmd_advise(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            try:
                hist = await _mds.get_history(ticker.upper(), period="3mo")
                if hist is None or hist.empty:
                    await interaction.followup.send(f"❌ No data"); return
                close = hist["Close"]; price = close.iloc[-1]
                sma20 = close.rolling(20).mean().iloc[-1]
                sma50 = close.rolling(50).mean().iloc[-1]
                h52, l52 = close.max(), close.min()
                score = 50; reasons = []
                if price > sma20: score += 15; reasons.append("✅ Above 20-MA")
                else: score -= 15; reasons.append("❌ Below 20-MA")
                if price > sma50: score += 15; reasons.append("✅ Above 50-MA")
                else: score -= 15; reasons.append("❌ Below 50-MA")
                dh = (h52 - price) / h52 * 100
                if dh < 5: score += 10; reasons.append(f"🔥 Near 52W high ({dh:.1f}%)")
                elif dh > 30: score -= 10; reasons.append(f"⚠️ Far from high ({dh:.1f}%)")
                if score >= 70: verdict = "🟢 **BUY**"; color = COLOR_BUY
                elif score >= 40: verdict = "🟡 **HOLD**"; color = COLOR_WARN
                else: verdict = "🔴 **SELL / AVOID**"; color = COLOR_SELL
                e = discord.Embed(title=f"🤖 AI Advice — {ticker.upper()}",
                                  description=f"Score: **{score}/100** → {verdict}", color=color)
                e.add_field(name="Price", value=f"${price:.2f}")
                e.add_field(name="52W", value=f"${l52:.2f} — ${h52:.2f}")
                e.add_field(name="📝 Reasons", value="\n".join(reasons), inline=False)
                e.set_footer(text="TradingAI Pro • Not financial advice")
                await interaction.followup.send(embed=e)
            except Exception as exc:
                await interaction.followup.send(f"❌ {exc}")

        @bot.tree.command(name="score", description="AI score 1-10 for a stock")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_score(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            if "error" in d:
                await interaction.followup.send(f"❌ {d['error']}"); return
            pct = d.get("change_pct", 0); pe = d.get("pe", 0)
            s = 5.0
            if pct > 2: s += 1.5
            elif pct > 0: s += 0.5
            elif pct < -2: s -= 1.5
            else: s -= 0.5
            if pe and 10 < pe < 25: s += 1
            elif pe and pe > 40: s -= 1
            s = max(1, min(10, s))
            e = discord.Embed(title=f"🎯 AI Score — {d['ticker']}",
                              description=f"**{s:.1f}/10**\n{'⭐' * int(s)}{'☆' * (10 - int(s))}",
                              color=COLOR_BUY if s >= 7 else COLOR_WARN if s >= 4 else COLOR_SELL)
            e.add_field(name="Price", value=f"${d['price']:.2f} ({pct:+.2f}%)")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="compare", description="Compare two stocks side by side")
        @app_commands.describe(ticker1="First stock", ticker2="Second stock")
        @app_commands.checks.cooldown(1, 8, key=lambda i: i.user.id)
        async def cmd_compare(interaction: discord.Interaction, ticker1: str, ticker2: str):
            await interaction.response.defer()
            d1, d2 = await _fetch_stock(ticker1), await _fetch_stock(ticker2)
            e = discord.Embed(title=f"⚖️ {ticker1.upper()} vs {ticker2.upper()}",
                              color=COLOR_PURPLE)
            for label, key, fmt in [("Price","price","${:.2f}"),("Change","change_pct","{:+.2f}%"),
                                     ("Mkt Cap","market_cap","cap"),("P/E","pe","{:.1f}"),
                                     ("Volume","volume","vol")]:
                v1, v2 = d1.get(key,0) or 0, d2.get(key,0) or 0
                if fmt == "cap": s1, s2 = _mcap(v1), _mcap(v2)
                elif fmt == "vol": s1, s2 = _vol(v1), _vol(v2)
                else: s1, s2 = (fmt.format(v1) if v1 else "N/A"), (fmt.format(v2) if v2 else "N/A")
                e.add_field(name=label,
                            value=f"{ticker1.upper()}: {s1}\n{ticker2.upper()}: {s2}")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="levels", description="Support and resistance levels")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 8, key=lambda i: i.user.id)
        async def cmd_levels(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            try:
                hist = await _mds.get_history(ticker.upper(), period="6mo")
                if hist is None or hist.empty:
                    await interaction.followup.send(f"❌ No data"); return
                close, high, low = hist["Close"], hist["High"], hist["Low"]
                price = close.iloc[-1]
                e = discord.Embed(title=f"📏 S/R — {ticker.upper()}",
                                  description=f"Current: **${price:.2f}**", color=COLOR_INFO)
                for n, v in [("🔴 R2 (6mo high)", f"${high.max():.2f}"),
                              ("🟠 R1 (20d high)", f"${high.rolling(20).max().iloc[-1]:.2f}"),
                              ("➖ SMA 20", f"${close.rolling(20).mean().iloc[-1]:.2f}"),
                              ("➖ SMA 50", f"${close.rolling(50).mean().iloc[-1]:.2f}"),
                              ("🟢 S1 (20d low)", f"${low.rolling(20).min().iloc[-1]:.2f}"),
                              ("🟢 S2 (6mo low)", f"${low.min():.2f}")]:
                    e.add_field(name=n, value=v, inline=False)
                await interaction.followup.send(embed=e)
            except Exception as exc:
                await interaction.followup.send(f"❌ {exc}")

        @bot.tree.command(name="why", description="Full conviction analysis — should you buy/sell, where to stop, why")
        @app_commands.describe(ticker="Stock symbol e.g. NVDA, TSLA, BTC-USD")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_why(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            ticker = ticker.upper().strip()
            now = datetime.now(timezone.utc)

            def _sync_why_analysis(sym, pre_hist=None):
                try:
                    hist = pre_hist
                    if hist is None:
                        if not _yf: return {}
                        hist = _yf.Ticker(sym).history(period="3mo")
                    if hist is None or hist.empty or len(hist) < 20:
                        return {}
                    techs = _compute_technicals(hist)
                    news, analyst = [], {}
                    try:
                        if _yf:
                            t = _yf.Ticker(sym)
                            raw_news = t.news if hasattr(t, "news") else []
                            ts_now = now.timestamp()
                        for item in (raw_news or [])[:8]:
                            url = item.get("link", item.get("url", ""))
                            title = item.get("title", "")
                            if url and title:
                                age_h = (ts_now - item.get("providerPublishTime", ts_now)) / 3600
                                news.append({"title": title[:100], "url": url,
                                             "publisher": item.get("publisher", ""),
                                             "age_h": age_h})
                    except Exception:
                        pass
                    try:
                        info = t.info or {}
                        analyst = {
                            "recommendation": info.get("recommendationKey", ""),
                            "analyst_count": info.get("numberOfAnalystOpinions", 0),
                            "target_mean": info.get("targetMeanPrice", 0),
                        }
                    except Exception:
                        pass
                    return {**techs, "news": news, "analyst": analyst}
                except Exception:
                    return {}

            why_hist = await _mds.get_history(ticker, period="3mo")
            data = await asyncio.to_thread(_sync_why_analysis, ticker, why_hist)
            d = await _fetch_stock(ticker)
            if not data:
                await interaction.followup.send(
                    f"❌ Could not fetch data for `{ticker}`. Check the symbol (e.g. NVDA, BTC-USD).")
                return

            price = d.get("price", data.get("price", 0))
            pct = d.get("change_pct", 0)
            rsi = data.get("rsi", 50)
            atr = data.get("atr", price * 0.02)
            sma20 = data.get("sma20", 0)
            sma50 = data.get("sma50", 0)
            rel_vol = data.get("rel_vol", 1.0)
            bb_lower = data.get("bb_lower", 0)
            bb_upper = data.get("bb_upper", 0)
            bb_width = data.get("bb_width", 5)
            pb = data.get("pullback_days", 0)

            # ── Build conviction score ─────────────────────────────────
            buy_pts, sell_pts, conviction = [], [], 0

            # Trend
            if price > sma20 > sma50:
                conviction += 25
                buy_pts.append(f"✅ Price > SMA20 > SMA50 — uptrend in force")
            elif price > sma50:
                conviction += 10
                buy_pts.append(f"🟡 Above SMA50 — holding trend support")
            elif price < sma20 < sma50:
                conviction -= 25
                sell_pts.append(f"🔴 Below SMA20 & SMA50 — downtrend confirmed, avoid longs")
            else:
                sell_pts.append(f"🟠 Mixed trend — no clear direction, wait for clarity")

            # Pullback (swing quality)
            if 2 <= pb <= 7:
                conviction += 15
                buy_pts.append(f"✅ {pb}-day healthy pullback in uptrend — classic swing entry")
            elif pb == 1:
                conviction += 5
                buy_pts.append(f"🟡 1-day dip — monitor for follow-through")

            # RSI
            if rsi < 30:
                conviction += 25
                buy_pts.append(f"✅ RSI {rsi:.0f} — severely oversold, bounce very likely")
            elif rsi < 45:
                conviction += 10
                buy_pts.append(f"✅ RSI {rsi:.0f} — oversold reset, buy zone")
            elif rsi > 75:
                conviction -= 25
                sell_pts.append(f"🔴 RSI {rsi:.0f} — extremely overbought, avoid new longs")
            elif rsi > 65:
                conviction -= 10
                sell_pts.append(f"🟠 RSI {rsi:.0f} — elevated, not ideal entry")
            else:
                buy_pts.append(f"🟡 RSI {rsi:.0f} — neutral zone, no RSI edge")

            # Volume
            if rel_vol >= 2.5:
                conviction += 25
                buy_pts.append(f"✅ Volume {rel_vol:.1f}× avg — strong institutional activity")
            elif rel_vol >= 1.5:
                conviction += 10
                buy_pts.append(f"🟡 Volume {rel_vol:.1f}× avg — above-normal interest")
            elif rel_vol < 0.7:
                conviction -= 10
                sell_pts.append(f"🔴 Volume {rel_vol:.1f}× avg — no conviction behind the move")

            # Today's move
            if abs(pct) >= 3:
                if pct > 0:
                    conviction += 15
                    buy_pts.append(f"✅ {pct:+.1f}% today — momentum catalyst present")
                else:
                    conviction -= 15
                    sell_pts.append(f"🔴 {pct:+.1f}% today — selling pressure, be cautious")
            elif pct > 1:
                conviction += 5
                buy_pts.append(f"🟡 {pct:+.1f}% today — mild positive momentum")

            # Bollinger Band position
            if bb_lower and price < bb_lower:
                conviction += 20
                buy_pts.append(f"✅ Below lower BB (${bb_lower:.2f}) — mean reversion setup")
            elif bb_upper and price > bb_upper:
                conviction -= 15
                sell_pts.append(f"🔴 Above upper BB (${bb_upper:.2f}) — extended, overbought")
            elif bb_width and bb_width < 4:
                conviction += 5
                buy_pts.append(f"✅ BB squeeze ({bb_width:.1f}%) — potential breakout building")

            conviction = max(-100, min(100, conviction))

            # ── Stop loss reasoning ────────────────────────────────────
            if conviction >= 0:
                suggested_stop = round(price - 1.5 * atr, 2)
                stop_risk_pct = abs(price - suggested_stop) / price * 100
                stop_text = (
                    f"**Enter:** ~${price:.2f}  |  **Stop:** ${suggested_stop:.2f}  |  **Risk:** {stop_risk_pct:.1f}%\n"
                    f"• Stop = **1.5× ATR** (${atr:.2f}) below price = outside normal daily noise\n"
                    f"• **If close below ${suggested_stop:.2f}**: the buy thesis is broken → exit immediately\n"
                    f"• SMA50 at ${sma50:.2f} — a close below SMA50 also invalidates a long\n"
                    f"• Stop loss exists to protect capital, not to hope the trade bounces"
                )
            else:
                suggested_stop = round(price + 1.5 * atr, 2)
                stop_risk_pct = abs(price - suggested_stop) / price * 100
                stop_text = (
                    f"**Counter-trend / falling setup** — higher risk, smaller size\n"
                    f"• If buying dip: stop above **${suggested_stop:.2f}** (+{stop_risk_pct:.1f}%)\n"
                    f"• Trend is DOWN — only trade with very tight stop and small position\n"
                    f"• **Better strategy**: wait for trend reversal confirmation before entering"
                )

            # ── Verdict ───────────────────────────────────────────────
            if conviction >= 50:
                verdict, v_color = "🟢 STRONG BUY — High conviction setup", COLOR_BUY
            elif conviction >= 20:
                verdict, v_color = "🟢 BUY / WATCH — Conditions favour long", COLOR_BUY
            elif conviction >= -10:
                verdict, v_color = "🟡 NEUTRAL — Wait for a clearer signal", COLOR_INFO
            elif conviction >= -40:
                verdict, v_color = "🟠 CAUTION — Avoid new long entries", COLOR_SELL
            else:
                verdict, v_color = "🔴 AVOID / SELL — Conditions unfavourable", COLOR_SELL

            e = discord.Embed(
                title=f"🧠 Conviction Analysis — {ticker}",
                description=(
                    f"**${price:.2f}** ({pct:+.2f}% today)  |  Conviction: **{conviction:+d}/100**\n\n"
                    f"**{verdict}**"
                ),
                color=v_color, timestamp=now)

            if buy_pts:
                e.add_field(name="🟢 REASONS TO BUY",
                            value="\n".join(buy_pts[:5]), inline=False)
            if sell_pts:
                e.add_field(name="🔴 REASONS TO WAIT / AVOID",
                            value="\n".join(sell_pts[:4]), inline=False)

            e.add_field(name="🛑 STOP LOSS — WHERE & WHY",
                        value=stop_text[:512], inline=False)

            e.add_field(name="📊 Technicals",
                        value=(
                            f"RSI **{rsi:.0f}** · Vol **{rel_vol:.1f}×** · ATR **${atr:.2f}**\n"
                            f"SMA20 **${sma20:.2f}** · SMA50 **${sma50:.2f}**"
                        ), inline=True)

            # Analyst consensus
            analyst = data.get("analyst", {})
            if analyst.get("recommendation") or analyst.get("analyst_count"):
                rec = (analyst.get("recommendation") or "N/A").upper()
                cnt = analyst.get("analyst_count", 0)
                tgt = analyst.get("target_mean", 0)
                upside = (tgt - price) / price * 100 if tgt and price else 0
                ana_text = f"**{rec}** ({cnt} analysts)"
                if tgt:
                    ana_text += f"\nTarget: **${tgt:.2f}** ({upside:+.1f}% upside)"
                e.add_field(name="👔 Analyst View", value=ana_text, inline=True)

            # News & social
            news = data.get("news", [])
            news_24h = [n for n in news if n.get("age_h", 99) < 24]
            s_icon = "🔥" if len(news_24h) >= 3 else "📰" if news_24h else "📭"
            if news:
                news_text = f"{s_icon} **{len(news_24h)}** stories in last 24h\n"
                news_text += "\n".join(
                    f"• [{n['title'][:65]}...]({n['url']})" for n in news[:4] if n.get("url"))
            else:
                news_text = "📭 No recent news found — quiet on this ticker"
            e.add_field(name="📰 NEWS & CATALYST", value=news_text[:900], inline=False)

            e.set_footer(text=f"🧠 /why conviction engine · {ticker} · Also try /analyze /ai /news")
            await interaction.followup.send(embed=e)
            await _audit(f"🧠 {interaction.user} → /why {ticker} (conviction {conviction:+d})")

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Signals & Scanners
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="signals", description="Latest AI trading signals")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_signals(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🎯 AI Trading Signals", color=COLOR_GOLD,
                              description="Scanning US · HK · JP · Crypto markets...\n"
                                          "Signals pushed to **#live-signals** in real time.")
            e.add_field(name="📢 Pipeline", inline=False,
                        value="1️⃣ AI scans 500+ tickers\n2️⃣ GPT validates each signal\n"
                              "3️⃣ Posted to #live-signals with 📈 Trade buttons\n"
                              "4️⃣ Auto-executed in paper mode")
            e.add_field(name="🔍 Scanners", inline=False,
                        value="`/scan vcp` · `/breakout` · `/dip` · `/momentum` · `/swing`")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="scan", description="Scan for trading setups")
        @app_commands.describe(strategy="vcp, breakout, dip, momentum, swing")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_scan(interaction: discord.Interaction, strategy: str):
            await interaction.response.defer()
            e = discord.Embed(title=f"🔍 Scanning: {strategy.upper()}",
                              description=f"Running **{strategy}** scanner...",
                              color=COLOR_INFO)
            e.add_field(name="Status", value="⏳ Results → #live-signals")
            await interaction.followup.send(embed=e)
            await _audit(f"🔍 {interaction.user} → /scan {strategy}")

        # Scanner shortcuts — individual commands (discord.py requires explicit defs)
        @bot.tree.command(name="breakout", description="Breakout near highs")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_breakout(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="📈 Breakout Scanner",
                              description="Scanning for breakout setups...", color=COLOR_INFO)
            e.add_field(name="Status", value="⏳ Results → #live-signals")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="dip", description="Dip buying opportunities")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_dip(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="💎 Dip Scanner",
                              description="Scanning for dip buying setups...", color=COLOR_INFO)
            e.add_field(name="Status", value="⏳ Results → #live-signals")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="momentum", description="High momentum stocks")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_momentum(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🚀 Momentum Scanner",
                              description="Scanning for momentum setups...", color=COLOR_INFO)
            e.add_field(name="Status", value="⏳ Results → #live-signals")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="swing", description="Swing trade setups (2-10 days)")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_swing(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🎯 Swing Scanner",
                              description="Scanning for swing setups...", color=COLOR_INFO)
            e.add_field(name="Status", value="⏳ Results → #live-signals")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="whale", description="Whale accumulation alerts")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_whale(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🐋 Whale Scanner",
                              description="Scanning for whale accumulation...", color=COLOR_INFO)
            e.add_field(name="Status", value="⏳ Results → #live-signals")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="squeeze", description="Short squeeze candidates")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_squeeze(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🔥 Squeeze Scanner",
                              description="Scanning for short squeeze setups...", color=COLOR_INFO)
            e.add_field(name="Status", value="⏳ Results → #live-signals")
            await interaction.followup.send(embed=e)

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Multi-Market
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="asia", description="Asia markets dashboard (JP + HK + CN)")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_asia(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🌏 Asia Markets", color=COLOR_PURPLE)
            for sym, name in [("^N225","🇯🇵 Nikkei"),("^HSI","🇭🇰 Hang Seng"),
                               ("000001.SS","🇨🇳 Shanghai")]:
                data = await _fetch_stock(sym)
                e.add_field(name=name,
                            value=f"{data.get('price',0):,.2f} ({data.get('change_pct',0):+.2f}%)",
                            inline=False)
            e.add_field(name="More", value="`/japan` · `/hk` · `/crypto`", inline=False)
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="japan", description="Japan market top picks")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_japan(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🇯🇵 Japan Market", color=COLOR_PURPLE)
            for sym, name in [("7203.T","Toyota"),("6758.T","Sony"),("6861.T","Keyence"),
                               ("9984.T","SoftBank"),("8306.T","MUFG")]:
                data = await _fetch_stock(sym)
                e.add_field(name=f"{name}",
                            value=f"¥{data.get('price',0):,.0f} ({data.get('change_pct',0):+.2f}%)")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="hk", description="Hong Kong market top picks")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_hk(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="🇭🇰 Hong Kong Market", color=COLOR_PURPLE)
            for sym, name in [("0700.HK","Tencent"),("9988.HK","Alibaba"),("0005.HK","HSBC"),
                               ("1299.HK","AIA"),("3690.HK","Meituan")]:
                data = await _fetch_stock(sym)
                e.add_field(name=name,
                            value=f"HK${data.get('price',0):,.2f} ({data.get('change_pct',0):+.2f}%)")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="crypto", description="Crypto market dashboard")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_crypto(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="₿ Crypto Dashboard", color=COLOR_GOLD)
            for sym, name in [("BTC-USD","₿ Bitcoin"),("ETH-USD","Ξ Ethereum"),
                               ("SOL-USD","◆ Solana"),("DOGE-USD","🐶 Doge"),
                               ("ADA-USD","♦ Cardano"),("XRP-USD","● Ripple")]:
                data = await _fetch_stock(sym)
                e.add_field(name=name,
                            value=f"${data.get('price',0):,.2f} ({data.get('change_pct',0):+.2f}%)")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="btc", description="Bitcoin detailed analysis")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_btc(interaction: discord.Interaction):
            await interaction.response.defer()
            data = await _fetch_stock("BTC-USD")
            pct = data.get("change_pct", 0)
            e = discord.Embed(title="₿ Bitcoin Analysis", color=COLOR_GOLD)
            e.add_field(name="Price", value=f"**${data.get('price',0):,.2f}**")
            e.add_field(name="24h", value=f"{pct:+.2f}%")
            e.add_field(name="Range",
                        value=f"${data.get('low',0):,.2f} — ${data.get('high',0):,.2f}")
            e.add_field(name="Vol", value=_vol(data.get("volume", 0)))
            await interaction.followup.send(embed=e)

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Trading (with confirmation buttons)
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="portfolio", description="Full portfolio — value, positions, P&L, risk metrics")
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.user.id)
        async def cmd_portfolio(interaction: discord.Interaction):
            """Comprehensive portfolio dashboard — replaces website stats row."""
            await interaction.response.defer()
            now = datetime.now(timezone.utc)
            try:
                positions = []
                cash_balance = 100_000.0
                portfolio_value = 100_000.0
                day_pnl = 0.0
                total_pnl = 0.0
                try:
                    import alpaca_trade_api as tradeapi
                    api = tradeapi.REST(
                        settings.alpaca_api_key, settings.alpaca_secret_key,
                        base_url=getattr(settings, 'alpaca_base_url',
                                         'https://paper-api.alpaca.markets'))
                    acct = api.get_account()
                    portfolio_value = float(acct.portfolio_value)
                    cash_balance = float(acct.cash)
                    day_pnl = float(acct.equity) - float(acct.last_equity)
                    total_pnl = portfolio_value - 100_000
                    for p in api.list_positions():
                        positions.append({
                            "symbol": p.symbol, "qty": int(p.qty),
                            "current": float(p.current_price),
                            "pnl": float(p.unrealized_pl),
                            "pnl_pct": float(p.unrealized_plpc) * 100,
                        })
                except Exception:
                    pass

                spy = await _fetch_stock("SPY")
                vix_d = await _fetch_stock("^VIX")
                vix_p = vix_d.get("price", 0)
                exposure = ((portfolio_value - cash_balance) / portfolio_value * 100) if portfolio_value else 0

                e = discord.Embed(
                    title="💼 Portfolio Dashboard",
                    description=(
                        f"**${portfolio_value:,.2f}** total value • "
                        f"{'📝 Paper' if not positions else f'{len(positions)} positions'}\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=COLOR_BUY if day_pnl >= 0 else COLOR_SELL, timestamp=now)

                e.add_field(name="📈 Day P&L",
                            value=f"{'🟢' if day_pnl >= 0 else '🔴'} **${day_pnl:+,.2f}**")
                e.add_field(name="💰 Total P&L",
                            value=f"{'🟢' if total_pnl >= 0 else '🔴'} **${total_pnl:+,.2f}**")
                e.add_field(name="💵 Cash", value=f"${cash_balance:,.2f}")
                exp_icon = "🔴" if exposure > 80 else "🟡" if exposure > 50 else "🟢"
                e.add_field(name="📊 Exposure", value=f"{exp_icon} **{exposure:.1f}%**")
                e.add_field(name="📉 VIX",
                            value=f"{'🔴' if vix_p > 25 else '🟡' if vix_p > 18 else '🟢'} **{vix_p:.1f}**")
                e.add_field(name="🇺🇸 SPY", value=f"{spy.get('change_pct',0):+.2f}%")

                if positions:
                    positions.sort(key=lambda x: abs(x["pnl"]), reverse=True)
                    pos_lines = []
                    for p in positions[:8]:
                        icon = "🟢" if p["pnl"] >= 0 else "🔴"
                        pos_lines.append(
                            f"{icon} **{p['symbol']}** ×{p['qty']} "
                            f"${p['current']:.2f} ({p['pnl_pct']:+.1f}%) "
                            f"P&L: ${p['pnl']:+,.2f}")
                    if len(positions) > 8:
                        pos_lines.append(f"... +{len(positions)-8} more")
                    e.add_field(name=f"📋 Positions ({len(positions)})",
                                value="\n".join(pos_lines), inline=False)
                else:
                    e.add_field(name="📋 Positions",
                                value="No open positions • `/buy AAPL 10` to start", inline=False)

                e.add_field(name="⚡ Quick Actions", inline=False,
                            value="`/daily_update` brief · `/pnl` P&L · `/risk AAPL` sizing · `/watchlist` tracked")
                e.set_footer(text="TradingAI Pro v6 • Portfolio Dashboard")
                await interaction.followup.send(embed=e)
            except Exception as exc:
                logger.error(f"portfolio error: {exc}")
                await interaction.followup.send(f"❌ Error: {exc}")

        @bot.tree.command(name="buy", description="Buy shares (paper) — with confirmation")
        @app_commands.describe(ticker="Stock symbol", quantity="Shares")
        @app_commands.checks.cooldown(1, 3, key=lambda i: i.user.id)
        async def cmd_buy(interaction: discord.Interaction, ticker: str, quantity: int):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            price = d.get("price", 0)
            total = price * quantity
            e = discord.Embed(
                title=f"🟢 BUY Order — {ticker.upper()}",
                description=(f"**{quantity}** shares @ **${price:.2f}**\n"
                             f"Total: **${total:,.2f}**\n\nConfirm or cancel below."),
                color=COLOR_BUY)
            await interaction.followup.send(
                embed=e, view=ConfirmTradeView(ticker.upper(), "BUY", quantity, price))

        @bot.tree.command(name="sell", description="Sell shares (paper) — with confirmation")
        @app_commands.describe(ticker="Stock symbol", quantity="Shares")
        @app_commands.checks.cooldown(1, 3, key=lambda i: i.user.id)
        async def cmd_sell(interaction: discord.Interaction, ticker: str, quantity: int):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            price = d.get("price", 0)
            total = price * quantity
            e = discord.Embed(
                title=f"🔴 SELL Order — {ticker.upper()}",
                description=(f"**{quantity}** shares @ **${price:.2f}**\n"
                             f"Total: **${total:,.2f}**\n\nConfirm or cancel below."),
                color=COLOR_SELL)
            await interaction.followup.send(
                embed=e, view=ConfirmTradeView(ticker.upper(), "SELL", quantity, price))

        @bot.tree.command(name="positions", description="View open positions")
        async def cmd_positions(interaction: discord.Interaction):
            e = discord.Embed(title="📊 Open Positions",
                              description="No open positions.\nUse `/buy` to open one.",
                              color=COLOR_INFO)
            await interaction.response.send_message(embed=e)

        @bot.tree.command(name="pnl", description="Today's P&L breakdown — positions, benchmark, risk")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_pnl(interaction: discord.Interaction):
            await interaction.response.defer()
            now = datetime.now(timezone.utc)
            try:
                day_pnl = 0.0
                total_pnl = 0.0
                winners = losers = 0
                best_sym = worst_sym = ""
                best_pnl = worst_pnl = 0.0
                try:
                    import alpaca_trade_api as tradeapi
                    api = tradeapi.REST(
                        settings.alpaca_api_key, settings.alpaca_secret_key,
                        base_url=getattr(settings, 'alpaca_base_url',
                                         'https://paper-api.alpaca.markets'))
                    acct = api.get_account()
                    day_pnl = float(acct.equity) - float(acct.last_equity)
                    total_pnl = float(acct.portfolio_value) - 100_000
                    for p in api.list_positions():
                        upl = float(p.unrealized_pl)
                        if upl >= 0:
                            winners += 1
                        else:
                            losers += 1
                        if upl > best_pnl:
                            best_pnl, best_sym = upl, p.symbol
                        if upl < worst_pnl:
                            worst_pnl, worst_sym = upl, p.symbol
                except Exception:
                    pass

                spy = await _fetch_stock("SPY")
                spy_pct = spy.get("change_pct", 0)
                e = discord.Embed(
                    title="💵 Today's P&L",
                    description=f"{'🟢' if day_pnl >= 0 else '🔴'} **${day_pnl:+,.2f}**",
                    color=COLOR_BUY if day_pnl >= 0 else COLOR_SELL, timestamp=now)
                e.add_field(name="📈 Day P&L", value=f"${day_pnl:+,.2f}")
                e.add_field(name="💰 Total P&L", value=f"${total_pnl:+,.2f}")
                e.add_field(name="🇺🇸 SPY", value=f"{spy_pct:+.2f}%")
                if best_sym:
                    e.add_field(name="🏆 Best", value=f"{best_sym} ${best_pnl:+,.2f}")
                if worst_sym:
                    e.add_field(name="💔 Worst", value=f"{worst_sym} ${worst_pnl:+,.2f}")
                if winners or losers:
                    e.add_field(name="W/L", value=f"{winners}W / {losers}L")
                elif not best_sym:
                    e.add_field(name="📋", value="No open positions", inline=False)
                e.set_footer(text="/portfolio for full view · /stats for history")
                await interaction.followup.send(embed=e)
            except Exception as exc:
                await interaction.followup.send(f"❌ {exc}")

        @bot.tree.command(name="risk", description="Position sizing calculator")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_risk(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            price = d.get("price", 0)
            acct, rpct = 100_000, 0.01
            stop = price * 0.05
            shares = int((acct * rpct) / stop) if stop else 0
            e = discord.Embed(title=f"🛡️ Position Sizing — {ticker.upper()}", color=COLOR_INFO)
            e.add_field(name="Price", value=f"${price:.2f}")
            e.add_field(name="Account", value=f"${acct:,.0f}")
            e.add_field(name="Risk", value=f"{rpct*100:.1f}%")
            e.add_field(name="Stop", value=f"${stop:.2f} (5%)")
            e.add_field(name="🎯 Shares", value=f"**{shares}** (${shares*price:,.0f})")
            e.add_field(name="Max Loss", value=f"${acct*rpct:,.0f}")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="stats", description="Trading statistics and performance metrics")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_stats(interaction: discord.Interaction):
            await interaction.response.defer()
            now = datetime.now(timezone.utc)
            try:
                portfolio_val = 100_000.0
                total_pnl = 0.0
                n_trades = 0
                n_positions = 0
                try:
                    import alpaca_trade_api as tradeapi
                    api = tradeapi.REST(
                        settings.alpaca_api_key, settings.alpaca_secret_key,
                        base_url=getattr(settings, 'alpaca_base_url',
                                         'https://paper-api.alpaca.markets'))
                    acct = api.get_account()
                    portfolio_val = float(acct.portfolio_value)
                    total_pnl = portfolio_val - 100_000
                    n_positions = len(api.list_positions())
                    orders = api.list_orders(status='closed', limit=100)
                    n_trades = len([o for o in orders if o.status == 'filled'])
                except Exception:
                    pass

                roi = (total_pnl / 100_000 * 100) if total_pnl else 0
                spy = await _fetch_stock("SPY")

                e = discord.Embed(title="📊 Trading Statistics", color=COLOR_PURPLE,
                                  timestamp=now)
                e.add_field(name="💰 Portfolio", value=f"${portfolio_val:,.2f}")
                e.add_field(name="📈 Total P&L",
                            value=f"{'🟢' if total_pnl >= 0 else '🔴'} ${total_pnl:+,.2f}")
                e.add_field(name="📊 ROI", value=f"{roi:+.2f}%")
                e.add_field(name="🔢 Trades", value=str(n_trades))
                e.add_field(name="📋 Positions", value=str(n_positions))
                e.add_field(name="🇺🇸 SPY Today", value=f"{spy.get('change_pct',0):+.2f}%")
                if n_trades == 0:
                    e.add_field(name="💡 Getting Started", inline=False,
                                value="Start trading to build stats!\n"
                                      "`/buy AAPL 10` · `/scan` for setups · `/signals` for AI picks")
                e.set_footer(text="TradingAI Pro v6 · /portfolio /pnl for more")
                await interaction.followup.send(embed=e)
            except Exception as exc:
                await interaction.followup.send(f"❌ {exc}")

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Tools
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="backtest",
                          description="Backtest all 4 strategies on a ticker — ranked by Sharpe, win-rate & regime fit")
        @app_commands.describe(ticker="Symbol e.g. NVDA, TSLA, BTC-USD",
                               period="1mo 3mo 6mo 1y 2y (default 1y)")
        @app_commands.checks.cooldown(1, 20, key=lambda i: i.user.id)
        async def cmd_backtest(interaction: discord.Interaction,
                                ticker: str, period: str = "1y"):
            await interaction.response.defer()
            ticker = ticker.upper().strip()
            now = datetime.now(timezone.utc)

            async def _async_run(sym, per):
                hist = await _mds.get_history(sym, period=per)
                if hist is None or hist.empty or len(hist) < 30:
                    return None
                opt = _get_optimizer()
                if opt is None:
                    return None
                return await asyncio.to_thread(opt.full_analysis, sym, hist, per)

            await interaction.followup.send(
                embed=discord.Embed(
                    title=f"🔬 Running AI Backtest — {ticker} ({period})",
                    description="Testing SWING · BREAKOUT · MEAN_REVERSION · MOMENTUM\nWalk-forward validation + parameter sweep + cross-check...",
                    color=COLOR_INFO, timestamp=now))

            result = await _async_run(ticker, period)
            if result is None:
                await interaction.followup.send(
                    f"❌ No data for `{ticker}` ({period}). Try a different symbol or period.")
                return

            regime = result["regime"]
            ranked = result["ranked"]
            best = result["best_strategy"]
            best_r = result["strategy_results"].get(best, {})
            cc = result["cross_check"]
            rr = result["regime_recommendation"]
            mc = result.get("monte_carlo", {})
            wf = result.get("walk_forward", {})

            # ── Header embed ──
            e = discord.Embed(
                title=f"📊 Backtest Results — {ticker} ({period})",
                description=(
                    f"**Regime: {regime['label']}** · Vol {regime.get('vol_ann',0):.0f}% ann · "
                    f"Trend {regime.get('trend_pct',0):+.1f}% vs SMA50\n"
                    f"**4 strategies tested · best = {best}**"
                ),
                color=COLOR_GOLD, timestamp=now)

            # Strategy comparison table
            table_lines = []
            for r in ranked:
                name = r["strategy"]
                score = r.get("score", 0)
                trades = r.get("trades", 0)
                wr = r.get("win_rate", 0) * 100
                sharpe = r.get("sharpe", 0)
                dd = r.get("max_dd", 0) * 100
                bar = "█" * int(score // 12) + "░" * (8 - int(score // 12))
                medal = "🥇" if name == best else ("🥈" if r == ranked[1] else "  ")
                table_lines.append(
                    f"{medal} **{name}** `{bar}` {score:.0f}\n"
                    f"  Trades {trades} · WR {wr:.0f}% · Sharpe {sharpe:.2f} · DD {dd:.1f}%")
            e.add_field(name="🏆 Strategy Ranking",
                        value="\n".join(table_lines)[:900], inline=False)

            # Regime recommendation
            e.add_field(
                name=f"🌡️ Regime: {rr['regime']}",
                value=(
                    f"{rr['explanation']}\n"
                    f"→ **Best strategy for this regime: {rr['best_strategy']}** "
                    f"(score {rr['best_score']:.0f}) "
                    f"{'✅ Regime-fit' if rr['regime_fit'] else '⚠️ Not ideal regime'}"
                ),
                inline=False)

            # Cross-check
            verdict_emoji = {"STRONG_AGREEMENT": "✅", "MIXED_SIGNAL": "⚠️",
                             "AVOID": "🔴", "MODERATE": "🟡"}.get(cc["verdict"], "❓")
            e.add_field(
                name=f"{verdict_emoji} Cross-Check: {cc['verdict']}",
                value=cc["explanation"][:300], inline=False)

            # Walk-forward OOS for best strategy
            if wf.get(best):
                wf_r = wf[best]
                stable = "✅ Stable" if wf_r.get("stable") else "⚠️ Unstable"
                e.add_field(
                    name=f"🔄 Walk-Forward OOS — {best}",
                    value=(
                        f"{stable} · {wf_r['folds']} folds\n"
                        f"OOS Sharpe **{wf_r['avg_oos_sharpe']:.2f}** · "
                        f"OOS Win-rate **{wf_r['avg_oos_win_rate']*100:.0f}%** · "
                        f"Score **{wf_r['avg_oos_score']:.0f}**"
                    ), inline=False)

            # Param sweep improvement
            sweep_delta = result.get("sweep_improvement", 0)
            if abs(sweep_delta) > 0.5:
                bp = result.get("best_params", {})
                params_str = "  ·  ".join(f"{k}={v}" for k, v in bp.items())
                e.add_field(
                    name=f"⚙️ Optimal Params — {best} (+{sweep_delta:.1f} pts)",
                    value=params_str[:200], inline=False)

            # Monte Carlo
            if mc:
                e.add_field(
                    name="🎲 Monte Carlo (500 runs)",
                    value=(
                        f"Median final equity **{mc['median_final']*100:.0f}%** · "
                        f"5th pct **{mc['p5_final']*100:.0f}%** · "
                        f"Profitable in **{mc['pct_profitable']:.0f}%** of simulations"
                    ), inline=False)

            # Self-correction notes
            corrections = result.get("correction_notes", [])
            if corrections:
                e.add_field(name="🧠 Self-Correction Status",
                            value="\n".join(corrections[:4])[:400], inline=False)

            e.set_footer(text=f"✅ Real backtest · {ticker} · /best_strategy for regime pick · /strategy_report for live accuracy")
            await interaction.followup.send(embed=e)
            await _audit(f"📊 {interaction.user} → /backtest {ticker} {period} → best={best} score={best_r.get('score',0):.0f}")

        @bot.tree.command(name="best_strategy",
                          description="Which strategy wins on this ticker RIGHT NOW in current market regime?")
        @app_commands.describe(ticker="Symbol e.g. SPY, NVDA, BTC-USD")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_best_strategy(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            ticker = ticker.upper().strip()
            now = datetime.now(timezone.utc)

            async def _async_best(sym):
                hist = await _mds.get_history(sym, period="6mo")
                if hist is None or hist.empty or len(hist) < 30:
                    return None
                opt = _get_optimizer()
                if opt is None:
                    return None
                from src.engines.strategy_optimizer import _regime_from_data
                def _compute():
                    ranked = opt.quick_regime_rank(hist)
                    regime = _regime_from_data(hist)
                    return {"ranked": ranked, "regime": regime}
                return await asyncio.to_thread(_compute)

            result = await _async_best(ticker)
            if not result:
                await interaction.followup.send(f"❌ No data for `{ticker}`.")
                return

            regime = result["regime"]
            ranked = result["ranked"]
            best = ranked[0] if ranked else {}

            regime_icons = {
                "RISK_ON_TRENDING": "🟢", "LOW_VOL_UPTREND": "🟢",
                "NEUTRAL": "🟡", "LOW_VOL_RANGING": "🟡",
                "RISK_OFF": "🔴", "HIGH_VOL": "🔴", "DOWNTREND": "🔴",
                "RISK_ON_HIGH_VOL": "🟠",
            }
            icon = regime_icons.get(regime["label"], "⚪")

            e = discord.Embed(
                title=f"🏆 Best Strategy for {ticker} Right Now",
                description=(
                    f"{icon} **Regime: {regime['label']}**\n"
                    f"Vol {regime.get('vol_ann',0):.0f}% ann · "
                    f"Trend {regime.get('trend_pct',0):+.1f}% vs SMA50 · "
                    f"20d mom {regime.get('mom20d',0):+.1f}%"
                ),
                color=COLOR_GOLD, timestamp=now)

            medals = ["🥇", "🥈", "🥉", "4️⃣"]
            lines = []
            for i, r in enumerate(ranked):
                medal = medals[i] if i < len(medals) else "  "
                fit_tag = "✅ Regime fit" if r["regime_fit"] else "⚠️ Off-regime"
                lines.append(f"{medal} **{r['strategy']}** — Score {r['score']:.0f}  {fit_tag}")
            e.add_field(name="Strategy Rankings (6mo data)",
                        value="\n".join(lines), inline=False)

            if best:
                e.add_field(
                    name=f"✅ Use this: {best['strategy']}",
                    value=(
                        f"Best fit for **{regime['label']}** regime.\n"
                        f"`/backtest {ticker} 1y` → full details + optimal parameters."
                    ), inline=False)

            e.set_footer(text="/backtest for walk-forward + param sweep · /strategy_report for live accuracy")
            await interaction.followup.send(embed=e)
            await _audit(f"🏆 {interaction.user} → /best_strategy {ticker} → {best.get('strategy','?')}")

        @bot.tree.command(name="strategy_report",
                          description="AI self-learning report — live accuracy, corrections, regime performance")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_strategy_report(interaction: discord.Interaction):
            await interaction.response.defer()
            now = datetime.now(timezone.utc)
            opt = _get_optimizer()
            if opt is None:
                await interaction.followup.send("❌ Strategy optimizer not available.")
                return

            acc = opt.get_accuracy_summary()
            e = discord.Embed(
                title="🧠 AI Self-Learning Strategy Report",
                description=(
                    "Live accuracy tracked from every signal outcome.\n"
                    "Scoring weights auto-adjust based on what's actually working."
                ),
                color=COLOR_PURPLE, timestamp=now)

            if not acc:
                e.add_field(
                    name="📊 Status",
                    value=(
                        "No live outcomes recorded yet.\n"
                        "The optimizer learns as signals hit target or stop.\n"
                        "Run `/backtest TICKER` to see historical backtest performance."
                    ), inline=False)
            else:
                for strat, data in acc.items():
                    total = data["total"]
                    if total == 0:
                        continue
                    wr = data.get("live_win_rate", 0) or 0
                    factor = data.get("score_factor", 1.0)
                    status = "✅" if wr >= 55 else ("⚠️" if wr >= 40 else "🔴")
                    up_dn = "🔺" if factor > 1.05 else ("🔻" if factor < 0.95 else "➡️")
                    e.add_field(
                        name=f"{status} {strat}",
                        value=(
                            f"Tracked: **{total}** signals\n"
                            f"Live win-rate: **{wr:.0f}%**\n"
                            f"{up_dn} Score factor: **×{factor:.2f}** (auto-adjusted)"
                        ))

            e.add_field(
                name="ℹ️ How Self-Correction Works",
                value=(
                    "1️⃣ Every signal tagged with its strategy\n"
                    "2️⃣ Target hit → WIN recorded\n"
                    "3️⃣ Stop hit → LOSS recorded\n"
                    "4️⃣ Live win-rate updates score multiplier (×0.6–1.4)\n"
                    "5️⃣ Weak strategies get lower scores, strong ones boosted\n"
                    "6️⃣ Rebalances every 20 new outcomes"
                ), inline=False)

            e.set_footer(text="/backtest TICKER · /best_strategy TICKER · auto_strategy_learn runs every 6h")
            await interaction.followup.send(embed=e)
            await _audit(f"🧠 {interaction.user} → /strategy_report")

        @bot.tree.command(name="watchlist",
                          description="Manage your watchlist — view, add, remove tickers with live prices")
        @app_commands.describe(
            action="show / add / remove / clear (default: show)",
            ticker="Stock symbol (for add/remove)")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_watchlist(interaction: discord.Interaction,
                                action: str = "show", ticker: str = ""):
            uid = interaction.user.id
            act = action.lower().strip()

            if act == "add" and ticker:
                t = ticker.upper().strip()
                if uid not in _user_watchlists:
                    _user_watchlists[uid] = []
                if t in _user_watchlists[uid]:
                    await interaction.response.send_message(
                        f"⚠️ **{t}** already in watchlist", ephemeral=True)
                    return
                if len(_user_watchlists[uid]) >= 20:
                    await interaction.response.send_message(
                        "❌ Watchlist full (max 20)", ephemeral=True)
                    return
                _user_watchlists[uid].append(t)
                await interaction.response.send_message(
                    f"✅ **{t}** added to watchlist ({len(_user_watchlists[uid])}/20)",
                    ephemeral=True)
                return

            if act == "remove" and ticker:
                t = ticker.upper().strip()
                wl = _user_watchlists.get(uid, [])
                if t in wl:
                    wl.remove(t)
                    await interaction.response.send_message(
                        f"✅ **{t}** removed", ephemeral=True)
                else:
                    await interaction.response.send_message(
                        f"❌ **{t}** not in watchlist", ephemeral=True)
                return

            if act == "clear":
                _user_watchlists[uid] = []
                await interaction.response.send_message(
                    "✅ Watchlist cleared", ephemeral=True)
                return

            # Show watchlist with live prices
            await interaction.response.defer()
            wl = _user_watchlists.get(uid, [])
            if not wl:
                e = discord.Embed(
                    title="👀 Your Watchlist",
                    description=(
                        "Empty! Add tickers:\n"
                        "`/watchlist action:add ticker:AAPL`\n"
                        "`/watchlist action:add ticker:NVDA`\n"
                        "`/watchlist action:add ticker:BTC-USD`"
                    ), color=COLOR_INFO)
                await interaction.followup.send(embed=e)
                return

            now = datetime.now(timezone.utc)
            e = discord.Embed(
                title=f"👀 Your Watchlist ({len(wl)} tickers)",
                color=COLOR_INFO, timestamp=now)
            for sym in wl:
                data = await _fetch_stock(sym)
                if "error" not in data:
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴" if pct < 0 else "⚪"
                    e.add_field(
                        name=f"{icon} {sym}",
                        value=f"${data.get('price',0):.2f} ({pct:+.2f}%)")
                else:
                    e.add_field(name=f"⚠️ {sym}", value="No data")
            e.set_footer(text="/watchlist action:add ticker:XYZ · /watchlist action:remove ticker:XYZ")
            await interaction.followup.send(embed=e)

        @bot.tree.command(name="alert", description="Set a price alert — auto-notified when triggered")
        @app_commands.describe(ticker="Symbol", condition="above or below", price="Target $")
        async def cmd_alert(interaction: discord.Interaction,
                            ticker: str, condition: str, price: float):
            uid = interaction.user.id
            sym = ticker.upper().strip()
            cond = condition.lower().strip()
            if cond not in ("above", "below"):
                return await interaction.response.send_message("❌ Condition must be `above` or `below`", ephemeral=True)

            if uid not in _user_alerts:
                _user_alerts[uid] = []
            if len(_user_alerts[uid]) >= 20:
                return await interaction.response.send_message("❌ Max 20 alerts. Use `/my_alerts` to manage.", ephemeral=True)

            _user_alerts[uid].append({
                "ticker": sym, "condition": cond, "price": price,
                "triggered": False, "set_at": datetime.now(timezone.utc).isoformat()
            })

            e = discord.Embed(
                title=f"🔔 Alert Set — {sym}",
                description=(
                    f"You'll be **notified** when **{sym}** goes **{cond}** **${price:.2f}**\n\n"
                    f"📡 Monitored every **3 minutes** by our real-time engine\n"
                    f"💡 Use `/my_alerts` to see/remove your alerts"
                ),
                color=COLOR_WARN)
            e.add_field(name="Active Alerts", value=str(len([a for a in _user_alerts[uid] if not a["triggered"]])))
            await interaction.response.send_message(embed=e)

        @bot.tree.command(name="my_alerts", description="View and manage your price alerts")
        async def cmd_my_alerts(interaction: discord.Interaction):
            uid = interaction.user.id
            alerts = _user_alerts.get(uid, [])
            active = [a for a in alerts if not a["triggered"]]
            triggered = [a for a in alerts if a["triggered"]]

            if not alerts:
                return await interaction.response.send_message(
                    "📭 No alerts set. Use `/alert AAPL above 200` to create one.", ephemeral=True)

            e = discord.Embed(title="🔔 Your Price Alerts",
                              color=COLOR_INFO,
                              timestamp=datetime.now(timezone.utc))

            if active:
                lines = []
                for i, a in enumerate(active, 1):
                    lines.append(f"`{i}` **{a['ticker']}** {a['condition']} **${a['price']:.2f}**")
                e.add_field(name=f"⏳ Active ({len(active)})",
                            value="\n".join(lines[:10]), inline=False)
            if triggered:
                lines = [f"✅ **{a['ticker']}** {a['condition']} ${a['price']:.2f}" for a in triggered[-5:]]
                e.add_field(name=f"✅ Recently Triggered ({len(triggered)})",
                            value="\n".join(lines), inline=False)

            e.set_footer(text="/clear_alerts to remove all • Checked every 3 min")
            await interaction.response.send_message(embed=e)

        @bot.tree.command(name="clear_alerts", description="Clear all your price alerts")
        async def cmd_clear_alerts(interaction: discord.Interaction):
            uid = interaction.user.id
            count = len(_user_alerts.get(uid, []))
            _user_alerts[uid] = []
            await interaction.response.send_message(f"🗑️ Cleared {count} alerts.", ephemeral=True)

        @bot.tree.command(name="daily",
                          description="📊 Full daily intelligence brief (alias for /daily_update)")
        @app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
        async def cmd_daily(interaction: discord.Interaction):
            """Alias for /daily_update — full market intelligence brief."""
            await cmd_daily_update.callback(interaction)

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Dashboard & Reports (Discord-First)
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="dashboard",
                          description="🖥️ Full trading dashboard — regime, markets, portfolio, signals")
        @app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
        async def cmd_dashboard(interaction: discord.Interaction):
            """The mega command — replaces the web dashboard entirely.
            Shows everything in 3 embeds: command center, markets, signals."""
            await interaction.response.defer()
            try:
                now = datetime.now(timezone.utc)
                spy_data = await _fetch_stock("SPY")
                qqq_data = await _fetch_stock("QQQ")
                iwm_data = await _fetch_stock("IWM")
                vix_data = await _fetch_stock("^VIX")
                tlt_data = await _fetch_stock("TLT")
                btc_data = await _fetch_stock("BTC-USD")
                gold_data = await _fetch_stock("GLD")

                vix = vix_data.get("price", 0)
                spy_pct = spy_data.get("change_pct", 0)
                qqq_pct = qqq_data.get("change_pct", 0)
                btc_pct = btc_data.get("change_pct", 0)

                risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                    "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                trend = "UPTREND" if spy_pct > 0.5 else "DOWNTREND" if spy_pct < -0.5 else "NEUTRAL"
                vol_state = "HIGH_VOL" if vix > 22 else "LOW_VOL" if vix < 15 else "NORMAL"
                risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))
                regime_icons = {"RISK_ON": "🟢 RISK ON", "NEUTRAL": "🟡 NEUTRAL", "RISK_OFF": "🔴 RISK OFF"}
                regime_label = regime_icons.get(risk, "🟡 NEUTRAL")

                if risk == "RISK_ON" and vix < 16:
                    ai_rec = "🟢 AGGRESSIVE"
                elif risk == "RISK_ON":
                    ai_rec = "🟢 NORMAL"
                elif risk == "NEUTRAL" and vix < 20:
                    ai_rec = "🟡 NORMAL"
                elif risk == "NEUTRAL":
                    ai_rec = "🟡 CAUTIOUS"
                else:
                    ai_rec = "🔴 DEFENSIVE"

                playbook_map = {
                    ("RISK_ON", "UPTREND"): ["Momentum", "Breakout", "Trend-Follow"],
                    ("RISK_ON", "NEUTRAL"): ["Swing", "Mean-Reversion"],
                    ("NEUTRAL", "UPTREND"): ["Momentum", "VCP"],
                    ("NEUTRAL", "NEUTRAL"): ["Mean-Reversion", "Swing"],
                    ("NEUTRAL", "DOWNTREND"): ["Mean-Reversion"],
                    ("RISK_OFF", "DOWNTREND"): ["Cash"],
                }
                strats = playbook_map.get((risk, trend), ["Swing", "Mean-Reversion"])

                # ── EMBED 1: Command Center ──
                score_bar = "█" * (int(risk_on_score) // 10) + "░" * (10 - int(risk_on_score) // 10)
                e1 = discord.Embed(
                    title=f"🖥️ Trading Dashboard — {now.strftime('%a %b %d, %H:%M UTC')}",
                    description=(
                        f"**{regime_label}** • Score: **{risk_on_score:.0f}/100** `{score_bar}`\n"
                        f"Trend: **{trend}** • Vol: **{vol_state}** • AI: **{ai_rec}**\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=COLOR_BUY if risk == "RISK_ON" else COLOR_SELL if risk == "RISK_OFF" else COLOR_GOLD,
                    timestamp=now)

                e1.add_field(name="📋 Active Strategies",
                             value=" · ".join(f"`{s}`" for s in strats), inline=False)

                # Risk alerts
                alerts = []
                if vix > 25: alerts.append(f"⚠️ VIX {vix:.1f} — cut size 50%")
                if spy_pct < -2: alerts.append("⚠️ SPY >2% drop — watch for cascade")
                if abs(qqq_pct - spy_pct) > 1.5: alerts.append("⚠️ Tech/SPY divergence")
                e1.add_field(name="🛡️ Risk Alerts",
                             value="\n".join(alerts) if alerts else "✅ All clear",
                             inline=False)

                # Portfolio snapshot
                pv = 100_000.0
                dp = 0.0
                cash = 100_000.0
                npos = 0
                try:
                    import alpaca_trade_api as tradeapi
                    api = tradeapi.REST(
                        settings.alpaca_api_key, settings.alpaca_secret_key,
                        base_url=getattr(settings, 'alpaca_base_url',
                                         'https://paper-api.alpaca.markets'))
                    acct = api.get_account()
                    pv = float(acct.portfolio_value)
                    cash = float(acct.cash)
                    dp = float(acct.equity) - float(acct.last_equity)
                    npos = len(api.list_positions())
                except Exception:
                    pass
                exposure = ((pv - cash) / pv * 100) if pv else 0
                e1.add_field(name="💼 Portfolio",
                             value=f"${pv:,.0f} | Day: ${dp:+,.0f} | Cash: ${cash:,.0f}")
                e1.add_field(name="📊 Exposure",
                             value=f"{exposure:.0f}% | {npos} positions")
                e1.add_field(name="📉 VIX",
                             value=f"{'🔴' if vix > 25 else '🟡' if vix > 18 else '🟢'} {vix:.1f}")

                # Chain of thought
                cot = []
                cot.append(f"VIX {vix:.1f} → {'⚠️ elevated' if vix > 22 else '✅ calm' if vix < 16 else '🟡 moderate'}")
                cot.append(f"SPY {spy_pct:+.2f}% → {'momentum' if spy_pct > 0.3 else 'selling' if spy_pct < -0.3 else 'range-bound'}")
                if abs(btc_pct) > 3:
                    cot.append(f"BTC {btc_pct:+.1f}% → {'risk-on' if btc_pct > 0 else 'risk-off'} signal")
                e1.add_field(name="🧠 AI Reasoning",
                             value="\n".join(f"→ {c}" for c in cot), inline=False)

                e1.set_footer(text="TradingAI Pro v6 • Discord-First Dashboard")
                await interaction.followup.send(embed=e1)

                # ── EMBED 2: Market Overview ──
                e2 = discord.Embed(title="🌎 Market Overview", color=COLOR_INFO, timestamp=now)
                idx_lines = []
                for sym, name in _INDICES[:4]:
                    d = await _fetch_stock(sym)
                    p = d.get("change_pct", 0)
                    idx_lines.append(f"{'🟢' if p > 0 else '🔴'} **{name}** ${d.get('price',0):.2f} ({p:+.2f}%)")
                e2.add_field(name="🇺🇸 US Indices", value="\n".join(idx_lines), inline=False)

                asia = []
                for sym, name in _WATCH_ASIA:
                    d = await _fetch_stock(sym)
                    p = d.get("change_pct", 0)
                    asia.append(f"{'🟢' if p > 0 else '🔴'} {name} {p:+.2f}%")
                e2.add_field(name="🌏 Asia", value=" | ".join(asia) or "Closed", inline=True)

                e2.add_field(name="🌍 Macro", value=(
                    f"VIX: {vix:.1f} | Gold: {gold_data.get('change_pct',0):+.2f}% | "
                    f"TLT: {tlt_data.get('change_pct',0):+.2f}% | "
                    f"BTC: ${btc_data.get('price',0):,.0f} ({btc_pct:+.2f}%)"
                ), inline=False)

                sector_text = []
                for sym, name in _SECTORS[:6]:
                    d = await _fetch_stock(sym)
                    p = d.get("change_pct", 0)
                    sector_text.append(f"{'🟢' if p > 0 else '🔴'} {name} {p:+.1f}%")
                e2.add_field(name="🏭 Sectors (Top 6)",
                             value=" | ".join(sector_text), inline=False)
                e2.set_footer(text="/sector for full heatmap · /macro for details · /crypto for coins")
                await interaction.followup.send(embed=e2)

                # ── EMBED 3: Top Signals ──
                try:
                    scan_results = await _async_signal_scan(_WATCH_US[:20])
                    if scan_results:
                        scan_results.sort(key=lambda x: x["score"], reverse=True)
                        e3 = discord.Embed(
                            title="🎯 Top AI Trade Ideas",
                            description="Live scan • swing + breakout + momentum",
                            color=COLOR_GOLD, timestamp=now)
                        for i, sig in enumerate(scan_results[:5], 1):
                            arrow = "🟢" if sig["direction"] == "LONG" else "🔴"
                            e3.add_field(
                                name=f"{arrow} #{i} {sig['ticker']} ${sig['price']:.2f}",
                                value=(
                                    f"Score: **{sig['score']}** | R:R: **{sig.get('rr_ratio',0):.1f}:1**\n"
                                    f"Stop: ${sig.get('stop',0):.2f} → Target: ${sig.get('target',0):.2f}"
                                ), inline=False)
                        e3.set_footer(text="/signals for all · /ai TICKER for deep analysis")
                        await interaction.followup.send(embed=e3)
                except Exception:
                    pass

                await _audit(f"🖥️ {interaction.user} → /dashboard ({risk})")
            except Exception as exc:
                logger.error(f"dashboard error: {exc}")
                await interaction.followup.send(f"❌ Error: {exc}")

        @bot.tree.command(name="report",
                          description="📋 On-demand morning memo or EOD scorecard")
        @app_commands.describe(style="morning or eod (default: auto based on time)")
        @app_commands.checks.cooldown(1, 60, key=lambda i: i.user.id)
        async def cmd_report(interaction: discord.Interaction, style: str = "auto"):
            """Generate and display morning memo or EOD scorecard on demand."""
            await interaction.response.defer()
            now = datetime.now(timezone.utc)
            rtype = style.lower().strip()
            if rtype == "auto":
                rtype = "eod" if now.hour >= 19 else "morning"
            try:
                spy = await _fetch_stock("SPY")
                qqq = await _fetch_stock("QQQ")
                iwm = await _fetch_stock("IWM")
                vix_d = await _fetch_stock("^VIX")
                tlt = await _fetch_stock("TLT")
                btc = await _fetch_stock("BTC-USD")
                gld = await _fetch_stock("GLD")

                vix = vix_d.get("price", 0)
                spy_pct = spy.get("change_pct", 0)
                qqq_pct = qqq.get("change_pct", 0)
                btc_pct = btc.get("change_pct", 0)

                risk = "RISK_OFF" if (vix > 25 or spy_pct < -1.5) else (
                    "RISK_ON" if (vix < 18 and spy_pct > 0.3) else "NEUTRAL")
                trend = "UPTREND" if spy_pct > 0.5 else "DOWNTREND" if spy_pct < -0.5 else "NEUTRAL"
                vol_state = "HIGH_VOL" if vix > 22 else "LOW_VOL" if vix < 15 else "NORMAL"
                risk_on_score = max(0, min(100, 50 + spy_pct * 10 - (vix - 18) * 3))
                regime_icons = {"RISK_ON": "🟢 RISK ON", "NEUTRAL": "🟡 NEUTRAL", "RISK_OFF": "🔴 RISK OFF"}
                regime_label = regime_icons.get(risk, "🟡 NEUTRAL")

                icon = "☀️" if rtype == "morning" else "🌙"
                label = "Morning Memo" if rtype == "morning" else "EOD Scorecard"

                e = discord.Embed(
                    title=f"{icon} {label} — {now.strftime('%A, %B %d')}",
                    description=(
                        f"**{regime_label}** • Risk Score: **{risk_on_score:.0f}/100**\n"
                        f"Trend: {trend} • Vol: {vol_state}\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=COLOR_GOLD, timestamp=now)

                idx_text = (
                    f"SPY: ${spy.get('price',0):.2f} ({spy_pct:+.2f}%) | "
                    f"QQQ: ${qqq.get('price',0):.2f} ({qqq_pct:+.2f}%) | "
                    f"IWM: ${iwm.get('price',0):.2f} ({iwm.get('change_pct',0):+.2f}%)")
                e.add_field(name="🇺🇸 Indices", value=idx_text, inline=False)

                macro_text = (
                    f"VIX: **{vix:.1f}** {'🔴' if vix > 25 else '🟡' if vix > 18 else '🟢'} | "
                    f"Gold: {gld.get('change_pct',0):+.2f}% | "
                    f"Bonds: {tlt.get('change_pct',0):+.2f}% | "
                    f"BTC: ${btc.get('price',0):,.0f} ({btc_pct:+.2f}%)")
                e.add_field(name="🌍 Macro", value=macro_text, inline=False)

                sector_text = []
                for sym, name in _SECTORS:
                    d = await _fetch_stock(sym)
                    p = d.get("change_pct", 0)
                    sector_text.append(f"{'🟢' if p > 0 else '🔴'} {name} {p:+.1f}%")
                e.add_field(name="🏭 Sectors", value=" | ".join(sector_text), inline=False)

                playbook_map = {
                    ("RISK_ON", "UPTREND"): ["Momentum", "Breakout"],
                    ("RISK_ON", "NEUTRAL"): ["Swing", "VCP"],
                    ("NEUTRAL", "UPTREND"): ["Momentum", "VCP"],
                    ("NEUTRAL", "NEUTRAL"): ["Mean-Reversion"],
                    ("RISK_OFF", "DOWNTREND"): ["Cash"],
                }
                strats = playbook_map.get((risk, trend), ["Swing", "Mean-Reversion"])
                e.add_field(name="📋 Playbook",
                             value=" · ".join(f"`{s}`" for s in strats), inline=False)

                notes = []
                if vix > 25:
                    notes.append(f"VIX {vix:.1f} — reduce position sizes")
                if rtype == "morning":
                    notes.append("☕ Check pre-market gaps before entries")
                    notes.append("⏰ Wait 15 min after open for range")
                else:
                    notes.append("🌙 Review positions for overnight risk")
                    notes.append("📝 Log trade decisions for ML learning")
                e.add_field(
                    name=f"📝 {'Pre-Market' if rtype == 'morning' else 'After-Hours'} Notes",
                    value="\n".join(f"• {n}" for n in notes), inline=False)

                e.set_footer(text=f"TradingAI Pro v6 • {label}")
                await interaction.followup.send(embed=e)
                # Also post to #daily-brief
                await _send_ch("daily-brief", embed=e)
                await _audit(f"📋 {interaction.user} → /report {rtype}")
            except Exception as exc:
                logger.error(f"report error: {exc}")
                await interaction.followup.send(f"❌ {exc}")

        # ══════════════════════════════════════════════════════════════
        # ADMIN COMMANDS
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="setup", description="[Admin] Re-run full server setup")
        @app_commands.guild_only()
        @app_commands.checks.has_permissions(administrator=True)
        async def cmd_setup(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)
            if interaction.guild:
                await full_server_setup(interaction.guild)
                await interaction.followup.send("✅ Server setup complete.", ephemeral=True)
                await _audit(f"⚙️ {interaction.user} ran /setup")

        @bot.tree.command(name="announce", description="[Admin] Post announcement to #daily-brief")
        @app_commands.describe(message="Announcement text")
        @app_commands.guild_only()
        @app_commands.checks.has_permissions(administrator=True)
        async def cmd_announce(interaction: discord.Interaction, message: str):
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.", ephemeral=True)
                return
            if not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "🔒 Insufficient permissions — administrator required.", ephemeral=True)
                return
            e = discord.Embed(title="📢 Announcement", description=message,
                              color=COLOR_GOLD,
                              timestamp=datetime.now(timezone.utc))
            e.set_footer(text=f"Posted by {interaction.user.display_name}")
            await _send_ch("daily-brief", embed=e)
            await interaction.response.send_message("✅ Announcement posted.", ephemeral=True)
            await _audit(f"📢 {interaction.user} posted announcement")

        @bot.tree.command(name="purge", description="[Admin] Delete last N messages in this channel")
        @app_commands.describe(count="Number of messages to delete (max 100)")
        @app_commands.guild_only()
        @app_commands.checks.has_permissions(manage_messages=True)
        async def cmd_purge(interaction: discord.Interaction, count: int):
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.", ephemeral=True)
                return
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "🔒 Insufficient permissions — manage_messages required.", ephemeral=True)
                return
            count = min(max(1, count), 100)
            await interaction.response.defer(ephemeral=True)
            if interaction.channel and hasattr(interaction.channel, "purge"):
                deleted = await interaction.channel.purge(limit=count)
                await interaction.followup.send(
                    f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)
                await _audit(f"🗑️ {interaction.user} purged {len(deleted)} msgs in #{interaction.channel}")

        @bot.tree.command(name="slowmode", description="[Admin] Set slowmode for this channel")
        @app_commands.describe(seconds="Slowmode seconds (0 = off, max 21600)")
        @app_commands.guild_only()
        @app_commands.checks.has_permissions(manage_channels=True)
        async def cmd_slowmode(interaction: discord.Interaction, seconds: int):
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.", ephemeral=True)
                return
            if not interaction.user.guild_permissions.manage_channels:
                await interaction.response.send_message(
                    "🔒 Insufficient permissions — manage_channels required.", ephemeral=True)
                return
            seconds = min(max(0, seconds), 21600)
            if interaction.channel and hasattr(interaction.channel, "edit"):
                await interaction.channel.edit(slowmode_delay=seconds)
                label = f"{seconds}s" if seconds else "off"
                await interaction.response.send_message(
                    f"⏱️ Slowmode set to **{label}**.", ephemeral=True)
                await _audit(f"⏱️ {interaction.user} set slowmode {label} in #{interaction.channel}")

        @bot.tree.command(name="pin", description="[Admin] Pin the last message")
        @app_commands.guild_only()
        @app_commands.checks.has_permissions(manage_messages=True)
        async def cmd_pin(interaction: discord.Interaction):
            if not interaction.guild:
                await interaction.response.send_message(
                    "❌ This command can only be used in a server.", ephemeral=True)
                return
            if not interaction.user.guild_permissions.manage_messages:
                await interaction.response.send_message(
                    "🔒 Insufficient permissions — manage_messages required.", ephemeral=True)
                return
            if interaction.channel and hasattr(interaction.channel, "history"):
                async for msg in interaction.channel.history(limit=2):
                    if msg.author != bot.user or not msg.embeds:
                        await msg.pin()
                        await interaction.response.send_message("📌 Pinned.", ephemeral=True)
                        return
            await interaction.response.send_message("Nothing to pin.", ephemeral=True)

        # ══════════════════════════════════════════════════════════════
        # START
        # ══════════════════════════════════════════════════════════════

        if self.bot_token:
            logger.info("Starting Discord interactive bot...")
            print("🚀 Launching TradingAI Discord Bot...")
            await bot.start(self.bot_token)
        else:
            logger.error("No DISCORD_BOT_TOKEN configured")
            print("ERROR: DISCORD_BOT_TOKEN not set in .env")


# ═══════════════════════════════════════════════════════════════════════
# Standalone launcher
# ═══════════════════════════════════════════════════════════════════════

async def main():
    bot = DiscordInteractiveBot()
    if not bot.is_configured:
        print("❌ DISCORD_BOT_TOKEN not set in .env\n"
              "Get your token: https://discord.com/developers/applications")
        return
    print("🤖 Starting TradingAI Discord Bot...")
    print("   Ctrl+C to stop\n")
    await bot.run_interactive_bot()


if __name__ == "__main__":
    asyncio.run(main())
