# Discord Alert Design Guide

> How CC formats and delivers alerts in Discord.

---

## Alert Severity Tiers

| Tier                 | Emoji         | When Used                                              | Example                                      |
| -------------------- | ------------- | ------------------------------------------------------ | -------------------------------------------- |
| 🔴 **Urgent**        | Red circle    | Circuit breaker triggered, tail-risk event, stop hit   | "Portfolio drawdown exceeded 3% daily limit" |
| 🟡 **Important**     | Yellow circle | New actionable signal, regime change, earnings warning | "NVDA Breakout Long — Score 82"              |
| 🔵 **Informational** | Blue circle   | Regime update, news digest, watchlist change           | "Regime shifted: Bull Trending → Neutral"    |

---

## Signal Alert Structure

Every signal alert should include these fields:

### Required Fields

| Field                     | Purpose                     | Example                                      |
| ------------------------- | --------------------------- | -------------------------------------------- |
| **Ticker**                | What asset                  | `AAPL`                                       |
| **Direction**             | Long or Short               | 🟢 Long / 🔴 Short                           |
| **Strategy Style**        | Which strategy generated it | Swing · Breakout · Momentum · Mean Reversion |
| **Score**                 | Confidence 0–100            | `78/100`                                     |
| **Grade**                 | Letter grade                | `B+`                                         |
| **Entry Zone**            | Price range for entry       | `$185.20 – $186.00`                          |
| **Stop / Invalidation**   | Where the idea is wrong     | `$181.50 (–2.0%)`                            |
| **Target(s)**             | Profit objective(s)         | `T1: $192 (+3.7%) · T2: $198 (+6.9%)`        |
| **Why Buy / Why Short**   | Plain-language conviction   | 1–2 sentences                                |
| **Why Not / Risk**        | Key contradiction or risk   | 1–2 sentences                                |
| **Regime**                | Current market state        | 🟢 Bull Trending                             |
| **Data Mode**             | LIVE / PAPER / SYNTHETIC    | Badge in footer                              |
| **Timestamp + Freshness** | When generated, how fresh   | `14:32 ET · <1min`                           |

### Optional Fields (when available)

| Field            | Purpose                                        |
| ---------------- | ---------------------------------------------- |
| **Sector**       | Sector context and relative strength           |
| **Catalyst**     | Upcoming earnings, macro event, news           |
| **Volume**       | Relative volume vs average                     |
| **ATR**          | Current volatility context                     |
| **Factor Chips** | Score decomposition (`Breakout +28, Risk -12`) |
| **Analog**       | "N similar past setups → X% win rate over 10D" |

---

## Discord Embed Template (discord.py)

```python
import discord
from datetime import datetime

def build_signal_embed(signal) -> discord.Embed:
    """Build a structured signal alert embed."""

    # Color by direction
    color = 0x00D4AA if signal.direction == "LONG" else 0xFF4444

    # Grade from score
    score = signal.score
    if score >= 80: grade = "A"
    elif score >= 70: grade = "B+"
    elif score >= 60: grade = "B"
    elif score >= 50: grade = "C+"
    else: grade = "C"

    # Confidence bar
    filled = int(score / 100 * 8)
    bar = "█" * filled + "░" * (8 - filled)

    direction_emoji = "🟢" if signal.direction == "LONG" else "🔴"
    title = f"{direction_emoji} {signal.ticker} — {signal.strategy} {signal.direction} (Score: {score}/100)"

    embed = discord.Embed(
        title=title,
        color=color,
        timestamp=datetime.utcnow(),
    )

    embed.add_field(
        name="Strategy",
        value=f"{signal.strategy} · {signal.setup_description}",
        inline=True,
    )
    embed.add_field(
        name="Confidence",
        value=f"{bar} {score}%  (Grade: {grade})",
        inline=True,
    )
    embed.add_field(
        name="Regime",
        value=signal.regime or "Unknown",
        inline=True,
    )

    # Entry / Stop / Target block
    entry_text = f"**Entry:** ${signal.entry_price:.2f}"
    stop_text = f"**Stop:** ${signal.stop_price:.2f}"
    target_text = f"**Target:** ${signal.target_price:.2f}"
    embed.add_field(
        name="Trade Plan",
        value=f"{entry_text}\n{stop_text}\n{target_text}",
        inline=False,
    )

    # Why Buy / Why Not
    embed.add_field(
        name="Why Buy" if signal.direction == "LONG" else "Why Short",
        value=signal.why_buy or "—",
        inline=False,
    )
    embed.add_field(
        name="⚠️ Risk / Why Not",
        value=signal.why_not or "—",
        inline=False,
    )

    # Invalidation
    if signal.invalidation:
        embed.add_field(
            name="❌ Invalidation",
            value=signal.invalidation,
            inline=False,
        )

    # Footer with trust metadata
    embed.set_footer(
        text=f"{signal.data_mode} · {signal.data_source} · Freshness: {signal.freshness}"
    )

    return embed
```

---

## Bilingual Support (English + Traditional Chinese)

When bilingual mode is enabled, alerts include a Chinese summary field:

```
📝 中文摘要
AAPL 波段做多 — 回調至21日均線支撐，成交量萎縮。
信心：78% (B+)｜止損：$181.50｜目標：$192.00
風險：12日後財報，注意事件風險。
```

---

## Alert Deduplication

- Same ticker + same strategy + same direction within 5 minutes → suppress duplicate
- Regime change alerts → max 1 per regime transition
- News digests → batched every 15 minutes, not per-article

---

## Channel Organization (Recommended)

| Channel        | Content                              | Severity         |
| -------------- | ------------------------------------ | ---------------- |
| `#signals`     | Trade signals (score ≥ 65)           | 🟡 Important     |
| `#watchlist`   | Lower-score setups (50–64)           | 🔵 Informational |
| `#regime`      | Market state changes                 | 🔵 Informational |
| `#risk-alerts` | Circuit breakers, drawdown warnings  | 🔴 Urgent        |
| `#news`        | Market news digests                  | 🔵 Informational |
| `#portfolio`   | Daily portfolio brief                | 🟡 Important     |
| `#system`      | Bot health, errors, operational logs | 🔵 Informational |

---

## Anti-Patterns to Avoid

| ❌ Don't                         | ✅ Do Instead                                     |
| -------------------------------- | ------------------------------------------------- |
| Send raw numbers without context | Always show entry, stop, target, and why          |
| Alert on every tiny RSI change   | Batch, deduplicate, filter by score threshold     |
| Say "BUY NOW" or "GUARANTEED"    | Say "Signal: Swing Long, Score 78, Grade B+"      |
| Hide risk or contradiction       | Always show "Why Not" and invalidation            |
| Send 50 alerts in 10 minutes     | Throttle by regime, deduplicate, tier by severity |
| Use jargon without explanation   | Explain in plain language what happened and why   |
| Treat all signals as equal       | Show score, grade, and regime context             |
