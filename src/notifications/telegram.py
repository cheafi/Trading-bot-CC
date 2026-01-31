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
        
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_notification": disable_notification
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    if response.status == 200:
                        return True
                    else:
                        error = await response.text()
                        self.logger.error(f"Telegram API error: {response.status} - {error}")
                        return False
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
        # Direction emoji
        direction_emoji = "🟢" if signal.direction == "LONG" else "🔴"
        
        # Confidence indicator
        if signal.confidence >= 0.8:
            confidence_emoji = "⭐⭐⭐"
        elif signal.confidence >= 0.6:
            confidence_emoji = "⭐⭐"
        else:
            confidence_emoji = "⭐"
        
        message = f"""
{direction_emoji} <b>SIGNAL: {signal.ticker}</b> {direction_emoji}

<b>Direction:</b> {signal.direction}
<b>Strategy:</b> {signal.strategy}
<b>Confidence:</b> {signal.confidence:.0%} {confidence_emoji}

<b>Entry:</b> ${signal.entry_price:.2f}
<b>Stop Loss:</b> ${signal.stop_loss:.2f}
<b>Take Profit:</b> ${signal.take_profit:.2f}

<b>Risk/Reward:</b> {self._calculate_rr(signal):.1f}:1
<b>Position Size:</b> {signal.position_size:.1%}

<i>Generated: {signal.timestamp.strftime('%Y-%m-%d %H:%M UTC')}</i>
"""
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
            emoji = "🟢" if s.direction == "LONG" else "🔴"
            summary += f"{emoji} <code>{s.ticker}</code> - {s.strategy} ({s.confidence:.0%})\n"
        
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
        overview = report.get('overview', {})
        signals = report.get('signals', [])
        news_summary = report.get('news_summary', 'No news summary available')
        
        # Market overview section
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
                emoji = "🟢" if s.direction == "LONG" else "🔴"
                message += f"\n{emoji} <code>{s.ticker}</code> ${s.entry_price:.2f} ({s.confidence:.0%})"
        else:
            message += "\nNo signals generated today"
        
        message += f"""

<b>═══ NEWS SUMMARY ═══</b>
{news_summary[:500]}{'...' if len(news_summary) > 500 else ''}
"""
        
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
        level_emoji = {
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🚨"
        }
        
        emoji = level_emoji.get(level, "ℹ️")
        
        text = f"""
{emoji} <b>ALERT: {title}</b>

{message}

<i>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</i>
"""
        
        # Don't silence critical alerts
        silent = level not in ("ERROR", "CRITICAL")
        return await self.send_message(text.strip(), disable_notification=silent)
    
    def _calculate_rr(self, signal: Signal) -> float:
        """Calculate risk/reward ratio."""
        risk = abs(signal.entry_price - signal.stop_loss)
        reward = abs(signal.take_profit - signal.entry_price)
        
        if risk == 0:
            return 0
        
        return reward / risk
    
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
