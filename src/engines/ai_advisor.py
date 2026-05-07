"""
TradingAI Bot - AI Advisor with Reasoning Engine

The brain of the system: an LLM-powered advisor that:
1. Synthesizes signals, market regime, news, and portfolio state
2. Provides trade-or-no-trade decisions with chain-of-thought reasoning
3. Learns from past trade outcomes to calibrate confidence
4. Generates natural-language market briefs and risk warnings
5. Acts as the final gatekeeper before execution

Architecture:
    Market Data ─┐
    Signals ─────┤
    News/Social ─┼──► AI Advisor ──► Decision + Reasoning
    Portfolio ───┤
    ML Scores ───┘

Usage:
    advisor = AIAdvisor()
    decision = await advisor.evaluate_signal(signal, context)
    brief = await advisor.generate_market_brief(market_data)
    review = await advisor.review_portfolio(positions)
"""
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.config import get_settings
from src.core.models import Signal

logger = logging.getLogger(__name__)
settings = get_settings()


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

ADVISOR_SYSTEM_PROMPT = """You are an elite quantitative trading advisor managing a multi-market \
portfolio (US, HK, JP, Crypto). You combine technical analysis, fundamental data, \
market regime awareness, and risk management into actionable decisions.

Your guiding principles:
1. Capital preservation first — never risk more than 1% per trade, 3% daily
2. Only take asymmetric risk/reward (≥2:1 R:R minimum)
3. Regime awareness — different strategies for different markets
4. Position sizing via Kelly criterion (half-Kelly for safety)
5. Correlation control — avoid concentrated sector/factor bets
6. Always explain your reasoning step-by-step

You respond ONLY in valid JSON."""

SIGNAL_EVALUATION_PROMPT = """Evaluate this trading signal and decide whether to EXECUTE, REDUCE, or SKIP.

## Signal
- Ticker: {ticker}
- Direction: {direction}
- Entry: ${entry_price:.2f}
- Stop: ${stop_price:.2f} ({stop_pct:+.1f}%)
- Target: ${target_price:.2f} ({target_pct:+.1f}%)
- R:R Ratio: {rr_ratio:.1f}:1
- Strategy: {strategy}
- Confidence: {confidence}%
- Horizon: {horizon}

## Market Context
- Regime: {regime}
- VIX: {vix}
- Market Trend: {trend}
- Sector: {sector}

## Portfolio State
- Equity: ${equity:,.0f}
- Open Positions: {open_positions}
- Daily P&L: {daily_pnl:+.2f}%
- Current Exposure: {exposure:.0f}%

## ML Model Prediction
- Win Probability: {win_prob}
- Signal Grade: {signal_grade}
- Recommended Size: {rec_size}

## Recent News (for {ticker})
{news_summary}

## Past Performance (this strategy)
- Win Rate: {strategy_win_rate}%
- Avg Win: {avg_win:+.2f}%
- Avg Loss: {avg_loss:.2f}%
- Recent Streak: {streak}

Provide your analysis in JSON:
{{
    "decision": "EXECUTE" | "REDUCE" | "SKIP",
    "reasoning": {{
        "technical": "...",
        "fundamental": "...",
        "risk": "...",
        "regime_fit": "..."
    }},
    "confidence_override": null | 1-100,
    "position_size_pct": 0.0-5.0,
    "adjusted_stop": null | price,
    "adjusted_target": null | price,
    "time_limit_hours": null | number,
    "warnings": ["...", "..."],
    "one_liner": "Brief summary of decision"
}}"""

MARKET_BRIEF_PROMPT = """Generate a concise morning market brief for a professional trader.

## Market Data
{market_data}

## Overnight Moves
{overnight_moves}

## Key Events Today
{events}

## Active Signals
{active_signals}

## Portfolio Exposure
{portfolio}

Provide JSON:
{{
    "headline": "One-sentence market summary",
    "regime": "RISK_ON | RISK_OFF | NEUTRAL | TRANSITIONING",
    "key_levels": {{
        "SPY_support": 0.0,
        "SPY_resistance": 0.0,
        "VIX_alert": 0.0
    }},
    "sector_rotation": "Description of sector flows",
    "opportunities": ["Top 3 opportunities today"],
    "risks": ["Top 3 risks to watch"],
    "action_plan": "What to focus on today",
    "markets_to_watch": {{
        "us": "...",
        "hk": "...",
        "jp": "...",
        "crypto": "..."
    }}
}}"""

PORTFOLIO_REVIEW_PROMPT = """Review the current portfolio and provide risk assessment.

## Positions
{positions}

## Portfolio Metrics
- Total Equity: ${equity:,.0f}
- Cash: ${cash:,.0f} ({cash_pct:.0f}%)
- Exposure: {exposure:.0f}%
- Open P&L: {open_pnl:+.2f}%
- Today P&L: {today_pnl:+.2f}%
- Max Drawdown: {max_dd:.1f}%
- Correlation Risk: {corr_risk}

## Market Regime
{regime}

Provide JSON:
{{
    "risk_score": 1-10,
    "risk_level": "LOW | MODERATE | HIGH | CRITICAL",
    "portfolio_grade": "A+ to F",
    "issues": ["List of portfolio issues"],
    "actions_needed": [
        {{"action": "...", "ticker": "...", "urgency": "HIGH|MEDIUM|LOW", "reason": "..."}}
    ],
    "diversification_score": 1-10,
    "regime_alignment": "GOOD | MODERATE | POOR",
    "summary": "2-3 sentence portfolio assessment"
}}"""

FAILURE_LEARNING_PROMPT = """Analyze these recent losing trades and suggest improvements.

## Losing Trades
{losing_trades}

## Current Strategy Parameters
{strategy_params}

## Market Conditions During Losses
{market_conditions}

Provide JSON:
{{
    "pattern_detected": "Description of the failure pattern",
    "root_cause": "Most likely cause of losses",
    "parameter_adjustments": [
        {{"param": "...", "current": "...", "suggested": "...", "rationale": "..."}}
    ],
    "new_filters": ["Suggested new entry/exit filters"],
    "regime_advice": "Which regimes to avoid for this strategy",
    "expected_improvement": "Estimated win rate improvement",
    "confidence": "HIGH | MEDIUM | LOW"
}}"""


# ---------------------------------------------------------------------------
# AI Advisor
# ---------------------------------------------------------------------------

class AIAdvisor:
    """
    The central AI brain that makes final trading decisions.
    
    Combines:
    - GPT reasoning for signal evaluation
    - ML model predictions for win probability
    - Portfolio risk assessment
    - Market regime analysis
    - Learning from past trades
    """

    def __init__(self, model: Optional[str] = None):
        self.logger = logging.getLogger(__name__)
        self._client = None

        if settings.use_azure_openai:
            self.model = settings.azure_openai_deployment or "gpt-4o"
        else:
            self.model = model or settings.openai_model or "gpt-4o"

    async def _get_client(self):
        """Lazy-initialize the OpenAI/Azure client."""
        if self._client is not None:
            return self._client

        try:
            if settings.use_azure_openai:
                from openai import AsyncAzureOpenAI
                azure_key = getattr(settings, "azure_openai_api_key", None)
                if azure_key:
                    self._client = AsyncAzureOpenAI(
                        azure_endpoint=settings.azure_openai_endpoint,
                        api_key=azure_key,
                        api_version=settings.azure_openai_api_version,
                    )
                else:
                    from azure.identity import (
                        ClientSecretCredential,
                        get_bearer_token_provider,
                    )
                    cred = ClientSecretCredential(
                        tenant_id=settings.azure_tenant_id,
                        client_id=settings.azure_client_id,
                        client_secret=settings.azure_client_secret,
                    )
                    tp = get_bearer_token_provider(
                        cred, "https://cognitiveservices.azure.com/.default"
                    )
                    self._client = AsyncAzureOpenAI(
                        azure_endpoint=settings.azure_openai_endpoint,
                        azure_ad_token_provider=tp,
                        api_version=settings.azure_openai_api_version,
                    )
            else:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=settings.openai_api_key)
        except Exception as e:
            self.logger.error(f"Failed to init AI client: {e}")
            return None

        return self._client

    async def _call_llm(self, prompt: str, max_tokens: int = 1500) -> Optional[Dict]:
        """Call the LLM and parse JSON response."""
        client = await self._get_client()
        if client is None:
            return None

        try:
            import asyncio
            response = await asyncio.wait_for(
                client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": ADVISOR_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens,
                    response_format={"type": "json_object"},
                ),
                timeout=45.0,
            )
            content = response.choices[0].message.content
            return json.loads(content)
        except json.JSONDecodeError as e:
            self.logger.error(f"JSON parse error from LLM: {e}")
            return None
        except Exception as e:
            self.logger.error(f"LLM call failed: {e}")
            return None

    # ------------------------------------------------------------------
    # Signal evaluation
    # ------------------------------------------------------------------

    async def evaluate_signal(
        self,
        signal: Signal,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Evaluate a signal and return EXECUTE / REDUCE / SKIP decision.

        Args:
            signal: The trading signal to evaluate
            context: Dict with keys: regime, vix, trend, equity,
                     open_positions, daily_pnl, exposure, news,
                     ml_prediction, strategy_stats, etc.

        Returns:
            Decision dict with reasoning, position size, warnings.
        """
        inv = signal.invalidation
        targets = signal.targets
        entry = signal.entry_price
        stop = inv.stop_price if inv else entry * 0.95
        target = targets[0].price if targets else entry * 1.10

        stop_pct = (stop / entry - 1) * 100 if entry > 0 else -5.0
        target_pct = (target / entry - 1) * 100 if entry > 0 else 10.0
        rr = abs(target_pct / stop_pct) if stop_pct != 0 else 0

        ml = context.get("ml_prediction", {})
        strat_stats = context.get("strategy_stats", {})

        prompt = SIGNAL_EVALUATION_PROMPT.format(
            ticker=signal.ticker,
            direction=signal.direction.value,
            entry_price=entry,
            stop_price=stop,
            stop_pct=stop_pct,
            target_price=target,
            target_pct=target_pct,
            rr_ratio=rr,
            strategy=signal.strategy_id or "unknown",
            confidence=signal.confidence,
            horizon=signal.horizon.value if hasattr(signal.horizon, "value") else str(signal.horizon),
            regime=context.get("regime", "UNKNOWN"),
            vix=context.get("vix", "N/A"),
            trend=context.get("trend", "N/A"),
            sector=context.get("sector", "N/A"),
            equity=context.get("equity", 100000),
            open_positions=context.get("open_positions", 0),
            daily_pnl=context.get("daily_pnl", 0.0),
            exposure=context.get("exposure", 0.0),
            win_prob=ml.get("win_probability", "N/A"),
            signal_grade=ml.get("signal_grade", "N/A"),
            rec_size=ml.get("recommended_position_pct", "N/A"),
            news_summary=context.get("news", "No recent news."),
            strategy_win_rate=strat_stats.get("win_rate", "N/A"),
            avg_win=strat_stats.get("avg_win", 0),
            avg_loss=strat_stats.get("avg_loss", 0),
            streak=strat_stats.get("streak", "N/A"),
        )

        result = await self._call_llm(prompt)
        if result is None:
            # Fallback: basic rule-based decision
            return self._fallback_decision(signal, context)

        self.logger.info(
            f"AI Advisor: {signal.ticker} → {result.get('decision', '?')} "
            f"| {result.get('one_liner', '')}"
        )
        return result

    def _fallback_decision(
        self, signal: Signal, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Rule-based fallback when LLM is unavailable."""
        conf = signal.confidence
        vix = context.get("vix", 20)
        exposure = context.get("exposure", 0)

        if vix > 35 or exposure > 80 or conf < 50:
            decision = "SKIP"
        elif conf < 65 or vix > 28:
            decision = "REDUCE"
        else:
            decision = "EXECUTE"

        return {
            "decision": decision,
            "reasoning": {
                "technical": f"Confidence {conf}%",
                "fundamental": "LLM unavailable — using rule-based fallback",
                "risk": f"VIX={vix}, Exposure={exposure}%",
                "regime_fit": "N/A",
            },
            "confidence_override": None,
            "position_size_pct": min(signal.position_size_pct or 2.0, 3.0),
            "warnings": ["AI advisor unavailable — rule-based decision"],
            "one_liner": f"Fallback: {decision} based on rules (conf={conf}, VIX={vix})",
        }

    # ------------------------------------------------------------------
    # Market brief
    # ------------------------------------------------------------------

    async def generate_market_brief(
        self,
        market_data: Dict[str, Any],
        overnight_moves: str = "",
        events: str = "",
        active_signals: str = "",
        portfolio: str = "",
    ) -> Dict[str, Any]:
        """Generate a morning market brief."""
        prompt = MARKET_BRIEF_PROMPT.format(
            market_data=json.dumps(market_data, indent=2, default=str),
            overnight_moves=overnight_moves or "No significant overnight moves.",
            events=events or "No major events scheduled.",
            active_signals=active_signals or "No active signals.",
            portfolio=portfolio or "No open positions.",
        )
        result = await self._call_llm(prompt, max_tokens=1200)
        if result is None:
            return {
                "headline": "Market brief unavailable",
                "regime": "UNKNOWN",
                "action_plan": "Check market data feeds — AI advisor could not generate brief.",
            }
        return result

    # ------------------------------------------------------------------
    # Portfolio review
    # ------------------------------------------------------------------

    async def review_portfolio(
        self,
        positions: List[Dict[str, Any]],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Review portfolio and provide risk assessment."""
        prompt = PORTFOLIO_REVIEW_PROMPT.format(
            positions=json.dumps(positions[:20], indent=2, default=str),
            equity=metrics.get("equity", 0),
            cash=metrics.get("cash", 0),
            cash_pct=metrics.get("cash_pct", 100),
            exposure=metrics.get("exposure", 0),
            open_pnl=metrics.get("open_pnl", 0),
            today_pnl=metrics.get("today_pnl", 0),
            max_dd=metrics.get("max_drawdown", 0),
            corr_risk=metrics.get("correlation_risk", "LOW"),
            regime=metrics.get("regime", "N/A"),
        )
        result = await self._call_llm(prompt, max_tokens=1200)
        if result is None:
            return {
                "risk_score": 5,
                "risk_level": "MODERATE",
                "portfolio_grade": "N/A",
                "summary": "Portfolio review unavailable — AI advisor could not connect.",
            }
        return result

    # ------------------------------------------------------------------
    # Failure analysis & learning
    # ------------------------------------------------------------------

    async def analyze_failures(
        self,
        losing_trades: List[Dict[str, Any]],
        strategy_params: Dict[str, Any],
        market_conditions: str = "",
    ) -> Optional[Dict[str, Any]]:
        """Analyze losing trades and suggest improvements."""
        if not losing_trades:
            return None
        prompt = FAILURE_LEARNING_PROMPT.format(
            losing_trades=json.dumps(losing_trades[:30], indent=2, default=str),
            strategy_params=json.dumps(strategy_params, indent=2, default=str),
            market_conditions=market_conditions or "No specific conditions noted.",
        )
        return await self._call_llm(prompt, max_tokens=1500)
