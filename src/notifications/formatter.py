"""
Professional notification formatter.
Builds concise paragraph-style commentary for trade signals.

v6.1: Added bilingual (English + Traditional Chinese) summary support
      and strategy-style labeling.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List


# ── Strategy style labels ─────────────────────────────────────────
STRATEGY_LABELS = {
    "swing": ("🔄 Swing", "波段交易"),
    "breakout": ("🚀 Breakout", "突破交易"),
    "momentum": ("⚡ Momentum", "動量交易"),
    "mean_reversion": ("📉 Mean Reversion", "均值回歸"),
    "vcp": ("🔍 VCP", "波動收縮"),
    "trend_following": ("📈 Trend Following", "趨勢跟蹤"),
    "event_driven": ("📅 Event-Driven", "事件驅動"),
    "multi-factor": ("🧩 Multi-Factor", "多因子"),
}

# ── Direction translations ────────────────────────────────────────
DIRECTION_ZH = {
    "LONG": "做多",
    "SHORT": "做空",
    "BUY": "買入",
    "SELL": "賣出",
}


class SignalNarrativeFormatter:
    """Create professional, paragraph-based signal commentary."""

    @staticmethod
    def _normalize_confidence(raw_conf: Any) -> float:
        try:
            conf = float(raw_conf or 0)
        except Exception:
            return 0.0
        if conf <= 1.0:
            return conf * 100.0
        return max(0.0, min(conf, 100.0))

    @staticmethod
    def _get_direction(signal: Any) -> str:
        direction = getattr(signal, "direction", "LONG")
        return direction.value if hasattr(direction, "value") else str(direction)

    @staticmethod
    def _get_stop(signal: Any) -> float:
        invalidation = getattr(signal, "invalidation", None)
        if invalidation is not None and hasattr(invalidation, "stop_price"):
            return float(getattr(invalidation, "stop_price", 0) or 0)
        return float(getattr(signal, "stop_loss", 0) or 0)

    @staticmethod
    def _get_target(signal: Any) -> float:
        targets = getattr(signal, "targets", None)
        if targets:
            first = targets[0]
            if hasattr(first, "price"):
                return float(getattr(first, "price", 0) or 0)
        return float(getattr(signal, "take_profit", 0) or 0)

    @staticmethod
    def _get_generated_at(signal: Any) -> datetime:
        return (
            getattr(signal, "generated_at", None)
            or getattr(signal, "timestamp", None)
            or datetime.utcnow()
        )

    @staticmethod
    def _get_strategy_label(strategy_id: str, lang: str = "en") -> str:
        """Get the display label for a strategy ID."""
        key = (strategy_id or "multi-factor").lower().replace(" ", "_")
        labels = STRATEGY_LABELS.get(key, STRATEGY_LABELS["multi-factor"])
        return labels[0] if lang == "en" else labels[1]

    def format_signal(self, signal: Any, as_html: bool = True) -> str:
        """Format one signal as professional paragraph commentary."""
        ticker = getattr(signal, "ticker", "N/A")
        direction = self._get_direction(signal).upper()
        direction_emoji = "🟢" if direction == "LONG" else "🔴"

        strategy = (
            getattr(signal, "strategy_id", None)
            or getattr(signal, "strategy", None)
            or "multi-factor"
        )
        strategy_label = self._get_strategy_label(strategy)
        horizon = getattr(signal, "horizon", None)
        horizon_text = (
            horizon.value if hasattr(horizon, "value")
            else (str(horizon) if horizon else "swing")
        )

        entry_price = float(getattr(signal, "entry_price", 0) or 0)
        stop_price = self._get_stop(signal)
        target_price = self._get_target(signal)
        rr = float(getattr(signal, "risk_reward_ratio", 0) or 0)
        if (
            rr == 0
            and entry_price
            and stop_price
            and target_price
            and abs(entry_price - stop_price) > 0
        ):
            rr = abs(target_price - entry_price) / abs(entry_price - stop_price)

        pos_size = getattr(signal, "position_size_pct", None)
        if pos_size is None:
            pos_size = getattr(signal, "position_size", 0)
        pos_pct = (
            float(pos_size or 0) * 100
            if float(pos_size or 0) <= 1
            else float(pos_size or 0)
        )

        confidence = self._normalize_confidence(
            getattr(signal, "confidence", 0)
        )
        rationale = (
            getattr(signal, "gpt_rationale", None)
            or getattr(signal, "rationale", "")
            or getattr(signal, "entry_logic", "")
        )
        catalyst = getattr(signal, "catalyst", "")
        risks: List[str] = list(getattr(signal, "key_risks", []) or [])

        ts = self._get_generated_at(signal).strftime("%Y-%m-%d %H:%M UTC")

        if as_html:
            p1 = (
                f"{direction_emoji} <b>{ticker} {direction}</b> "
                f"setup flagged under <b>{strategy_label}</b> "
                f"for a <b>{horizon_text}</b> horizon. "
                f"Confidence is <b>{confidence:.0f}%</b>, "
                f"with entry near <b>${entry_price:.2f}</b>, "
                f"invalidation at <b>${stop_price:.2f}</b>, "
                f"and primary objective at "
                f"<b>${target_price:.2f}</b> "
                f"(estimated R:R <b>{rr:.2f}:1</b>)."
            )
            default_thesis = (
                "price/volume alignment with trend continuation conditions"
            )
            default_catalyst = (
                "no singular catalyst; setup driven by technical structure"
            )
            p2 = (
                f"Position sizing is calibrated at approximately "
                f"<b>{pos_pct:.1f}%</b> of portfolio risk budget. "
                f"Primary thesis: {rationale or default_thesis}. "
                f"Catalyst context: {catalyst or default_catalyst}."
            )
            risk_text = (
                "; ".join(risks[:3])
                if risks
                else "event-driven volatility and trend failure "
                     "below invalidation"
            )
            p3 = (
                f"Execution note: prioritize disciplined entries "
                f"inside the proposed zone and preserve downside limits. "
                f"Key risks include {risk_text}. "
                f"Review after each impulse leg and adjust only if "
                f"market structure improves. "
                f"<i>Generated: {ts}</i>"
            )
            return f"{p1}\n\n{p2}\n\n{p3}"

        default_thesis_plain = "technical trend and momentum alignment"
        default_catalyst_plain = "technical setup"
        default_risk_plain = "event volatility and invalidation break"
        risk_str = "; ".join(risks[:3]) if risks else default_risk_plain
        return (
            f"{ticker} {direction} setup ({strategy_label}, {horizon_text}) "
            f"with {confidence:.0f}% confidence. "
            f"Entry ${entry_price:.2f}, stop ${stop_price:.2f}, "
            f"target ${target_price:.2f}, R:R {rr:.2f}:1, "
            f"position size ~{pos_pct:.1f}%. "
            f"Thesis: {rationale or default_thesis_plain}. "
            f"Catalyst: {catalyst or default_catalyst_plain}. "
            f"Risks: {risk_str}."
        )

    def format_bilingual_summary(self, signal: Any) -> str:
        """
        Generate a concise bilingual (EN + Traditional Chinese) summary
        suitable for a Discord embed field.

        Example output:
            🟢 AAPL Swing Long — Pullback to 21 EMA
            信心：78% (B+)｜止損：$181.50｜目標：$192.00
            風險：12日後財報，注意事件風險。
        """
        ticker = getattr(signal, "ticker", "N/A")
        direction = self._get_direction(signal).upper()
        direction_emoji = "🟢" if direction in ("LONG", "BUY") else "🔴"
        direction_zh = DIRECTION_ZH.get(direction, direction)

        strategy = (
            getattr(signal, "strategy_id", None)
            or getattr(signal, "strategy", None)
            or "multi-factor"
        )
        strategy_zh = self._get_strategy_label(strategy, lang="zh")

        stop_price = self._get_stop(signal)
        target_price = self._get_target(signal)
        confidence = self._normalize_confidence(
            getattr(signal, "confidence", 0)
        )

        # Grade
        if confidence >= 80:
            grade = "A"
        elif confidence >= 70:
            grade = "B+"
        elif confidence >= 60:
            grade = "B"
        elif confidence >= 50:
            grade = "C+"
        else:
            grade = "C"

        setup_desc = (
            getattr(signal, "entry_logic", "")
            or getattr(signal, "rationale", "")
            or ""
        )
        setup_short = setup_desc[:50] if setup_desc else ""

        risks: List[str] = list(getattr(signal, "key_risks", []) or [])
        risk_zh = risks[0][:30] if risks else "注意市場環境風險"

        # English line
        en_line = (
            f"{direction_emoji} {ticker} {strategy_zh}{direction_zh}"
        )
        if setup_short:
            en_line += f" — {setup_short}"

        # Chinese details
        zh_line = (
            f"信心：{confidence:.0f}% ({grade})"
            f"｜止損：${stop_price:.2f}"
            f"｜目標：${target_price:.2f}"
        )
        zh_risk = f"風險：{risk_zh}"

        return f"{en_line}\n{zh_line}\n{zh_risk}"

    def format_signal_batch(
        self, signals: List[Any], as_html: bool = True
    ) -> str:
        """Format a batch of signals into a single summary."""
        if not signals:
            return "No signals to report."

        parts = []
        for i, sig in enumerate(signals, 1):
            ticker = getattr(sig, "ticker", "?")
            direction = self._get_direction(sig).upper()
            confidence = self._normalize_confidence(
                getattr(sig, "confidence", 0)
            )
            strategy = (
                getattr(sig, "strategy_id", None)
                or getattr(sig, "strategy", None)
                or "?"
            )
            label = self._get_strategy_label(strategy)
            emoji = "🟢" if direction in ("LONG", "BUY") else "🔴"
            parts.append(
                f"{i}. {emoji} **{ticker}** {direction} "
                f"({label}, {confidence:.0f}%)"
            )

        header = f"📡 **{len(signals)} Signal(s) Generated**\n"
        return header + "\n".join(parts)
