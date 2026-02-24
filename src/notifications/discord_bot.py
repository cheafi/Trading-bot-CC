"""
TradingAI Pro v5.0 — Institutional-Grade Discord Trading Server Bot
=====================================================================

v5 Upgrades:
  • InsightEngine integration: playbook, trade briefs, risk bulletin
  • Progressive disclosure UX: 7 primary actions
  • Signal cards with EdgeModel (P(T1), EV, R:R) and execution plan
  • Morning memo: What Changed → 3 Levels → Playbook → Top 5 Briefs → Risk Bulletin
  • /market_now command: instant regime + playbook + risk snapshot

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
        embed.add_field("Confidence",
                        f"{'█' * (conf // 10)}{'░' * (10 - conf // 10)} {conf}%")
        embed.add_field("Horizon", str(getattr(signal, "horizon", "")))
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
        strat = getattr(signal, "strategy_id", None)
        if strat:
            embed.add_field("Strategy", f"`{strat}`")

        # ── v5: Edge Model + Execution Plan ──
        fs = getattr(signal, "feature_snapshot", None) or {}
        edge = fs.get("edge_model", {})
        exec_plan = fs.get("execution_plan", {})
        risk_plan = fs.get("risk_plan", {})

        if edge:
            p_t1 = edge.get("p_t1", 0)
            p_stop = edge.get("p_stop", 0)
            ev = edge.get("expected_return_pct", 0)
            sample = edge.get("sample_size", 0)
            cal_label = f"(n={sample})" if sample >= 30 else "(base-rate)"
            embed.add_field(
                "📊 Edge Model",
                f"P(T1): **{p_t1*100:.0f}%** | P(stop): {p_stop*100:.0f}%\n"
                f"EV: **{ev:+.1f}%** | Hold: {edge.get('expected_holding_days', '?')}d\n"
                f"MAE: {edge.get('expected_mae_pct', 0):.1f}% {cal_label}",
                inline=False)

        if exec_plan:
            exec_str = f"Order: `{exec_plan.get('order_type', '?')}`"
            if exec_plan.get("avoid_times"):
                exec_str += f"\n⚠️ Avoid: {', '.join(exec_plan['avoid_times'])}"
            embed.add_field("📐 Execution", exec_str)

        if risk_plan:
            liq = risk_plan.get("liquidity_tier", "?")
            liq_icon = {"A": "✅", "B": "🟡", "C": "🔴"}.get(liq, "?")
            rr_t1 = risk_plan.get("rr_to_t1", 0)
            embed.add_field("🛡️ Risk",
                            f"R:R to T1: **{rr_t1:.1f}** | "
                            f"Liq: {liq_icon}{liq} | "
                            f"{'⚠️ GAP' if risk_plan.get('gap_risk_flag') else '✅ No gap'}")

        risks = getattr(signal, "key_risks", [])
        if risks:
            embed.add_field("⚠️ Risks",
                            "\n".join(f"• {r}" for r in risks[:3]), inline=False)
        embed.set_footer(
            f"TradingAI Pro v5 • {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
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
        e = DiscordEmbed(title="📋 Daily Trading Report",
                         description=report.get("summary", ""), color=COLOR_INFO)
        e.add_field("Signals", str(report.get("signals_count", 0)))
        e.add_field("Trades", str(report.get("trades_count", 0)))
        e.add_field("Win Rate", f"{report.get('win_rate', 0):.1f}%")
        e.add_field("Total P&L", f"{report.get('total_pnl', 0):+.2f}%")
        e.add_field("Best Trade", report.get("best_trade", "N/A"))
        e.add_field("Worst Trade", report.get("worst_trade", "N/A"))
        e.set_footer("TradingAI Bot — End of Day Report")
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
                reasons = self.sig.get("reasons", [])
                why_text = "\n".join(reasons) if reasons else "No specific catalyst identified."
                invalidation = self.sig.get("invalidation", "Break below SMA50")
                earnings_risk = self.sig.get("earnings_risk", "N/A")
                e = discord.Embed(
                    title=f"❓ Why Now — {self.ticker}",
                    color=COLOR_PURPLE)
                e.add_field(name="Setup Reasons", value=why_text, inline=False)
                e.add_field(name="Invalidation", value=f"🛑 {invalidation}")
                e.add_field(name="Earnings Risk", value=f"📅 {earnings_risk}")
                e.add_field(name="Crowding Risk",
                            value=f"Rel Vol: {self.sig.get('rel_vol', 1):.1f}x — "
                                  f"{'⚠️ Crowded' if self.sig.get('rel_vol', 1) > 3 else '✅ Normal'}",
                            inline=False)
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
                    if any("TradingAI Pro v5" in (em.title or "") for em in msg.embeds):
                        return
            e = discord.Embed(
                title="🤖 TradingAI Pro v5 — AI Trading Command Center",
                description=(
                    "Welcome to the AI-powered trading server.\n\n"
                    "**What I do:**\n"
                    "• Scan **US · HK · JP · Crypto** markets 24/7\n"
                    "• AI signals with edge model (P(T1), EV, R:R)\n"
                    "• Regime detection → daily playbook → trade plans\n"
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
                            "**#swing-trades** — pullback entries in trending stocks (2-8wk hold)\n"
                            "**#breakout-setups** — consolidation breaks with volume (1-4wk hold)\n"
                            "**#momentum-alerts** — big movers, whale flow, momentum (days-2wk)\n"
                            "**#daily-brief** — morning memo + EOD report\n"
                            "**#bot-commands** — use all slash commands\n"
                            "**#trading-chat** — discuss anything market-related"),
                        inline=False)
            e.set_footer(text="TradingAI Pro v5 • 24/7 AI Trading • Type /help to begin")
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
        _WATCH_US = ["AAPL","MSFT","GOOGL","AMZN","NVDA","META","TSLA","AMD",
                     "NFLX","CRM","COIN","PLTR","SOFI","NIO","RIVN","MARA",
                     "XYZ","SHOP","ROKU","SNAP","UBER","ABNB","NET","CRWD",
                     "DKNG","SMCI","ARM","AVGO","MU","INTC"]
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

        # ── 2. Market pulse (every 15 min, US hours) ─────────────────
        @tasks.loop(minutes=15)
        async def market_pulse():
            now = datetime.now(timezone.utc)
            if not (13 <= now.hour < 21 and now.weekday() < 5):
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

        # ── 3. Top movers auto-scan (every 30 min, US hours) ─────────
        @tasks.loop(minutes=30)
        async def auto_movers():
            now = datetime.now(timezone.utc)
            if not (13 <= now.hour < 21 and now.weekday() < 5):
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
                await _send_ch("momentum-alerts", embed=e)
                await _audit(f"📡 Auto-movers: {len(big)} stocks ≥ 2%")
            except Exception as exc:
                logger.error(f"auto_movers error: {exc}")

        # ── 4. Sector + Macro snapshot (every 60 min, US hours) ──────
        @tasks.loop(minutes=60)
        async def auto_sector_macro():
            now = datetime.now(timezone.utc)
            if not (13 <= now.hour < 21 and now.weekday() < 5):
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

        # ── 6a. Swing scanner ────────────────────────────────────────
        def _sync_swing_scan(tickers):
            """
            Swing trade scanner — finds pullback entries in trending stocks.
            Criteria: uptrend (SMA50>SMA200-ish, price>SMA50),
            2-7 day pullback that holds key MA, RSI not overbought,
            healthy volume.  Hold target: 2-8 weeks.
            """
            if not _yf:
                return []
            signals = []
            for ticker in tickers:
                try:
                    t = _yf.Ticker(ticker)
                    hist = t.history(period="6mo")
                    if hist.empty or len(hist) < 60:
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
                    })
                except Exception:
                    continue
            return signals

        # ── 6b. Breakout scanner ─────────────────────────────────────
        def _sync_breakout_scan(tickers):
            """
            Breakout scanner — finds consolidation breaks with volume.
            Criteria: tight range (low BB width or narrow 10-day range),
            price breaking above the consolidation high on above-avg volume.
            Hold target: 1-4 weeks.
            """
            if not _yf:
                return []
            signals = []
            for ticker in tickers:
                try:
                    t = _yf.Ticker(ticker)
                    hist = t.history(period="6mo")
                    if hist.empty or len(hist) < 60:
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
                    })
                except Exception:
                    continue
            return signals

        # ── 6c. Momentum scanner ─────────────────────────────────────
        def _sync_momentum_scan(tickers):
            """
            Momentum scanner — finds strong movers for short-term plays.
            Criteria: big move today (>2%), above-avg volume, strong trend.
            Hold target: days to 2 weeks.
            """
            if not _yf:
                return []
            signals = []
            for ticker in tickers:
                try:
                    t = _yf.Ticker(ticker)
                    hist = t.history(period="3mo")
                    if hist.empty or len(hist) < 30:
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
                    })
                except Exception:
                    continue
            return signals

        # ── Legacy wrapper (used by morning brief) ───────────────────
        def _sync_signal_scan(tickers):
            """Combined scan — merges all three scanner types."""
            swing = _sync_swing_scan(tickers)
            breakout = _sync_breakout_scan(tickers)
            momentum = _sync_momentum_scan(tickers)
            combined = swing + breakout + momentum
            combined.sort(key=lambda x: x.get("score", 0), reverse=True)
            return combined

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
                signals = await asyncio.to_thread(_sync_swing_scan, _WATCH_US)
                if not signals:
                    return
                signals.sort(key=lambda x: x["score"], reverse=True)
                top_count = min(5, len(signals))
                header = discord.Embed(
                    title=f"🔄 Swing Trade Scan — {now.strftime('%H:%M UTC')}",
                    description=(
                        f"Scanned {len(_WATCH_US)} tickers • "
                        f"**{len(signals)}** swing setups • "
                        f"Hold: 2-8 weeks"
                    ), color=COLOR_BUY, timestamp=now)
                header.set_footer(text="Pullback entries in trending stocks • Score 0-100")
                await _send_ch("swing-trades", embed=header)
                await asyncio.sleep(0.5)

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
                signals = await asyncio.to_thread(_sync_breakout_scan, _WATCH_US)
                if not signals:
                    return
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
                signals = await asyncio.to_thread(_sync_momentum_scan, _WATCH_US)
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

        # ── 7. Morning brief (runs every 10 min, fires once at ~13:30 UTC / 9:30 ET)
        _morning_posted = set()
        @tasks.loop(minutes=10)
        async def morning_brief():
            """v5 Morning Decision Memo — regime, playbook, top trades, risk bulletin."""
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

                # ── Regime derivation ──
                risk = "risk_off" if (vix > 25 or spy_pct < -1.5) else (
                    "risk_on" if (vix < 18 and spy_pct > 0.3) else "neutral")
                trend = "up" if spy_pct > 0.5 else "down" if spy_pct < -0.5 else "flat"
                vol = "high" if vix > 22 else "low" if vix < 15 else "normal"

                regime_icons = {
                    "risk_on": "🟢 RISK ON", "neutral": "🟡 NEUTRAL", "risk_off": "🔴 RISK OFF"
                }
                regime_label = regime_icons.get(risk, "🟡 NEUTRAL")

                # ── Playbook ──
                playbook_map = {
                    ("risk_on", "up", "low"): ("Trending bull — full offence",
                        ["Momentum", "Breakout", "Trend-Follow"]),
                    ("risk_on", "up", "normal"): ("Mild bull — normal book",
                        ["Momentum", "Swing", "VCP"]),
                    ("risk_on", "flat", "low"): ("Low-vol grind — fade extremes",
                        ["Mean-Reversion", "Swing"]),
                    ("neutral", "up", "normal"): ("Selective bull — pick spots",
                        ["Momentum", "VCP", "Swing"]),
                    ("neutral", "flat", "normal"): ("Chop — reduce size",
                        ["Mean-Reversion", "Swing"]),
                    ("neutral", "down", "normal"): ("Pullback — wait for support",
                        ["Mean-Reversion"]),
                    ("risk_off", "down", "high"): ("Sell-off — capital preservation",
                        ["Cash", "Hedges"]),
                    ("risk_off", "flat", "high"): ("Elevated vol — small positions only",
                        ["Mean-Reversion"]),
                }
                key = (risk, trend, vol)
                stance_text, strategies = playbook_map.get(
                    key, ("Mixed signals — be selective", ["Swing", "Mean-Reversion"]))

                # ═══ EMBED 1: Morning Decision Memo ═══
                e = discord.Embed(
                    title=f"☀️ Morning Decision Memo — {now.strftime('%A, %B %d')}",
                    description=(
                        f"**{regime_label}** • VIX {vix:.1f} • "
                        f"SPY {spy_pct:+.2f}% • QQQ {qqq_pct:+.2f}%\n"
                        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=COLOR_GOLD, timestamp=now)

                # ── What Changed ──
                changes = []
                for sym, pct_val in [("SPY", spy_pct), ("QQQ", qqq_pct)]:
                    if abs(pct_val) > 1.5:
                        changes.append(f"{'📈' if pct_val > 0 else '📉'} **{sym}** {pct_val:+.2f}%")
                if vix > 22:
                    changes.append(f"⚠️ VIX elevated at **{vix:.1f}**")
                btc_pct = btc_data.get("change_pct", 0)
                if abs(btc_pct) > 3:
                    changes.append(f"₿ BTC {'surging' if btc_pct > 0 else 'dumping'} {btc_pct:+.1f}%")
                if not changes:
                    changes.append("No major overnight moves — quiet open expected")
                e.add_field(name="🔄 What Changed",
                            value="\n".join(changes[:5]), inline=False)

                # ── Key Levels ──
                levels = []
                for sym, name, data in [
                    ("SPY", "S&P 500", spy_data),
                    ("QQQ", "Nasdaq", qqq_data),
                    ("IWM", "Russell", iwm_data),
                ]:
                    price = data.get("price", 0)
                    hi = data.get("high", price)
                    lo = data.get("low", price)
                    levels.append(f"**{name}**: ${price:.2f} (R: ${hi:.2f} | S: ${lo:.2f})")
                e.add_field(name="📐 3 Key Levels",
                            value="\n".join(levels), inline=False)

                # ── Today's Playbook ──
                strat_str = " · ".join(f"`{s}`" for s in strategies)
                e.add_field(
                    name="📋 Today's Playbook",
                    value=f"**{stance_text}**\nStrategies: {strat_str}",
                    inline=False)

                # ── Macro snapshot ──
                e.add_field(
                    name="🌍 Macro",
                    value=(
                        f"📉 VIX: **{vix:.1f}** "
                        f"{'🔴' if vix > 25 else '🟡' if vix > 18 else '🟢'} | "
                        f"💵 TLT: {tlt_data.get('change_pct',0):+.2f}% | "
                        f"🥇 Gold: {gold_data.get('change_pct',0):+.2f}% | "
                        f"₿ BTC: {btc_pct:+.2f}%"
                    ), inline=False)

                # Futures
                futures_text = []
                for sym, name in [("ES=F", "S&P"), ("NQ=F", "Nasdaq"), ("YM=F", "Dow")]:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴" if pct < 0 else "⚪"
                    futures_text.append(f"{icon} **{name}**: {pct:+.2f}%")
                e.add_field(name="📈 Futures", value=" | ".join(futures_text), inline=False)

                # Asia close
                asia_lines = []
                for sym, name in _WATCH_ASIA:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0 else "🔴"
                    asia_lines.append(f"{icon} {name}: {pct:+.2f}%")
                e.add_field(name="🌏 Asia Close", value=" | ".join(asia_lines), inline=False)

                # ── Risk Bulletin ──
                risks = []
                if vix > 25:
                    risks.append(f"🔴 VIX {vix:.1f} — reduce position sizes to 50%")
                if vix > 18 and spy_pct < -1:
                    risks.append("⚠️ Selling into vol — stop discipline critical")
                if abs(qqq_pct - spy_pct) > 1.5:
                    risks.append(f"⚠️ QQQ/SPY divergence {qqq_pct-spy_pct:+.1f}% — rotation risk")
                if not risks:
                    risks.append("✅ No critical risk flags")
                e.add_field(name="🛡️ Risk Bulletin",
                            value="\n".join(risks), inline=False)

                # ── Sizing ──
                if risk == "risk_off":
                    sizing = "⚠️ **25-50%** of normal • Wider stops"
                elif risk == "neutral":
                    sizing = "🟡 **75%** of normal • Standard stops"
                else:
                    sizing = "🟢 **100%** full size • Tight stops"
                e.add_field(name="📏 Sizing Guidance", value=sizing, inline=False)

                e.set_footer(text="☀️ v5 Decision Memo • /market_now for real-time • Good luck!")
                await _send_ch("daily-brief", embed=e)

                # ═══ EMBED 2: Top Trades Preview ═══
                try:
                    signals = await asyncio.to_thread(_sync_signal_scan, _WATCH_US[:15])
                    if signals:
                        signals.sort(key=lambda x: x["score"], reverse=True)
                        e2 = discord.Embed(
                            title="🎯 Top 5 Trade Ideas",
                            description="Pre-market scan • sorted by conviction",
                            color=COLOR_INFO, timestamp=now)
                        for i, sig in enumerate(signals[:5], 1):
                            arrow = "🟢" if sig["direction"] == "LONG" else "🔴"
                            rr = sig.get("rr_ratio", 0)
                            stype = sig.get("setup_type", "SIGNAL")
                            e2.add_field(
                                name=f"{arrow} #{i} {sig['ticker']} — ${sig['price']:.2f}  [{stype}]",
                                value=(
                                    f"Score: **{sig['score']}** | "
                                    f"R:R: **{rr:.1f}:1** | "
                                    f"Stop: ${sig.get('stop',0):.2f} | "
                                    f"Target: ${sig.get('target',0):.2f}\n"
                                    f"{sig['reasons'][0] if sig.get('reasons') else ''}"
                                ), inline=False)
                        e2.set_footer(text="/scan for full list • Setups in #swing-trades #breakout-setups #momentum-alerts")
                        await _send_ch("daily-brief", embed=e2)
                except Exception as exc:
                    logger.warning(f"morning_brief trade preview: {exc}")

                await _audit("☀️ v5 Morning Decision Memo posted")
            except Exception as exc:
                logger.error(f"morning_brief error: {exc}")

        # ── 8. EOD report (runs every 10 min, fires once at ~20:10 UTC / 4:10 PM ET)
        _eod_posted = set()
        @tasks.loop(minutes=10)
        async def eod_report():
            """Enhanced EOD report with sector heat map and market breadth."""
            now = datetime.now(timezone.utc)
            today = now.strftime("%Y-%m-%d")
            if today in _eod_posted:
                return
            if not (now.weekday() < 5 and now.hour == 20 and 5 <= now.minute <= 20):
                return
            _eod_posted.add(today)
            try:
                e = discord.Embed(
                    title=f"🌙 End-of-Day Scorecard — {now.strftime('%A, %B %d')}",
                    description="Markets closed. Here's your daily performance review.",
                    color=COLOR_PURPLE, timestamp=now)

                # Index performance with visual bars
                index_lines = []
                for sym, name in _INDICES:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    icon = "🟢" if pct > 0.3 else "🔴" if pct < -0.3 else "⚪"
                    index_lines.append(
                        f"{icon} **{name}**: ${data.get('price', 0):,.2f} ({pct:+.2f}%) {_bar(pct, 6)}")
                e.add_field(name="📊 Indices", value="\n".join(index_lines), inline=False)

                # Sector heat map
                sector_data = []
                for sym, name in _SECTORS:
                    data = await _fetch_stock(sym)
                    pct = data.get("change_pct", 0)
                    sector_data.append((name, pct))
                sector_data.sort(key=lambda x: x[1], reverse=True)

                heat_lines = []
                for name, pct in sector_data:
                    icon = "🟢" if pct > 0.5 else "🔴" if pct < -0.5 else "⚪"
                    heat_lines.append(f"{icon} {name}: {pct:+.2f}%")
                e.add_field(name="🏭 Sector Heat Map",
                            value="\n".join(heat_lines[:8]),
                            inline=False)

                # Watchlist movers
                results = []
                for t in _WATCH_US[:20]:
                    data = await _fetch_stock(t)
                    if "error" not in data:
                        results.append(data)
                results.sort(key=lambda x: x.get("change_pct", 0), reverse=True)

                if results:
                    # Winners
                    winners = [r for r in results[:3] if r.get("change_pct", 0) > 0]
                    losers = [r for r in results[-3:] if r.get("change_pct", 0) < 0]
                    if winners:
                        win_text = "\n".join(
                            f"🏆 **{r['ticker']}** {r.get('change_pct', 0):+.2f}% (${r.get('price', 0):.2f})"
                            for r in winners)
                        e.add_field(name="🏆 Top Movers", value=win_text)
                    if losers:
                        lose_text = "\n".join(
                            f"📉 **{r['ticker']}** {r.get('change_pct', 0):+.2f}% (${r.get('price', 0):.2f})"
                            for r in losers)
                        e.add_field(name="📉 Laggards", value=lose_text)

                    # Market breadth (% green in watchlist)
                    green_count = sum(1 for r in results if r.get("change_pct", 0) > 0)
                    breadth_pct = (green_count / len(results)) * 100
                    breadth_icon = "🟢" if breadth_pct > 65 else "🔴" if breadth_pct < 35 else "🟡"
                    e.add_field(name="📊 Breadth",
                                value=f"{breadth_icon} {breadth_pct:.0f}% green ({green_count}/{len(results)})")

                # VIX check
                vix_data = await _fetch_stock("^VIX")
                vix = vix_data.get("price", 0)
                vix_icon = "🔴" if vix > 25 else "🟡" if vix > 18 else "🟢"
                e.add_field(name="📉 VIX Close", value=f"{vix_icon} {vix:.1f}")

                e.set_footer(text="🌙 Auto EOD Report • See you tomorrow! • Use /recap for detailed stats")
                await _send_ch("daily-brief", embed=e)
                await _audit("🌙 EOD report v4 auto-posted")
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

        # ── 10. Whale / unusual volume alert (every 45 min, US hours) ─
        @tasks.loop(minutes=45)
        async def auto_whale_scan():
            now = datetime.now(timezone.utc)
            if not (13 <= now.hour < 21 and now.weekday() < 5):
                return
            try:
                def _sync_whale_scan():
                    if not _yf:
                        return []
                    whales = []
                    for ticker in _WATCH_US:
                        try:
                            t = _yf.Ticker(ticker)
                            hist = t.history(period="1mo")
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
                await _send_ch("momentum-alerts", embed=e)
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

        # ── 12. Bot health check to #bot-status (every 30 min) ───────
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
                    f"{'✅' if auto_movers.is_running() else '❌'} Auto Movers\n"
                    f"{'✅' if auto_swing_scan.is_running() else '❌'} Swing Scan\n"
                    f"{'✅' if auto_breakout_scan.is_running() else '❌'} Breakout Scan\n"
                    f"{'✅' if auto_momentum_scan.is_running() else '❌'} Momentum Scan\n"
                    f"{'✅' if auto_crypto.is_running() else '❌'} Crypto\n"
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
        @auto_swing_scan.before_loop
        async def _w6a(): await bot.wait_until_ready()
        @auto_breakout_scan.before_loop
        async def _w6b(): await bot.wait_until_ready()
        @auto_momentum_scan.before_loop
        async def _w6c(): await bot.wait_until_ready()
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
            all_tasks = [update_presence, market_pulse, auto_movers,
                         auto_sector_macro, auto_crypto,
                         auto_swing_scan, auto_breakout_scan, auto_momentum_scan,
                         morning_brief, eod_report, asia_preview,
                         auto_whale_scan, weekly_recap, health_check]
            for t in all_tasks:
                if not t.is_running():
                    t.start()
            print(f"   🔄 Started {len(all_tasks)} auto-pilot tasks")
            await _audit(f"🤖 Bot started as {bot.user} — {len(all_tasks)} tasks running")

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

        # ── /market_now — v5 institutional regime + playbook snapshot ──
        @bot.tree.command(name="market_now",
                          description="Instant regime · playbook · risk snapshot (v5)")
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.user.id)
        async def cmd_market_now(interaction: discord.Interaction):
            await interaction.response.defer()
            try:
                # ── Fetch regime inputs ──
                spy_data = await _fetch_stock("SPY")
                qqq_data = await _fetch_stock("QQQ")
                vix_data = await _fetch_stock("^VIX")
                tlt_data = await _fetch_stock("TLT")
                btc_data = await _fetch_stock("BTC-USD")
                gold_data = await _fetch_stock("GLD")

                vix = vix_data.get("price", 0)
                spy_pct = spy_data.get("change_pct", 0)
                qqq_pct = qqq_data.get("change_pct", 0)

                # ── Derive regime ──
                risk = "risk_off" if (vix > 25 or spy_pct < -1.5) else (
                    "risk_on" if (vix < 18 and spy_pct > 0.3) else "neutral")
                trend = "up" if spy_pct > 0.5 else "down" if spy_pct < -0.5 else "flat"
                vol = "high" if vix > 22 else "low" if vix < 15 else "normal"

                regime_icons = {
                    "risk_on": "🟢 RISK ON", "neutral": "🟡 NEUTRAL", "risk_off": "🔴 RISK OFF"
                }
                regime_label = regime_icons.get(risk, "🟡 NEUTRAL")

                # ── Playbook logic (mirrors InsightEngine) ──
                playbook_map = {
                    ("risk_on", "up", "low"): ("Trending bull — full offence",
                        ["Momentum", "Breakout", "Trend-Follow"]),
                    ("risk_on", "up", "normal"): ("Mild bull — normal book",
                        ["Momentum", "Swing", "VCP"]),
                    ("risk_on", "flat", "low"): ("Low-vol grind — fade extremes",
                        ["Mean-Reversion", "Swing"]),
                    ("neutral", "up", "normal"): ("Selective bull — pick spots",
                        ["Momentum", "VCP", "Swing"]),
                    ("neutral", "flat", "normal"): ("Chop — reduce size",
                        ["Mean-Reversion", "Swing"]),
                    ("neutral", "down", "normal"): ("Pullback — wait for support",
                        ["Mean-Reversion"]),
                    ("risk_off", "down", "high"): ("Sell-off — capital preservation",
                        ["Cash", "Hedges"]),
                    ("risk_off", "flat", "high"): ("Elevated vol — small positions only",
                        ["Mean-Reversion"]),
                }
                key = (risk, trend, vol)
                stance_text, strategies = playbook_map.get(
                    key, ("Mixed signals — be selective", ["Swing", "Mean-Reversion"]))

                # ── Build embed ──
                now_ts = datetime.now(timezone.utc)
                e = discord.Embed(
                    title=f"🎛️ Market Now — {now_ts.strftime('%H:%M UTC')}",
                    description=(
                        f"**{regime_label}** • VIX {vix:.1f} • "
                        f"SPY {spy_pct:+.2f}% • QQQ {qqq_pct:+.2f}%"
                    ),
                    color=COLOR_BUY if risk == "risk_on" else (
                        COLOR_SELL if risk == "risk_off" else COLOR_INFO),
                    timestamp=now_ts)

                # Section 1: Regime
                e.add_field(
                    name="📊 Regime",
                    value=(
                        f"Risk: **{risk.replace('_',' ').title()}** | "
                        f"Trend: **{trend.title()}** | Vol: **{vol.title()}**"
                    ), inline=False)

                # Section 2: Playbook
                strat_str = " · ".join(f"`{s}`" for s in strategies)
                e.add_field(
                    name="📋 Today's Playbook",
                    value=f"**{stance_text}**\nStrategies: {strat_str}",
                    inline=False)

                # Section 3: Key Levels
                levels = []
                for sym, name, data in [
                    ("SPY", "S&P 500", spy_data), ("QQQ", "Nasdaq", qqq_data)
                ]:
                    price = data.get("price", 0)
                    hi = data.get("high", price)
                    lo = data.get("low", price)
                    levels.append(f"**{name}**: ${price:.2f} (R: ${hi:.2f} | S: ${lo:.2f})")
                e.add_field(name="📐 Key Levels",
                            value="\n".join(levels), inline=False)

                # Section 4: Macro snapshot
                e.add_field(
                    name="🌍 Macro",
                    value=(
                        f"📉 VIX: **{vix:.1f}** "
                        f"{'🔴' if vix > 25 else '🟡' if vix > 18 else '🟢'}\n"
                        f"💵 TLT: ${tlt_data.get('price',0):.2f} "
                        f"({tlt_data.get('change_pct',0):+.2f}%)\n"
                        f"🥇 Gold: ${gold_data.get('price',0):.2f} "
                        f"({gold_data.get('change_pct',0):+.2f}%)\n"
                        f"₿ BTC: ${btc_data.get('price',0):,.0f} "
                        f"({btc_data.get('change_pct',0):+.2f}%)"
                    ), inline=False)

                # Section 5: Risk Bulletin
                risks = []
                if vix > 25:
                    risks.append(f"🔴 VIX at {vix:.1f} — reduce position sizes")
                if vix > 18 and spy_pct < -1:
                    risks.append("⚠️ Selling into elevated vol — stop discipline critical")
                if abs(qqq_pct - spy_pct) > 1.5:
                    risks.append(f"⚠️ QQQ/SPY divergence {qqq_pct-spy_pct:+.1f}% — rotation risk")
                if not risks:
                    risks.append("✅ No critical risk flags")
                e.add_field(name="🛡️ Risk Bulletin",
                            value="\n".join(risks), inline=False)

                # Section 6: Sizing guidance
                if risk == "risk_off":
                    sizing = "⚠️ **25-50%** of normal size • Wider stops"
                elif risk == "neutral":
                    sizing = "🟡 **75%** of normal size • Standard stops"
                else:
                    sizing = "🟢 **100%** full size OK • Tight stops"
                e.add_field(name="📏 Position Sizing", value=sizing, inline=False)

                e.set_footer(text="TradingAI Pro v5 • /scan /morning /ai <ticker> for trades")
                await interaction.followup.send(embed=e)
                await _audit(f"🎛️ {interaction.user} → /market_now ({regime_label})")
            except Exception as exc:
                logger.error(f"market_now error: {exc}")
                await interaction.followup.send(f"❌ {exc}")

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
                def _sync_news():
                    t = _yf.Ticker(ticker.upper())
                    return t.news[:5] if t.news else []
                news = await asyncio.to_thread(_sync_news)
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
                def _sync_analyze():
                    t = _yf.Ticker(ticker.upper())
                    return t.history(period="3mo")
                hist = await asyncio.to_thread(_sync_analyze)
                if hist.empty:
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
                def _sync_advise():
                    t = _yf.Ticker(ticker.upper())
                    return t.history(period="3mo")
                hist = await asyncio.to_thread(_sync_advise)
                if hist.empty:
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
                def _sync_levels():
                    t = _yf.Ticker(ticker.upper())
                    return t.history(period="6mo")
                hist = await asyncio.to_thread(_sync_levels)
                if hist.empty:
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

        @bot.tree.command(name="why", description="Why is a stock moving?")
        @app_commands.describe(ticker="Stock symbol")
        @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
        async def cmd_why(interaction: discord.Interaction, ticker: str):
            await interaction.response.defer()
            d = await _fetch_stock(ticker)
            pct = d.get("change_pct", 0)
            direction = "up" if pct > 0 else "down"
            e = discord.Embed(title=f"❓ Why is {ticker.upper()} {direction} {abs(pct):.1f}%?",
                              color=COLOR_BUY if pct > 0 else COLOR_SELL)
            e.add_field(name="Quick Check", inline=False,
                        value=f"`/news {ticker}` · `/analyze {ticker}` · `/ai {ticker}`")
            await interaction.followup.send(embed=e)

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

        @bot.tree.command(name="portfolio", description="View portfolio dashboard")
        async def cmd_portfolio(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="💼 Portfolio Dashboard", color=COLOR_INFO)
            e.add_field(name="Mode", value="📝 Paper Trading")
            e.add_field(name="Broker", value="Alpaca (Paper)")
            e.add_field(name="📝 Quick Actions", inline=False,
                        value="`/buy AAPL 10` · `/sell AAPL 10` · `/positions` · `/pnl`")
            await interaction.followup.send(embed=e)

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

        @bot.tree.command(name="pnl", description="Today's P&L")
        async def cmd_pnl(interaction: discord.Interaction):
            e = discord.Embed(title="💵 Today's P&L", description="$0.00 (0.00%)",
                              color=COLOR_INFO)
            e.add_field(name="Trades", value="0")
            e.add_field(name="Win Rate", value="N/A")
            e.add_field(name="Realized", value="$0.00")
            await interaction.response.send_message(embed=e)

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

        @bot.tree.command(name="stats", description="Trading statistics")
        async def cmd_stats(interaction: discord.Interaction):
            e = discord.Embed(title="📊 Trading Statistics", color=COLOR_INFO)
            for k, v in [("Trades","0"),("Win Rate","N/A"),("PF","N/A"),
                         ("Avg Win","N/A"),("Avg Loss","N/A"),("Max DD","N/A")]:
                e.add_field(name=k, value=v)
            e.add_field(name="💡", value="Start trading to build stats!", inline=False)
            await interaction.response.send_message(embed=e)

        # ══════════════════════════════════════════════════════════════
        # SLASH COMMANDS — Tools
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="backtest", description="Backtest a strategy")
        @app_commands.describe(ticker="Symbol", period="1mo, 3mo, 6mo, 1y, 2y")
        @app_commands.checks.cooldown(1, 15, key=lambda i: i.user.id)
        async def cmd_backtest(interaction: discord.Interaction,
                                ticker: str, period: str = "1y"):
            await interaction.response.defer()
            e = discord.Embed(title=f"📈 Backtest — {ticker.upper()} ({period})",
                              description="⏳ Running...", color=COLOR_INFO)
            e.add_field(name="Strategy", value="Momentum + MR")
            e.add_field(name="Period", value=period)
            e.add_field(name="Output", value="#backtesting")
            await interaction.followup.send(embed=e)
            await _audit(f"📈 {interaction.user} → /backtest {ticker} {period}")

        @bot.tree.command(name="watchlist", description="Your watchlist")
        async def cmd_watchlist(interaction: discord.Interaction):
            e = discord.Embed(title="👀 Watchlist",
                              description="Empty. Use `/alert` to add tickers.",
                              color=COLOR_INFO)
            await interaction.response.send_message(embed=e)

        @bot.tree.command(name="alert", description="Set a price alert")
        @app_commands.describe(ticker="Symbol", condition="above or below", price="Target $")
        async def cmd_alert(interaction: discord.Interaction,
                            ticker: str, condition: str, price: float):
            e = discord.Embed(
                title=f"🔔 Alert Set — {ticker.upper()}",
                description=f"When **{condition}** **${price:.2f}** → notified in #alerts",
                color=COLOR_WARN)
            await interaction.response.send_message(embed=e)

        @bot.tree.command(name="daily", description="Daily market summary")
        @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
        async def cmd_daily(interaction: discord.Interaction):
            await interaction.response.defer()
            e = discord.Embed(title="📋 Daily Summary",
                              description=datetime.now(timezone.utc).strftime("%A, %B %d, %Y"),
                              color=COLOR_INFO)
            for sym, name in [("SPY","S&P 500"),("QQQ","Nasdaq"),("BTC-USD","Bitcoin")]:
                data = await _fetch_stock(sym)
                e.add_field(name=name,
                            value=f"${data.get('price',0):.2f} ({data.get('change_pct',0):+.2f}%)")
            e.add_field(name="📝", value="Full reports → #daily-brief", inline=False)
            await interaction.followup.send(embed=e)

        # ══════════════════════════════════════════════════════════════
        # ADMIN COMMANDS
        # ══════════════════════════════════════════════════════════════

        @bot.tree.command(name="setup", description="[Admin] Re-run full server setup")
        @app_commands.checks.has_permissions(administrator=True)
        async def cmd_setup(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True)
            if interaction.guild:
                await full_server_setup(interaction.guild)
                await interaction.followup.send("✅ Server setup complete.", ephemeral=True)
                await _audit(f"⚙️ {interaction.user} ran /setup")

        @bot.tree.command(name="announce", description="[Admin] Post announcement to #daily-brief")
        @app_commands.describe(message="Announcement text")
        @app_commands.checks.has_permissions(administrator=True)
        async def cmd_announce(interaction: discord.Interaction, message: str):
            e = discord.Embed(title="📢 Announcement", description=message,
                              color=COLOR_GOLD,
                              timestamp=datetime.now(timezone.utc))
            e.set_footer(text=f"Posted by {interaction.user.display_name}")
            await _send_ch("daily-brief", embed=e)
            await interaction.response.send_message("✅ Announcement posted.", ephemeral=True)
            await _audit(f"📢 {interaction.user} posted announcement")

        @bot.tree.command(name="purge", description="[Admin] Delete last N messages in this channel")
        @app_commands.describe(count="Number of messages to delete (max 100)")
        @app_commands.checks.has_permissions(manage_messages=True)
        async def cmd_purge(interaction: discord.Interaction, count: int):
            count = min(max(1, count), 100)
            await interaction.response.defer(ephemeral=True)
            if interaction.channel and hasattr(interaction.channel, "purge"):
                deleted = await interaction.channel.purge(limit=count)
                await interaction.followup.send(
                    f"🗑️ Deleted {len(deleted)} messages.", ephemeral=True)
                await _audit(f"🗑️ {interaction.user} purged {len(deleted)} msgs in #{interaction.channel}")

        @bot.tree.command(name="slowmode", description="[Admin] Set slowmode for this channel")
        @app_commands.describe(seconds="Slowmode seconds (0 = off, max 21600)")
        @app_commands.checks.has_permissions(manage_channels=True)
        async def cmd_slowmode(interaction: discord.Interaction, seconds: int):
            seconds = min(max(0, seconds), 21600)
            if interaction.channel and hasattr(interaction.channel, "edit"):
                await interaction.channel.edit(slowmode_delay=seconds)
                label = f"{seconds}s" if seconds else "off"
                await interaction.response.send_message(
                    f"⏱️ Slowmode set to **{label}**.", ephemeral=True)
                await _audit(f"⏱️ {interaction.user} set slowmode {label} in #{interaction.channel}")

        @bot.tree.command(name="pin", description="[Admin] Pin the last message")
        @app_commands.checks.has_permissions(manage_messages=True)
        async def cmd_pin(interaction: discord.Interaction):
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
