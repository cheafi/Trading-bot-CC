"""
TradingAI Bot — Institutional-Grade Stock Writer (v4)

Generates professional equity research reports modeled on:
  • Goldman Sachs "Conviction Buy" format
  • Bridgewater macro overlays
  • Tradytics-style data visualization language

Sections:
  1. Verdict + Price Target
  2. Why Now (3 bullets, fact-anchored)
  3. Technical Setup (chart pattern, key levels, momentum)
  4. Fundamental Snapshot (if available: P/E, revenue growth, margins)
  5. Risk Factors + Invalidation
  6. Position Sizing Suggestion
  7. Event Calendar (earnings, ex-div, FOMC)

Every claim must cite data (price, RSI value, date).
No hallucinated forward guidance — only mechanical inference.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


class StockWriter:
    """
    Composes institutional-quality stock reports from raw data.
    No GPT required — pure template + data approach.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def generate_report(
        self,
        ticker: str,
        price_data: Dict[str, Any],
        technicals: Dict[str, Any],
        fundamentals: Optional[Dict[str, Any]] = None,
        signal: Optional[Dict[str, Any]] = None,
        news: Optional[List[str]] = None,
    ) -> str:
        """
        Generate a full institutional report as formatted Markdown.

        Args:
            ticker: Stock symbol
            price_data: Current price info (price, change_pct, high52, low52, volume)
            technicals: Technical indicators (rsi, sma20, sma50, sma200, atr, adx, macd, bbands)
            fundamentals: Optional financial data (pe, eps, revenue_growth, margins, market_cap)
            signal: Optional signal data (direction, score, target, stop, rr_ratio, reasons)
            news: Optional recent headlines
        """
        sections = []

        # ── Header ──
        price = price_data.get("price", 0)
        pct = price_data.get("change_pct", 0)
        sections.append(self._header(ticker, price, pct, signal))

        # ── 1. Verdict ──
        sections.append(self._verdict(ticker, price, signal, technicals))

        # ── 2. Why Now ──
        sections.append(self._why_now(ticker, price, technicals, signal))

        # ── 3. Technical Setup ──
        sections.append(self._technical_setup(ticker, price, price_data, technicals))

        # ── 4. Fundamentals ──
        if fundamentals:
            sections.append(self._fundamentals(ticker, fundamentals))

        # ── 5. Risk Factors ──
        sections.append(self._risk_factors(ticker, price, technicals, signal))

        # ── 6. Position Sizing ──
        sections.append(self._position_sizing(price, signal))

        # ── 7. News & Events ──
        if news:
            sections.append(self._news_section(news))

        # ── Footer ──
        sections.append(self._footer())

        return "\n\n".join(sections)

    # ────────────────────────────────────────────────────────────

    def _header(self, ticker: str, price: float, pct: float,
                signal: Optional[Dict]) -> str:
        direction = signal.get("direction", "N/A") if signal else "N/A"
        score = signal.get("score", "N/A") if signal else "N/A"
        icon = "🟢" if direction == "LONG" else "🔴" if direction == "SHORT" else "⚪"
        return (
            f"# {icon} {ticker} — ${price:.2f} ({pct:+.2f}%)\n"
            f"**Signal:** {direction} | **Score:** {score}/100 | "
            f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}"
        )

    def _verdict(self, ticker: str, price: float,
                 signal: Optional[Dict], technicals: Dict) -> str:
        rsi = technicals.get("rsi", 50)
        sma20 = technicals.get("sma20", price)
        sma50 = technicals.get("sma50", price)

        if signal and signal.get("score", 0) >= 75:
            verdict = "**CONVICTION BUY**" if signal["direction"] == "LONG" else "**CONVICTION SHORT**"
        elif signal and signal.get("score", 0) >= 60:
            verdict = "**BUY**" if signal["direction"] == "LONG" else "**SHORT**"
        else:
            verdict = "**NEUTRAL — WATCH**"

        target = signal.get("target", price * 1.10) if signal else price * 1.10
        stop = signal.get("stop", price * 0.95) if signal else price * 0.95
        rr = signal.get("rr_ratio", 2.0) if signal else 2.0

        return (
            f"## 🎯 Verdict: {verdict}\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| **Price Target** | ${target:.2f} |\n"
            f"| **Stop Loss** | ${stop:.2f} |\n"
            f"| **R:R Ratio** | {rr:.1f}:1 |\n"
            f"| **RSI** | {rsi:.0f} |\n"
            f"| **Trend** | {'Bullish' if price > sma50 else 'Bearish'} (price {'>' if price > sma20 else '<'} SMA20) |"
        )

    def _why_now(self, ticker: str, price: float,
                 technicals: Dict, signal: Optional[Dict]) -> str:
        reasons = []
        sma20 = technicals.get("sma20", price)
        sma50 = technicals.get("sma50", price)
        rsi = technicals.get("rsi", 50)
        rel_vol = technicals.get("rel_vol", 1)

        if price > sma20 > sma50:
            reasons.append(
                f"📈 **Trend alignment**: Price (${price:.2f}) > SMA20 (${sma20:.2f}) > SMA50 (${sma50:.2f}) — "
                f"all moving averages stacked bullish"
            )
        elif price < sma20 < sma50:
            reasons.append(
                f"📉 **Bearish structure**: Price < SMA20 < SMA50 — downtrend intact"
            )

        if 40 <= rsi <= 60:
            reasons.append(f"⚡ **RSI reset**: At {rsi:.0f}, momentum has room to expand in either direction")
        elif rsi > 70:
            reasons.append(f"⚠️ **RSI extended**: At {rsi:.0f}, momentum is stretched — watch for pullback")
        elif rsi < 30:
            reasons.append(f"🟢 **RSI oversold**: At {rsi:.0f}, potential mean-reversion setup")

        if rel_vol > 1.5:
            reasons.append(
                f"📊 **Volume confirmation**: Relative volume {rel_vol:.1f}x average — "
                f"institutional participation likely"
            )

        if signal and signal.get("reasons"):
            for r in signal["reasons"][:2]:
                reasons.append(f"• {r}")

        if not reasons:
            reasons.append("No strong catalyst identified — monitor for setup development")

        return "## ❓ Why Now?\n" + "\n".join(reasons[:4])

    def _technical_setup(self, ticker: str, price: float,
                         price_data: Dict, technicals: Dict) -> str:
        sma20 = technicals.get("sma20", 0)
        sma50 = technicals.get("sma50", 0)
        sma200 = technicals.get("sma200", 0)
        rsi = technicals.get("rsi", 50)
        atr = technicals.get("atr", 0)
        atr_pct = (atr / price * 100) if price > 0 and atr else 0
        adx = technicals.get("adx", 0)
        high52 = price_data.get("high52", 0)
        low52 = price_data.get("low52", 0)

        # Position within 52w range
        range_width = high52 - low52 if high52 > low52 else 1
        range_pct = ((price - low52) / range_width) * 100

        return (
            f"## 📊 Technical Setup\n"
            f"| Indicator | Value | Signal |\n"
            f"|-----------|-------|--------|\n"
            f"| SMA 20 | ${sma20:.2f} | {'✅ Above' if price > sma20 else '❌ Below'} |\n"
            f"| SMA 50 | ${sma50:.2f} | {'✅ Above' if price > sma50 else '❌ Below'} |\n"
            f"| SMA 200 | ${sma200:.2f} | {'✅ Above' if price > sma200 else '❌ Below'} |\n"
            f"| RSI (14) | {rsi:.0f} | {'🔴 Overbought' if rsi > 70 else '🟢 Oversold' if rsi < 30 else '⚪ Neutral'} |\n"
            f"| ATR (14) | ${atr:.2f} ({atr_pct:.1f}%) | {'High vol' if atr_pct > 3 else 'Low vol'} |\n"
            f"| ADX | {adx:.0f} | {'Strong trend' if adx > 25 else 'Weak/range'} |\n"
            f"| 52w Range | ${low52:.2f} — ${high52:.2f} | {range_pct:.0f}% from low |\n"
        )

    def _fundamentals(self, ticker: str, funda: Dict) -> str:
        pe = funda.get("pe", "N/A")
        eps = funda.get("eps", "N/A")
        rev_growth = funda.get("revenue_growth", "N/A")
        margin = funda.get("profit_margin", "N/A")
        mcap = funda.get("market_cap", 0)
        mcap_str = f"${mcap / 1e9:.1f}B" if mcap > 1e9 else f"${mcap / 1e6:.0f}M"

        pe_str = f"{pe:.1f}" if isinstance(pe, (int, float)) else str(pe)
        eps_str = f"${eps:.2f}" if isinstance(eps, (int, float)) else str(eps)
        rev_str = f"{rev_growth:.1%}" if isinstance(rev_growth, (int, float)) else str(rev_growth)
        margin_str = f"{margin:.1%}" if isinstance(margin, (int, float)) else str(margin)

        return (
            f"## 💰 Fundamental Snapshot\n"
            f"| Metric | Value |\n"
            f"|--------|-------|\n"
            f"| **Market Cap** | {mcap_str} |\n"
            f"| **P/E** | {pe_str} |\n"
            f"| **EPS** | {eps_str} |\n"
            f"| **Rev Growth** | {rev_str} |\n"
            f"| **Profit Margin** | {margin_str} |"
        )

    def _risk_factors(self, ticker: str, price: float,
                      technicals: Dict, signal: Optional[Dict]) -> str:
        risks = []
        rsi = technicals.get("rsi", 50)
        atr_pct = technicals.get("atr", 0) / price * 100 if price > 0 else 0
        rel_vol = technicals.get("rel_vol", 1)

        if rsi > 75:
            risks.append("🔴 **Overbought**: RSI above 75 — high probability of pullback")
        if rsi < 25:
            risks.append("🔴 **Oversold capitulation**: RSI below 25 — falling knife risk")
        if atr_pct > 4:
            risks.append(f"⚠️ **High volatility**: ATR at {atr_pct:.1f}% — wide stops needed")
        if rel_vol > 3:
            risks.append(f"⚠️ **Crowded trade**: Rel vol {rel_vol:.1f}x — possible reversal setup")

        if signal:
            rr = signal.get("rr_ratio", 0)
            if rr < 1.5:
                risks.append(f"🔴 **Poor R:R**: {rr:.1f}:1 — below 1.5:1 minimum threshold")
            invalidation = signal.get("invalidation", "")
            if invalidation:
                risks.append(f"🛑 **Invalidation**: {invalidation}")

        if not risks:
            risks.append("✅ No major red flags identified")

        return "## ⚠️ Risk Factors\n" + "\n".join(risks)

    def _position_sizing(self, price: float, signal: Optional[Dict]) -> str:
        stop = signal.get("stop", price * 0.95) if signal else price * 0.95
        risk_per_share = abs(price - stop)
        accounts = [
            ("$10K Account", 10000, 100),
            ("$25K Account", 25000, 250),
            ("$100K Account", 100000, 1000),
        ]
        rows = []
        for name, capital, risk_dollar in accounts:
            shares = int(risk_dollar / risk_per_share) if risk_per_share > 0 else 0
            pos_value = shares * price
            pct_of_capital = (pos_value / capital) * 100 if capital > 0 else 0
            rows.append(
                f"| {name} | ${risk_dollar} | {shares} | ${pos_value:,.0f} | {pct_of_capital:.0f}% |"
            )

        return (
            f"## 📐 Position Sizing (1% risk)\n"
            f"Stop distance: ${risk_per_share:.2f} ({risk_per_share / price * 100:.1f}%)\n\n"
            f"| Account | Risk $ | Shares | Value | % Capital |\n"
            f"|---------|--------|--------|-------|-----------|\n"
            + "\n".join(rows)
        )

    def _news_section(self, news: List[str]) -> str:
        lines = [f"• {h}" for h in news[:5]]
        return "## 📰 Recent Headlines\n" + "\n".join(lines)

    def _footer(self) -> str:
        return (
            "---\n"
            "*This report is auto-generated by TradingAI Bot v4. "
            "It is not financial advice. All claims reference specific data points. "
            "Past performance does not guarantee future results.*"
        )


class DiscordReportFormatter:
    """
    Formats StockWriter reports for Discord embeds (max 4096 chars).
    Splits into multiple embeds if needed.
    """

    @staticmethod
    def to_embeds(report_md: str, ticker: str, color: int = 0x2979FF) -> list:
        """Convert Markdown report to Discord embed(s)."""
        # Discord embed description limit is 4096 chars
        # Field value limit is 1024 chars
        MAX_DESC = 4000
        chunks = []
        current = ""

        for line in report_md.split("\n"):
            if len(current) + len(line) + 1 > MAX_DESC:
                chunks.append(current)
                current = line
            else:
                current += "\n" + line if current else line
        if current:
            chunks.append(current)

        embeds = []
        for i, chunk in enumerate(chunks):
            title = f"📋 {ticker} Research Report" if i == 0 else f"📋 {ticker} (cont.)"
            embeds.append({
                "title": title,
                "description": chunk,
                "color": color,
            })

        return embeds
