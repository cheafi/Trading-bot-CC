# D) Daily Report Format & Example

## Report Template Structure

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                     US MARKET DAILY BRIEF                                        │
│                     [Date] - Pre-Market Edition                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  1. MARKET SNAPSHOT                                                              │
│     - Index levels & changes                                                     │
│     - Futures positioning                                                        │
│     - Volatility metrics                                                         │
│                                                                                  │
│  2. SECTOR PERFORMANCE                                                           │
│     - Heat map of sector returns                                                 │
│     - Rotation analysis                                                          │
│                                                                                  │
│  3. MARKET BREADTH                                                               │
│     - Advance/Decline                                                            │
│     - New Highs/Lows                                                             │
│     - % Above Moving Averages                                                    │
│                                                                                  │
│  4. RATES & MACRO                                                                │
│     - Treasury yields                                                            │
│     - Credit spreads                                                             │
│     - Currency & commodities                                                     │
│                                                                                  │
│  5. TODAY'S CALENDAR                                                             │
│     - Economic releases                                                          │
│     - Earnings (pre/post)                                                        │
│     - Fed speakers                                                               │
│                                                                                  │
│  6. NOTABLE MOVERS                                                               │
│     - Top gainers/losers                                                         │
│     - Unusual volume                                                             │
│     - News-driven moves                                                          │
│                                                                                  │
│  7. SENTIMENT ANALYSIS                                                           │
│     - News sentiment summary                                                     │
│     - Social media trends                                                        │
│                                                                                  │
│  8. TRADE SIGNALS                                                                │
│     - Active signals (structured format)                                         │
│     - Watchlist                                                                  │
│                                                                                  │
│  9. RISK DASHBOARD                                                               │
│     - Current regime                                                             │
│     - Portfolio exposure                                                         │
│     - Key levels to watch                                                        │
│                                                                                  │
│  DISCLAIMER                                                                      │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Example Daily Report (Mock Data)

```markdown
# 🇺🇸 US MARKET DAILY BRIEF
## Thursday, January 30, 2026 | Pre-Market Edition
### Generated: 06:30 AM ET

---

## ⚠️ RISK DISCLAIMER
This report is for educational and research purposes only. It does not constitute 
personalized investment advice. Past performance does not guarantee future results. 
Trading involves substantial risk of loss. Never invest more than you can afford to lose.

---

## 1. 📊 MARKET SNAPSHOT

### Index Performance (Prior Close → Futures)

| Index | Close | Change | % Chg | Futures | Futures % |
|-------|-------|--------|-------|---------|-----------|
| S&P 500 | 5,842.31 | +28.45 | +0.49% | 5,851 | +0.15% |
| Nasdaq 100 | 20,892.45 | +156.23 | +0.75% | 20,945 | +0.25% |
| Dow Jones | 43,521.89 | +102.34 | +0.24% | 43,580 | +0.13% |
| Russell 2000 | 2,287.45 | -12.34 | -0.54% | 2,291 | +0.16% |

### Volatility Metrics

| Metric | Value | Signal |
|--------|-------|--------|
| VIX | 16.42 | 🟢 Normal |
| VIX Term Structure | 1.08 (contango) | 🟢 Risk-on |
| VIX9D | 14.85 | 🟢 Calm |
| VVIX | 92.45 | 🟡 Slightly elevated |
| Put/Call Ratio | 0.82 | 🟢 Neutral-bullish |

**Regime: 🟢 RISK-ON | Normal Volatility | Uptrend**

---

## 2. 🏭 SECTOR PERFORMANCE

### Yesterday's Sector Returns (SPDR ETFs)

```
Technology   (XLK)  ████████████████████████  +1.24%
Cons Discr   (XLY)  ████████████████████      +0.98%
Comm Services(XLC)  ██████████████████        +0.87%
Financials   (XLF)  ██████████████            +0.65%
Industrials  (XLI)  ████████████              +0.54%
Healthcare   (XLV)  ████████                  +0.32%
Materials    (XLB)  ██████                    +0.21%
Consumer Stap(XLP)  ████                      +0.12%
Real Estate  (XLRE) ██                        +0.05%
Utilities    (XLU)  ▌                         -0.08%
Energy       (XLE)  ████████ (neg)            -0.45%
```

### Rotation Signal
📈 **Growth > Value** | Risk appetite healthy, tech leadership continues.
Large-cap outperforming small-cap (SPY +0.49% vs IWM -0.54%).

---

## 3. 📐 MARKET BREADTH

### NYSE Breadth (Yesterday)

| Metric | Value | Prior | Trend |
|--------|-------|-------|-------|
| Advancing Issues | 1,842 | 1,654 | ↑ |
| Declining Issues | 1,234 | 1,412 | ↓ |
| A/D Ratio | 1.49 | 1.17 | ↑ Improving |
| New 52W Highs | 156 | 132 | ↑ |
| New 52W Lows | 28 | 34 | ↓ |
| Hi-Lo Ratio | 5.57 | 3.88 | ↑ Strong |

### Stocks Above Moving Averages (S&P 500)

| Timeframe | % Above | Prior Week | Signal |
|-----------|---------|------------|--------|
| Above 20 DMA | 68.2% | 62.4% | 🟢 Expanding |
| Above 50 DMA | 71.4% | 68.8% | 🟢 Healthy |
| Above 200 DMA | 76.8% | 75.2% | 🟢 Bull market |

**McClellan Oscillator:** +42.5 (bullish, but approaching overbought)

---

## 4. 💵 RATES & MACRO

### Treasury Yields

| Tenor | Yield | Daily Δ | Weekly Δ |
|-------|-------|---------|----------|
| 2-Year | 4.12% | -2 bps | -8 bps |
| 10-Year | 4.38% | -1 bp | -5 bps |
| 30-Year | 4.52% | flat | -3 bps |
| 2s10s Spread | +26 bps | +1 bp | +3 bps |

### Credit & Currency

| Metric | Value | Signal |
|--------|-------|--------|
| HY Spread (OAS) | 312 bps | 🟢 Tight, risk-on |
| IG Spread (OAS) | 92 bps | 🟢 Normal |
| DXY (Dollar Index) | 103.45 | Flat |
| EUR/USD | 1.0842 | -0.12% |
| USD/JPY | 148.92 | +0.08% |

### Commodities

| Commodity | Price | Change |
|-----------|-------|--------|
| WTI Crude | $76.42 | -0.85% |
| Gold | $2,048 | +0.32% |
| Bitcoin | $98,450 | +2.14% |

---

## 5. 📅 TODAY'S CALENDAR

### Economic Releases

| Time (ET) | Event | Consensus | Prior | Importance |
|-----------|-------|-----------|-------|------------|
| 08:30 | GDP Q4 (Advance) | +2.4% | +4.9% | ⭐⭐⭐ HIGH |
| 08:30 | Initial Jobless Claims | 215K | 212K | ⭐⭐ MED |
| 10:00 | Pending Home Sales | +1.5% | -1.0% | ⭐ LOW |

### Earnings (Pre-Market) ⭐⭐⭐

| Ticker | Company | EPS Est | Rev Est | Notes |
|--------|---------|---------|---------|-------|
| **AAPL** | Apple | $2.10 | $117.9B | iPhone seasonality, Services growth |
| **AMZN** | Amazon | $1.52 | $165.8B | AWS margins, holiday retail |
| **V** | Visa | $2.64 | $8.9B | Cross-border volumes |
| META | Meta | $5.22 | $38.9B | Reels monetization |

### Earnings (Post-Market)

| Ticker | Company | EPS Est | Notes |
|--------|---------|---------|-------|
| INTC | Intel | $0.12 | Foundry update |
| ROKU | Roku | -$0.42 | Subscriber adds |

### Fed Speakers
- 10:00 AM: Fed Gov. Waller on inflation outlook
- 2:00 PM: Richmond Fed Barkin Q&A

---

## 6. 🚀 NOTABLE MOVERS

### Pre-Market Movers (>$5B market cap, >3% move)

| Ticker | Move | Volume | Catalyst |
|--------|------|--------|----------|
| TSLA | +4.2% | 8.2M | Earnings beat, FSD progress |
| IBM | +6.8% | 2.1M | AI revenue +45% YoY |
| NOW | -5.4% | 890K | Guidance below consensus |
| LLY | +2.8% | 1.2M | Positive Phase 3 data |

### Unusual Volume (Prior Session)

| Ticker | Rel Vol | Price Action | Notes |
|--------|---------|--------------|-------|
| PLTR | 3.4x | +4.2% | Defense contract rumor |
| SNOW | 2.8x | -2.1% | Block trade reported |
| COIN | 2.6x | +5.8% | BTC correlation |

### Gap Watchlist (Earnings Reaction)
- **AAPL**: Options imply ±4.2% move
- **AMZN**: Options imply ±5.8% move
- **META**: Options imply ±6.1% move

---

## 7. 🧠 SENTIMENT ANALYSIS

### News Sentiment (24hr Rolling)

| Category | Score | Trend | Key Themes |
|----------|-------|-------|------------|
| Overall Market | 62/100 | 📈 Improving | Earnings optimism, soft landing narrative |
| Technology | 71/100 | 📈 Bullish | AI infrastructure spend, chip demand |
| Financials | 58/100 | ➡️ Neutral | NIM pressure vs capital markets |
| Energy | 42/100 | 📉 Bearish | Oversupply concerns, weak demand |

### Top Themes in News (GPT Summary)
1. **AI Infrastructure Boom**: IBM and hyperscalers reporting strong AI-driven revenue
2. **Soft Landing Confirmed?**: GDP expected to show resilient growth without inflation spike
3. **Megacap Earnings**: Apple/Amazon results will set tone for Q1

### Social Sentiment (X/Reddit - Cashtag Velocity)

| Ticker | Mentions (24h) | Sentiment | Δ vs Avg |
|--------|---------------|-----------|----------|
| $AAPL | 12,450 | 65% bullish | +180% |
| $TSLA | 18,230 | 72% bullish | +95% |
| $NVDA | 9,820 | 78% bullish | +45% |
| $PLTR | 6,540 | 81% bullish | +310% ⚠️ |

⚠️ **Alert**: Unusual retail interest in PLTR. Exercise caution - could indicate crowded trade.

---

## 8. 📡 TRADE SIGNALS

### Active Signals

#### Signal 1: NVDA (LONG)

| Field | Value |
|-------|-------|
| **Ticker** | NVDA |
| **Direction** | LONG |
| **Horizon** | SWING_5_15D |
| **Entry Logic** | Breakout from 3-week consolidation at $875, volume 2.1x avg, AI demand catalyst |
| **Entry Price** | $878.50 (market) |
| **Stop Loss** | $842.00 (close below consolidation low) |
| **Target 1** | $920.00 (50% position) |
| **Target 2** | $965.00 (50% position) |
| **Risk/Reward** | 1:1.5 / 1:2.4 |
| **Catalyst** | GTC conference in 3 weeks, continued AI infrastructure spending |
| **Key Risks** | 1) Market-wide risk-off 2) Export restriction news 3) Stretched valuation |
| **Confidence** | 72/100 |
| **Position Size** | 3.5% of portfolio |
| **Rationale** | Technical breakout with fundamental catalyst alignment. Institutional accumulation visible in OBV. Sector momentum strong. |

---

#### Signal 2: XLE (SHORT via Put Spreads)

| Field | Value |
|-------|-------|
| **Ticker** | XLE |
| **Direction** | SHORT (bearish bias) |
| **Horizon** | SWING_5_15D |
| **Entry Logic** | Breakdown below 50 DMA, relative weakness vs SPY, oversupply concerns |
| **Entry Price** | $82.50 |
| **Invalidation** | Close above $85.50 (above 50 DMA) |
| **Target** | $78.00 |
| **Catalyst** | Weak oil demand, OPEC+ uncertainty |
| **Key Risks** | 1) Geopolitical oil spike 2) Rotation into value 3) Cold weather demand |
| **Confidence** | 58/100 |
| **Position Size** | 2.0% of portfolio (defined risk) |
| **Rationale** | Sector showing persistent weakness. Better opportunities elsewhere. Trade with defined risk via put spreads. |

---

### Watchlist (Not Yet Actionable)

| Ticker | Setup | Trigger | Notes |
|--------|-------|---------|-------|
| GOOGL | Post-earnings base | Break above $178 | Wait for AAPL/AMZN tone |
| CRM | Bull flag | Break above $312 | Volume confirmation needed |
| JPM | 50 DMA support | Hold above $198 | Rate-sensitive |
| COST | All-time high test | Break above $925 | Consumer strength |

---

### NO TRADE Today

| Condition | Status | Action |
|-----------|--------|--------|
| VIX > 40 | ✅ VIX = 16.42 | OK to trade |
| FOMC Day | ✅ Not today | OK to trade |
| GDP Release Risk | ⚠️ 08:30 AM | **Reduce size pre-8:30** |
| Megacap Earnings | ⚠️ AAPL/AMZN | **No new positions in megacap tech until reaction clear** |

---

## 9. 🎯 RISK DASHBOARD

### Current Regime
```
Volatility:  🟢 NORMAL (VIX 16.42)
Trend:       🟢 UPTREND (71% > 50 DMA)
Risk:        🟢 RISK-ON (contango, tight spreads)

Active Strategies: momentum_v1, breakout_v1, event_driven_v1
Inactive: mean_reversion_v1 (not oversold conditions)
```

### Portfolio Exposure (Hypothetical)

| Metric | Current | Limit | Status |
|--------|---------|-------|--------|
| Gross Exposure | 82% | 100% | ✅ |
| Net Long | 68% | 80% | ✅ |
| Single Position Max | 4.2% | 5% | ✅ |
| Sector Max (Tech) | 22% | 25% | ✅ |
| Correlation Avg | 0.48 | 0.70 | ✅ |
| Daily VaR (95%) | 1.8% | 2.5% | ✅ |
| MTD Drawdown | -1.2% | -10% | ✅ |

### Key Levels to Watch

| Index/Ticker | Level | Significance |
|--------------|-------|--------------|
| SPX | 5,785 | 21 DMA support |
| SPX | 5,900 | Psychological resistance |
| QQQ | $505 | Breakout level |
| VIX | 20 | Risk-off threshold |
| 10Y Yield | 4.50% | Equity pressure point |

---

## 📋 SUMMARY

**Market Tone:** Constructive. Breadth improving, volatility contained, risk appetite intact.

**Key Themes Today:**
1. GDP print at 8:30 AM - consensus expects cooling but still positive
2. AAPL/AMZN earnings will dictate megacap tech direction
3. Tech leadership continues, energy lagging

**Positioning Guidance:**
- Maintain long bias in quality growth (NVDA, software)
- Underweight energy, cautious on rate-sensitives
- Reduce position sizes ahead of GDP print
- No new megacap tech until earnings reaction clear

**Risk Events:**
- ⚠️ GDP 8:30 AM (could shift soft landing narrative)
- ⚠️ AAPL/AMZN earnings (25% of QQQ)
- Fed speakers could add rate noise

---

*Report generated by TradingAI Bot v1.0*  
*Data sources: Polygon.io, NewsAPI, X API*  
*Next update: Post-market edition @ 4:30 PM ET*
```

---

## Report Generation Code

```python
class DailyReportGenerator:
    """Generates the daily market brief using structured data + GPT."""
    
    def __init__(self, data_service: DataService, gpt_client: OpenAI):
        self.data = data_service
        self.gpt = gpt_client
    
    async def generate(self, report_date: date) -> DailyReport:
        """Generate complete daily report."""
        
        # Gather all data in parallel
        market_data, breadth, sectors, calendar, signals, sentiment = await asyncio.gather(
            self.data.get_market_snapshot(report_date),
            self.data.get_breadth_metrics(report_date),
            self.data.get_sector_performance(report_date),
            self.data.get_calendar_events(report_date),
            self.data.get_active_signals(report_date),
            self.data.get_sentiment_summary(report_date)
        )
        
        # Build structured sections
        sections = {
            "market_snapshot": self._build_market_snapshot(market_data),
            "sectors": self._build_sector_section(sectors),
            "breadth": self._build_breadth_section(breadth),
            "rates_macro": self._build_rates_section(market_data),
            "calendar": self._build_calendar_section(calendar),
            "movers": self._build_movers_section(market_data['movers']),
            "sentiment": self._build_sentiment_section(sentiment),
            "signals": self._build_signals_section(signals),
            "risk_dashboard": self._build_risk_section(market_data)
        }
        
        # Use GPT to generate summary and narrative
        summary = await self._generate_summary(sections)
        
        # Render to Markdown
        markdown = self._render_markdown(sections, summary, report_date)
        
        return DailyReport(
            report_date=report_date,
            markdown_content=markdown,
            structured_data=sections,
            generated_at=datetime.now(timezone.utc)
        )
    
    async def _generate_summary(self, sections: dict) -> str:
        """Use GPT to generate executive summary."""
        
        prompt = f"""
        Based on the following market data, generate a concise 3-paragraph executive summary:
        
        Market Data:
        {json.dumps(sections['market_snapshot'], indent=2)}
        
        Key Events:
        {json.dumps(sections['calendar'], indent=2)}
        
        Active Signals:
        {json.dumps(sections['signals'], indent=2)}
        
        Provide:
        1. Market Tone (1-2 sentences)
        2. Key Themes Today (3 bullet points)
        3. Positioning Guidance (2-3 sentences)
        
        Be specific, actionable, and include risk warnings. Do not make price predictions.
        """
        
        response = await self.gpt.chat.completions.create(
            model="gpt-5.2",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=500
        )
        
        return response.choices[0].message.content
```
