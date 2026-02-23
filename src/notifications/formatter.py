"""
Professional notification formatter.
Builds concise paragraph-style commentary for trade signals.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, List


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
        return getattr(signal, "generated_at", None) or getattr(signal, "timestamp", None) or datetime.utcnow()

    def format_signal(self, signal: Any, as_html: bool = True) -> str:
        """Format one signal as professional paragraph commentary."""
        ticker = getattr(signal, "ticker", "N/A")
        direction = self._get_direction(signal).upper()
        direction_emoji = "🟢" if direction == "LONG" else "🔴"

        strategy = getattr(signal, "strategy_id", None) or getattr(signal, "strategy", None) or "multi-factor"
        horizon = getattr(signal, "horizon", None)
        horizon_text = horizon.value if hasattr(horizon, "value") else (str(horizon) if horizon else "swing")

        entry_price = float(getattr(signal, "entry_price", 0) or 0)
        stop_price = self._get_stop(signal)
        target_price = self._get_target(signal)
        rr = float(getattr(signal, "risk_reward_ratio", 0) or 0)
        if rr == 0 and entry_price and stop_price and target_price and abs(entry_price - stop_price) > 0:
            rr = abs(target_price - entry_price) / abs(entry_price - stop_price)

        pos_size = getattr(signal, "position_size_pct", None)
        if pos_size is None:
            pos_size = getattr(signal, "position_size", 0)
        pos_pct = float(pos_size or 0) * 100 if float(pos_size or 0) <= 1 else float(pos_size or 0)

        confidence = self._normalize_confidence(getattr(signal, "confidence", 0))
        rationale = getattr(signal, "gpt_rationale", None) or getattr(signal, "rationale", "") or getattr(signal, "entry_logic", "")
        catalyst = getattr(signal, "catalyst", "")
        risks: List[str] = list(getattr(signal, "key_risks", []) or [])

        ts = self._get_generated_at(signal).strftime("%Y-%m-%d %H:%M UTC")

        if as_html:
            p1 = (
                f"{direction_emoji} <b>{ticker} {direction}</b> setup flagged under <b>{strategy}</b> "
                f"for a <b>{horizon_text}</b> horizon. Confidence is <b>{confidence:.0f}%</b>, "
                f"with entry near <b>${entry_price:.2f}</b>, invalidation at <b>${stop_price:.2f}</b>, "
                f"and primary objective at <b>${target_price:.2f}</b> (estimated R:R <b>{rr:.2f}:1</b>)."
            )
            p2 = (
                f"Position sizing is calibrated at approximately <b>{pos_pct:.1f}%</b> of portfolio risk budget. "
                f"Primary thesis: {rationale or 'price/volume alignment with trend continuation conditions'}. "
                f"Catalyst context: {catalyst or 'no singular catalyst; setup driven by technical structure and momentum quality'}."
            )
            risk_text = "; ".join(risks[:3]) if risks else "event-driven volatility and trend failure below invalidation"
            p3 = (
                f"Execution note: prioritize disciplined entries inside the proposed zone and preserve downside limits. "
                f"Key risks include {risk_text}. Review after each impulse leg and adjust only if market structure improves. "
                f"<i>Generated: {ts}</i>"
            )
            return f"{p1}\n\n{p2}\n\n{p3}"

        return (
            f"{ticker} {direction} setup ({strategy}, {horizon_text}) with {confidence:.0f}% confidence. "
            f"Entry ${entry_price:.2f}, stop ${stop_price:.2f}, target ${target_price:.2f}, R:R {rr:.2f}:1, "
            f"position size ~{pos_pct:.1f}%. Thesis: {rationale or 'technical trend and momentum alignment'}. "
            f"Catalyst: {catalyst or 'technical setup'}. Risks: "
            f"{'; '.join(risks[:3]) if risks else 'event volatility and invalidation break'}.")
