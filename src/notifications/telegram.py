"""
TradingAI Bot - Telegram Notification Service
Sends trading signals and reports to Telegram.
"""
import asyncio
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
import aiohttp

from src.core.config import get_settings
from src.core.models import Signal
from src.notifications.formatter import SignalNarrativeFormatter


settings = get_settings()


class TelegramNotifier:
    """
    Sends notifications to Telegram using Bot API.
    
    Supports:
    - Trading signals with formatted messages
    - Daily market reports
    - System alerts
    - Batch notifications with rate limiting
    """
    
    TELEGRAM_API_BASE = "https://api.telegram.org"
    
    def __init__(self):
        self.bot_token = settings.telegram_bot_token
        self.chat_id = settings.telegram_chat_id
        self.logger = logging.getLogger(__name__)
        self._rate_limit_delay = 0.05  # Telegram allows 30 msg/sec
        self._max_message_len = 3900
        self._formatter = SignalNarrativeFormatter()
    
    @property
    def is_configured(self) -> bool:
        """Check if Telegram is properly configured."""
        return bool(self.bot_token and self.chat_id)
    
    async def send_message(
        self,
        text: str,
        parse_mode: str = "HTML",
        disable_notification: bool = False
    ) -> bool:
        """
        Send a message to Telegram.
        
        Args:
            text: Message text (supports HTML formatting)
            parse_mode: HTML or Markdown
            disable_notification: Send silently
        
        Returns:
            True if sent successfully
        """
        if not self.is_configured:
            self.logger.warning("Telegram not configured, skipping notification")
            return False

        url = f"{self.TELEGRAM_API_BASE}/bot{self.bot_token}/sendMessage"

        chunks = self._split_message(text, self._max_message_len)

        try:
            async with aiohttp.ClientSession() as session:
                for chunk in chunks:
                    payload = {
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "parse_mode": parse_mode,
                        "disable_notification": disable_notification,
                    }

                    async with session.post(url, json=payload) as response:
                        if response.status != 200:
                            error = await response.text()
                            self.logger.error(f"Telegram API error: {response.status} - {error}")
                            return False

                    # Keep some space between chunk sends
                    if len(chunks) > 1:
                        await asyncio.sleep(0.1)
                return True
        except Exception as e:
            self.logger.error(f"Failed to send Telegram message: {e}")
            return False
    
    async def send_signal(self, signal: Signal) -> bool:
        """
        Send a formatted trading signal to Telegram.
        
        Args:
            signal: Trading signal to send
        
        Returns:
            True if sent successfully
        """
        message = self._formatter.format_signal(signal, as_html=True)
        return await self.send_message(message.strip())
    
    async def send_signals_batch(self, signals: List[Signal]) -> int:
        """
        Send multiple signals with rate limiting.
        
        Args:
            signals: List of signals to send
        
        Returns:
            Number of successfully sent signals
        """
        if not signals:
            return 0
        
        # Send summary first
        summary = f"📊 <b>{len(signals)} New Signals</b>\n\n"
        for s in signals[:10]:  # Limit to 10 in summary
            direction = getattr(s, 'direction', 'LONG')
            direction_text = direction.value if hasattr(direction, 'value') else str(direction)
            emoji = "🟢" if str(direction_text).upper() == "LONG" else "🔴"
            strategy = getattr(s, 'strategy_id', None) or getattr(s, 'strategy', None) or 'multi-factor'
            conf = self._formatter._normalize_confidence(getattr(s, 'confidence', 0))
            summary += f"{emoji} <code>{s.ticker}</code> - {strategy} ({conf:.0f}%)\n"
        
        if len(signals) > 10:
            summary += f"\n... and {len(signals) - 10} more"
        
        await self.send_message(summary)
        
        # Send detailed signals with rate limiting
        success_count = 0
        for signal in signals[:5]:  # Limit detailed to top 5
            await asyncio.sleep(self._rate_limit_delay)
            if await self.send_signal(signal):
                success_count += 1
        
        return success_count
    
    async def send_daily_report(
        self,
        report: Dict[str, Any]
    ) -> bool:
        """
        Send formatted daily market report.
        
        Args:
            report: Dict with market overview, signals, news summary
        
        Returns:
            True if sent successfully
        """
        message = self._format_daily_report_message(report)
        return await self.send_message(message.strip())
    
    async def send_alert(
        self,
        title: str,
        message: str,
        level: str = "INFO"
    ) -> bool:
        """
        Send system alert.
        
        Args:
            title: Alert title
            message: Alert message
            level: INFO, WARNING, ERROR, CRITICAL
        
        Returns:
            True if sent successfully
        """
        text = self._format_alert_message(title=title, message=message, level=level)

        # Don't silence critical alerts
        silent = level not in ("ERROR", "CRITICAL")
        return await self.send_message(text.strip(), disable_notification=silent)

    def _format_alert_message(self, title: str, message: str, level: str = "INFO") -> str:
        level_emoji = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }

        emoji = level_emoji.get(level, "ℹ️")

        return f"""
{emoji} <b>ALERT: {title}</b>

{message}

<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""

    def _format_daily_report_message(self, report: Dict[str, Any]) -> str:
        overview = report.get('overview', {})
        signals = report.get('signals', [])
        news_summary = report.get('news_summary', 'No news summary available')

        message = f"""
📈 <b>DAILY MARKET REPORT</b>
<i>{datetime.utcnow().strftime('%Y-%m-%d')}</i>

<b>═══ MARKET OVERVIEW ═══</b>

<b>Indices:</b>
  SPY: {overview.get('spy_change', 'N/A')}
  QQQ: {overview.get('qqq_change', 'N/A')}
  IWM: {overview.get('iwm_change', 'N/A')}

<b>VIX:</b> {overview.get('vix', 'N/A')}
<b>Market Regime:</b> {overview.get('regime', 'N/A')}

<b>═══ TOP SIGNALS ═══</b>
"""

        if signals:
            for s in signals[:5]:
                direction = getattr(s, 'direction', 'LONG')
                direction_text = direction.value if hasattr(direction, 'value') else str(direction)
                emoji = "🟢" if str(direction_text).upper() == "LONG" else "🔴"
                entry = float(getattr(s, 'entry_price', 0) or 0)
                conf = self._formatter._normalize_confidence(getattr(s, 'confidence', 0))
                message += f"\n{emoji} <code>{s.ticker}</code> ${entry:.2f} ({conf:.0f}%)"
        else:
            message += "\nNo signals generated today"

        message += f"""

<b>═══ NEWS SUMMARY ═══</b>
{news_summary[:800]}{'...' if len(news_summary) > 800 else ''}
"""
        return message
    
    def _calculate_rr(self, signal: Signal) -> float:
        """Calculate risk/reward ratio."""
        risk = abs(signal.entry_price - signal.stop_loss)
        reward = abs(signal.take_profit - signal.entry_price)
        
        if risk == 0:
            return 0
        
        return reward / risk

    def _split_message(self, text: str, max_len: int) -> List[str]:
        """Split long text by paragraph/sentence boundaries for cleaner reading."""
        if len(text) <= max_len:
            return [text]

        chunks: List[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= max_len:
                chunks.append(remaining)
                break

            split_at = remaining.rfind("\n\n", 0, max_len)
            if split_at < max_len // 3:
                split_at = remaining.rfind("\n", 0, max_len)
            if split_at < max_len // 3:
                split_at = remaining.rfind(". ", 0, max_len)
            if split_at < max_len // 3:
                split_at = max_len

            chunks.append(remaining[:split_at].strip())
            remaining = remaining[split_at:].strip()

        return chunks
    
    async def test_connection(self) -> bool:
        """Test Telegram connection by getting bot info."""
        if not self.is_configured:
            return False
        
        url = f"{self.TELEGRAM_API_BASE}/bot{self.bot_token}/getMe"
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        bot_name = data.get('result', {}).get('username', 'Unknown')
                        self.logger.info(f"Telegram connected: @{bot_name}")
                        return True
                    return False
        except Exception as e:
            self.logger.error(f"Telegram connection test failed: {e}")
            return False
