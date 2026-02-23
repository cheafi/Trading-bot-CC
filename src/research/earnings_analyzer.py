"""
Earnings Analyzer - AI-powered earnings report analysis.

Condenses earnings reports into actionable trading briefs with:
- Beat/miss analysis
- Guidance assessment
- Key metrics extraction
- Trading implications
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class EarningsResult(str, Enum):
    """Earnings result classification."""
    BEAT = "beat"
    MISS = "miss"
    INLINE = "inline"


class GuidanceChange(str, Enum):
    """Guidance change classification."""
    RAISED = "raised"
    LOWERED = "lowered"
    MAINTAINED = "maintained"
    WITHDRAWN = "withdrawn"


@dataclass
class EarningsMetrics:
    """Key earnings metrics."""
    eps_actual: Optional[float] = None
    eps_estimate: Optional[float] = None
    eps_surprise_pct: Optional[float] = None
    
    revenue_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_surprise_pct: Optional[float] = None
    
    # Growth metrics
    eps_yoy_growth: Optional[float] = None
    revenue_yoy_growth: Optional[float] = None
    
    # Margins
    gross_margin: Optional[float] = None
    operating_margin: Optional[float] = None
    net_margin: Optional[float] = None
    
    # Guidance
    next_quarter_eps_guidance: Optional[tuple] = None
    full_year_eps_guidance: Optional[tuple] = None


@dataclass
class EarningsReport:
    """Comprehensive earnings report analysis."""
    ticker: str
    company_name: str
    fiscal_quarter: str
    fiscal_year: int
    report_date: datetime
    
    # Results
    eps_result: EarningsResult = EarningsResult.INLINE
    revenue_result: EarningsResult = EarningsResult.INLINE
    guidance_change: GuidanceChange = GuidanceChange.MAINTAINED
    
    # Metrics
    metrics: EarningsMetrics = field(default_factory=EarningsMetrics)
    
    # Analysis
    headline: str = ""
    key_highlights: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    management_comments: List[str] = field(default_factory=list)
    
    # Trading implications
    overall_sentiment: str = "neutral"  # bullish, bearish, neutral
    expected_price_reaction: str = ""
    trading_recommendation: str = ""
    
    # Historical context
    beat_streak: int = 0
    avg_post_earnings_move: float = 0.0
    
    # AI summary
    ai_summary: str = ""


class EarningsAnalyzer:
    """
    Analyzes earnings reports and generates actionable briefs.
    
    Features:
    - Beat/miss detection
    - Guidance analysis
    - Key metrics extraction
    - Historical comparison
    - Trading implications
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.openai_client = None
        self._init_openai()
        
    def _init_openai(self):
        """Initialize OpenAI client."""
        try:
            from openai import AsyncOpenAI
            import os
            
            api_key = os.getenv('OPENAI_API_KEY')
            if api_key:
                self.openai_client = AsyncOpenAI(api_key=api_key)
        except Exception as e:
            logger.warning(f"OpenAI not available: {e}")
    
    async def analyze_earnings(
        self,
        ticker: str,
        earnings_data: Dict
    ) -> EarningsReport:
        """
        Analyze earnings report data.
        
        Args:
            ticker: Stock ticker
            earnings_data: Raw earnings data with actuals, estimates, guidance
            
        Returns:
            EarningsReport with full analysis
        """
        report = EarningsReport(
            ticker=ticker,
            company_name=earnings_data.get('company_name', ticker),
            fiscal_quarter=earnings_data.get('fiscal_quarter', 'Q1'),
            fiscal_year=earnings_data.get('fiscal_year', datetime.now().year),
            report_date=earnings_data.get('report_date', datetime.now())
        )
        
        # Extract metrics
        report.metrics = self._extract_metrics(earnings_data)
        
        # Determine results
        report.eps_result = self._determine_result(
            report.metrics.eps_actual,
            report.metrics.eps_estimate
        )
        report.revenue_result = self._determine_result(
            report.metrics.revenue_actual,
            report.metrics.revenue_estimate
        )
        
        # Analyze guidance
        report.guidance_change = self._analyze_guidance(earnings_data)
        
        # Generate headline
        report.headline = self._generate_headline(report)
        
        # Extract highlights
        report.key_highlights = self._extract_highlights(earnings_data, report)
        report.concerns = self._extract_concerns(earnings_data, report)
        
        # Determine sentiment and trading implications
        report.overall_sentiment = self._determine_sentiment(report)
        report.expected_price_reaction = self._estimate_price_reaction(report)
        report.trading_recommendation = self._generate_recommendation(report)
        
        # AI enhancement
        if self.openai_client:
            await self._enhance_with_ai(report, earnings_data)
        
        return report
    
    def _extract_metrics(self, data: Dict) -> EarningsMetrics:
        """Extract key metrics from earnings data."""
        return EarningsMetrics(
            eps_actual=data.get('eps_actual'),
            eps_estimate=data.get('eps_estimate'),
            eps_surprise_pct=self._calc_surprise(
                data.get('eps_actual'),
                data.get('eps_estimate')
            ),
            revenue_actual=data.get('revenue_actual'),
            revenue_estimate=data.get('revenue_estimate'),
            revenue_surprise_pct=self._calc_surprise(
                data.get('revenue_actual'),
                data.get('revenue_estimate')
            ),
            eps_yoy_growth=data.get('eps_yoy_growth'),
            revenue_yoy_growth=data.get('revenue_yoy_growth'),
            gross_margin=data.get('gross_margin'),
            operating_margin=data.get('operating_margin'),
            net_margin=data.get('net_margin')
        )
    
    def _calc_surprise(
        self,
        actual: Optional[float],
        estimate: Optional[float]
    ) -> Optional[float]:
        """Calculate surprise percentage."""
        if actual is None or estimate is None or estimate == 0:
            return None
        return (actual - estimate) / abs(estimate) * 100
    
    def _determine_result(
        self,
        actual: Optional[float],
        estimate: Optional[float]
    ) -> EarningsResult:
        """Determine if metric beat, missed, or inline."""
        if actual is None or estimate is None:
            return EarningsResult.INLINE
            
        surprise_pct = self._calc_surprise(actual, estimate)
        
        if surprise_pct > 2:
            return EarningsResult.BEAT
        elif surprise_pct < -2:
            return EarningsResult.MISS
        else:
            return EarningsResult.INLINE
    
    def _analyze_guidance(self, data: Dict) -> GuidanceChange:
        """Analyze guidance changes."""
        guidance_text = data.get('guidance', '').lower()
        
        if 'raise' in guidance_text or 'increase' in guidance_text or 'higher' in guidance_text:
            return GuidanceChange.RAISED
        elif 'lower' in guidance_text or 'reduce' in guidance_text or 'cut' in guidance_text:
            return GuidanceChange.LOWERED
        elif 'withdraw' in guidance_text or 'suspend' in guidance_text:
            return GuidanceChange.WITHDRAWN
        else:
            return GuidanceChange.MAINTAINED
    
    def _generate_headline(self, report: EarningsReport) -> str:
        """Generate earnings headline."""
        eps_word = report.eps_result.value.capitalize() + "s"
        rev_word = report.revenue_result.value.capitalize() + "s"
        
        if report.eps_result == EarningsResult.BEAT and report.revenue_result == EarningsResult.BEAT:
            if report.guidance_change == GuidanceChange.RAISED:
                return f"{report.ticker} Posts Strong Beat, Raises Guidance"
            return f"{report.ticker} {eps_word} on EPS and Revenue"
        elif report.eps_result == EarningsResult.MISS or report.revenue_result == EarningsResult.MISS:
            if report.guidance_change == GuidanceChange.LOWERED:
                return f"{report.ticker} Misses Estimates, Cuts Outlook"
            return f"{report.ticker} Falls Short on {'EPS' if report.eps_result == EarningsResult.MISS else 'Revenue'}"
        else:
            return f"{report.ticker} Reports In-Line Results"
    
    def _extract_highlights(self, data: Dict, report: EarningsReport) -> List[str]:
        """Extract positive highlights."""
        highlights = []
        
        if report.eps_result == EarningsResult.BEAT:
            surprise = report.metrics.eps_surprise_pct
            if surprise:
                highlights.append(f"EPS beat by {surprise:.1f}%")
        
        if report.revenue_result == EarningsResult.BEAT:
            surprise = report.metrics.revenue_surprise_pct
            if surprise:
                highlights.append(f"Revenue beat by {surprise:.1f}%")
        
        if report.metrics.eps_yoy_growth and report.metrics.eps_yoy_growth > 20:
            highlights.append(f"EPS grew {report.metrics.eps_yoy_growth:.0f}% YoY")
        
        if report.guidance_change == GuidanceChange.RAISED:
            highlights.append("Management raised full-year guidance")
        
        # Add custom highlights from data
        if 'highlights' in data:
            highlights.extend(data['highlights'][:3])
        
        return highlights[:5]
    
    def _extract_concerns(self, data: Dict, report: EarningsReport) -> List[str]:
        """Extract concerns from report."""
        concerns = []
        
        if report.eps_result == EarningsResult.MISS:
            surprise = report.metrics.eps_surprise_pct
            if surprise:
                concerns.append(f"EPS missed by {abs(surprise):.1f}%")
        
        if report.revenue_result == EarningsResult.MISS:
            surprise = report.metrics.revenue_surprise_pct
            if surprise:
                concerns.append(f"Revenue missed by {abs(surprise):.1f}%")
        
        if report.guidance_change == GuidanceChange.LOWERED:
            concerns.append("Management lowered guidance")
        elif report.guidance_change == GuidanceChange.WITHDRAWN:
            concerns.append("Guidance withdrawn")
        
        if report.metrics.gross_margin and report.metrics.gross_margin < 30:
            concerns.append(f"Gross margin at {report.metrics.gross_margin:.1f}%")
        
        # Add custom concerns from data
        if 'concerns' in data:
            concerns.extend(data['concerns'][:3])
        
        return concerns[:5]
    
    def _determine_sentiment(self, report: EarningsReport) -> str:
        """Determine overall sentiment."""
        score = 0
        
        # EPS result
        if report.eps_result == EarningsResult.BEAT:
            score += 2
        elif report.eps_result == EarningsResult.MISS:
            score -= 2
        
        # Revenue result
        if report.revenue_result == EarningsResult.BEAT:
            score += 1
        elif report.revenue_result == EarningsResult.MISS:
            score -= 1
        
        # Guidance
        if report.guidance_change == GuidanceChange.RAISED:
            score += 2
        elif report.guidance_change == GuidanceChange.LOWERED:
            score -= 2
        elif report.guidance_change == GuidanceChange.WITHDRAWN:
            score -= 3
        
        if score >= 3:
            return "bullish"
        elif score <= -3:
            return "bearish"
        else:
            return "neutral"
    
    def _estimate_price_reaction(self, report: EarningsReport) -> str:
        """Estimate expected price reaction."""
        if report.overall_sentiment == "bullish":
            if report.guidance_change == GuidanceChange.RAISED:
                return "Strong positive reaction expected (+3-5%)"
            return "Moderate positive reaction expected (+1-3%)"
        elif report.overall_sentiment == "bearish":
            if report.guidance_change in [GuidanceChange.LOWERED, GuidanceChange.WITHDRAWN]:
                return "Strong negative reaction expected (-5-8%)"
            return "Moderate negative reaction expected (-2-4%)"
        else:
            return "Muted reaction expected (-1% to +1%)"
    
    def _generate_recommendation(self, report: EarningsReport) -> str:
        """Generate trading recommendation."""
        if report.overall_sentiment == "bullish":
            return "Consider buying dips post-earnings. Positive momentum likely."
        elif report.overall_sentiment == "bearish":
            return "Wait for stabilization before any long positions. Risk elevated."
        else:
            return "Mixed results suggest range-bound trading. Watch for trend confirmation."
    
    async def _enhance_with_ai(self, report: EarningsReport, data: Dict):
        """Enhance analysis with AI."""
        if not self.openai_client:
            return
            
        context = f"""
Ticker: {report.ticker}
Quarter: {report.fiscal_quarter} {report.fiscal_year}
EPS: ${report.metrics.eps_actual} vs ${report.metrics.eps_estimate} expected ({report.eps_result.value})
Revenue: ${report.metrics.revenue_actual}B vs ${report.metrics.revenue_estimate}B expected ({report.revenue_result.value})
Guidance: {report.guidance_change.value}
Highlights: {', '.join(report.key_highlights[:3])}
Concerns: {', '.join(report.concerns[:3])}
"""
        
        prompt = f"""Analyze this earnings report and provide a 2-3 sentence executive summary for traders:

{context}

Focus on: What matters most for the stock price? What should traders watch?"""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-5.2-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
                temperature=0.4
            )
            
            report.ai_summary = response.choices[0].message.content
            
        except Exception as e:
            logger.warning(f"AI enhancement failed: {e}")
    
    def format_report_brief(self, report: EarningsReport) -> str:
        """Format earnings report as brief text."""
        lines = []
        
        # Header
        emoji = "🟢" if report.overall_sentiment == "bullish" else "🔴" if report.overall_sentiment == "bearish" else "🟡"
        lines.append(f"{emoji} **{report.ticker} Earnings** - {report.fiscal_quarter} {report.fiscal_year}")
        lines.append("")
        lines.append(f"**{report.headline}**")
        lines.append("")
        
        # Key metrics
        lines.append("**Results:**")
        if report.metrics.eps_actual:
            eps_emoji = "✅" if report.eps_result == EarningsResult.BEAT else "❌" if report.eps_result == EarningsResult.MISS else "➡️"
            lines.append(f"  {eps_emoji} EPS: ${report.metrics.eps_actual:.2f} vs ${report.metrics.eps_estimate:.2f} exp")
        
        if report.metrics.revenue_actual:
            rev_emoji = "✅" if report.revenue_result == EarningsResult.BEAT else "❌" if report.revenue_result == EarningsResult.MISS else "➡️"
            lines.append(f"  {rev_emoji} Revenue: ${report.metrics.revenue_actual:.2f}B vs ${report.metrics.revenue_estimate:.2f}B exp")
        
        lines.append(f"  📊 Guidance: {report.guidance_change.value.title()}")
        lines.append("")
        
        # Highlights
        if report.key_highlights:
            lines.append("**✨ Highlights:**")
            for h in report.key_highlights[:3]:
                lines.append(f"  • {h}")
        
        # Concerns
        if report.concerns:
            lines.append("")
            lines.append("**⚠️ Concerns:**")
            for c in report.concerns[:3]:
                lines.append(f"  • {c}")
        
        # Trading implication
        lines.append("")
        lines.append(f"**📈 Outlook:** {report.expected_price_reaction}")
        lines.append(f"**💡 Action:** {report.trading_recommendation}")
        
        # AI Summary
        if report.ai_summary:
            lines.append("")
            lines.append(f"**🤖 AI Take:** {report.ai_summary}")
        
        return "\n".join(lines)
