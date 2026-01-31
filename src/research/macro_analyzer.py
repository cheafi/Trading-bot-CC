"""
Macro Analyzer - Economic and macroeconomic news analysis.

Monitors and analyzes:
- Fed decisions and commentary
- Economic indicators (CPI, jobs, GDP)
- Global macro events
- Market-moving announcements
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class MacroEventType(str, Enum):
    """Types of macro events."""
    FED_DECISION = "fed_decision"
    FED_SPEECH = "fed_speech"
    CPI = "cpi"
    PPI = "ppi"
    EMPLOYMENT = "employment"
    GDP = "gdp"
    RETAIL_SALES = "retail_sales"
    HOUSING = "housing"
    PMI = "pmi"
    TRADE = "trade"
    GEOPOLITICAL = "geopolitical"
    CENTRAL_BANK = "central_bank"


class ImpactLevel(str, Enum):
    """Impact level classification."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class MacroEvent:
    """Macro economic event."""
    event_type: MacroEventType
    title: str
    timestamp: datetime
    
    # Data
    actual: Optional[float] = None
    forecast: Optional[float] = None
    previous: Optional[float] = None
    
    # Analysis
    surprise_direction: str = "inline"  # above, below, inline
    surprise_magnitude: float = 0.0
    
    # Impact
    impact_level: ImpactLevel = ImpactLevel.MEDIUM
    market_reaction: str = ""
    
    # Implications
    fed_implications: str = ""
    bond_implications: str = ""
    equity_implications: str = ""
    sector_implications: Dict[str, str] = field(default_factory=dict)
    
    # AI summary
    summary: str = ""
    trading_notes: str = ""


@dataclass
class MacroOutlook:
    """Current macroeconomic outlook."""
    generated_at: datetime
    
    # Economic assessment
    growth_outlook: str = "stable"  # accelerating, stable, slowing, contracting
    inflation_trend: str = "stable"  # rising, stable, falling
    employment_trend: str = "strong"  # strong, stable, weakening
    
    # Fed outlook
    fed_stance: str = "neutral"  # hawkish, neutral, dovish
    rate_path: str = "hold"  # hiking, hold, cutting
    next_meeting_expectation: str = ""
    
    # Market implications
    risk_environment: str = "neutral"  # risk_on, neutral, risk_off
    
    # Key themes
    themes: List[str] = field(default_factory=list)
    
    # Upcoming events
    key_events_ahead: List[Dict] = field(default_factory=list)
    
    # AI summary
    summary: str = ""


class MacroAnalyzer:
    """
    Analyzes macroeconomic events and their market implications.
    
    Features:
    - Economic indicator analysis
    - Fed policy interpretation
    - Market impact assessment
    - Sector-specific implications
    """
    
    # Economic calendar importance
    HIGH_IMPACT_EVENTS = [
        MacroEventType.FED_DECISION,
        MacroEventType.CPI,
        MacroEventType.EMPLOYMENT,
        MacroEventType.GDP
    ]
    
    MEDIUM_IMPACT_EVENTS = [
        MacroEventType.PPI,
        MacroEventType.RETAIL_SALES,
        MacroEventType.PMI,
        MacroEventType.FED_SPEECH
    ]
    
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
    
    async def analyze_event(
        self,
        event_data: Dict
    ) -> MacroEvent:
        """
        Analyze a macroeconomic event.
        
        Args:
            event_data: Raw event data with type, actual, forecast, etc.
            
        Returns:
            MacroEvent with full analysis
        """
        event_type = self._classify_event_type(event_data.get('title', ''))
        
        event = MacroEvent(
            event_type=event_type,
            title=event_data.get('title', ''),
            timestamp=event_data.get('timestamp', datetime.now()),
            actual=event_data.get('actual'),
            forecast=event_data.get('forecast'),
            previous=event_data.get('previous')
        )
        
        # Determine surprise
        if event.actual is not None and event.forecast is not None:
            diff = event.actual - event.forecast
            event.surprise_magnitude = abs(diff)
            
            if diff > event.forecast * 0.02:
                event.surprise_direction = "above"
            elif diff < -event.forecast * 0.02:
                event.surprise_direction = "below"
            else:
                event.surprise_direction = "inline"
        
        # Set impact level
        if event_type in self.HIGH_IMPACT_EVENTS:
            event.impact_level = ImpactLevel.HIGH
        elif event_type in self.MEDIUM_IMPACT_EVENTS:
            event.impact_level = ImpactLevel.MEDIUM
        else:
            event.impact_level = ImpactLevel.LOW
        
        # Analyze implications
        event.fed_implications = self._analyze_fed_implications(event)
        event.bond_implications = self._analyze_bond_implications(event)
        event.equity_implications = self._analyze_equity_implications(event)
        event.sector_implications = self._analyze_sector_implications(event)
        
        # Generate summary
        event.summary = self._generate_summary(event)
        event.trading_notes = self._generate_trading_notes(event)
        
        # AI enhancement
        if self.openai_client:
            await self._enhance_with_ai(event)
        
        return event
    
    def _classify_event_type(self, title: str) -> MacroEventType:
        """Classify event type from title."""
        title_lower = title.lower()
        
        if 'fomc' in title_lower or 'fed' in title_lower and 'rate' in title_lower:
            return MacroEventType.FED_DECISION
        elif 'powell' in title_lower or 'fed' in title_lower:
            return MacroEventType.FED_SPEECH
        elif 'cpi' in title_lower or 'consumer price' in title_lower:
            return MacroEventType.CPI
        elif 'ppi' in title_lower or 'producer price' in title_lower:
            return MacroEventType.PPI
        elif 'employment' in title_lower or 'payroll' in title_lower or 'jobs' in title_lower:
            return MacroEventType.EMPLOYMENT
        elif 'gdp' in title_lower:
            return MacroEventType.GDP
        elif 'retail' in title_lower:
            return MacroEventType.RETAIL_SALES
        elif 'pmi' in title_lower or 'manufacturing' in title_lower:
            return MacroEventType.PMI
        elif 'housing' in title_lower or 'home' in title_lower:
            return MacroEventType.HOUSING
        else:
            return MacroEventType.GEOPOLITICAL
    
    def _analyze_fed_implications(self, event: MacroEvent) -> str:
        """Analyze implications for Fed policy."""
        if event.event_type == MacroEventType.CPI:
            if event.surprise_direction == "above":
                return "Hot inflation reading increases pressure on Fed to maintain restrictive policy."
            elif event.surprise_direction == "below":
                return "Cooling inflation gives Fed more flexibility for rate cuts."
            else:
                return "In-line reading unlikely to change Fed's current stance."
        
        elif event.event_type == MacroEventType.EMPLOYMENT:
            if event.surprise_direction == "above":
                return "Strong job growth supports Fed's patient approach to rate cuts."
            elif event.surprise_direction == "below":
                return "Weakening labor market may prompt Fed to consider easier policy."
            else:
                return "Steady employment consistent with soft landing scenario."
        
        elif event.event_type == MacroEventType.GDP:
            if event.surprise_direction == "above":
                return "Strong growth reduces urgency for rate cuts."
            elif event.surprise_direction == "below":
                return "Slowing growth increases likelihood of Fed easing."
            else:
                return "Growth in line with Fed projections."
        
        return "Limited direct implications for Fed policy."
    
    def _analyze_bond_implications(self, event: MacroEvent) -> str:
        """Analyze implications for bond market."""
        if event.event_type in [MacroEventType.CPI, MacroEventType.PPI]:
            if event.surprise_direction == "above":
                return "Yields likely to rise on hotter inflation. Duration risk elevated."
            elif event.surprise_direction == "below":
                return "Yields may fall. Duration extension opportunities."
            else:
                return "Neutral impact on yields."
        
        elif event.event_type == MacroEventType.FED_DECISION:
            if event.surprise_direction == "above":  # Hawkish surprise
                return "Hawkish surprise pressures bond prices. Short-end particularly vulnerable."
            elif event.surprise_direction == "below":  # Dovish surprise
                return "Dovish pivot supportive for bonds across curve."
        
        return "Monitor Treasury yields for direction."
    
    def _analyze_equity_implications(self, event: MacroEvent) -> str:
        """Analyze implications for equity markets."""
        if event.event_type == MacroEventType.CPI:
            if event.surprise_direction == "above":
                return "Hot CPI negative for growth stocks. Value and energy may outperform."
            elif event.surprise_direction == "below":
                return "Cooler CPI supportive for growth and tech stocks."
        
        elif event.event_type == MacroEventType.EMPLOYMENT:
            if event.surprise_direction == "above":
                return "Strong jobs data generally positive for cyclicals and financials."
            elif event.surprise_direction == "below":
                return "Weak jobs data favors defensive sectors."
        
        elif event.event_type == MacroEventType.GDP:
            if event.surprise_direction == "above":
                return "Strong GDP supports cyclical rotation."
            elif event.surprise_direction == "below":
                return "Weak GDP favors defensive positioning."
        
        return "Monitor market reaction for sector opportunities."
    
    def _analyze_sector_implications(self, event: MacroEvent) -> Dict[str, str]:
        """Analyze sector-specific implications."""
        implications = {}
        
        if event.event_type == MacroEventType.CPI:
            if event.surprise_direction == "above":
                implications["Technology"] = "Pressure on growth valuations"
                implications["Financials"] = "Higher rates may support margins"
                implications["Energy"] = "Inflation hedge, may outperform"
                implications["Utilities"] = "Rate sensitivity a headwind"
            else:
                implications["Technology"] = "Lower rates supportive"
                implications["Financials"] = "Net interest margin pressure"
                implications["Utilities"] = "Lower rates beneficial"
        
        elif event.event_type == MacroEventType.EMPLOYMENT:
            if event.surprise_direction == "above":
                implications["Consumer Discretionary"] = "Strong consumer supports spending"
                implications["Industrials"] = "Strong economy positive"
                implications["Financials"] = "Credit quality supported"
        
        return implications
    
    def _generate_summary(self, event: MacroEvent) -> str:
        """Generate event summary."""
        parts = []
        
        parts.append(f"**{event.title}**")
        
        if event.actual is not None:
            parts.append(f"Actual: {event.actual}")
            if event.forecast is not None:
                parts.append(f"Forecast: {event.forecast}")
            if event.previous is not None:
                parts.append(f"Previous: {event.previous}")
        
        if event.surprise_direction != "inline":
            parts.append(f"Surprise: {event.surprise_direction.title()}")
        
        return " | ".join(parts)
    
    def _generate_trading_notes(self, event: MacroEvent) -> str:
        """Generate trading notes."""
        notes = []
        
        if event.impact_level == ImpactLevel.HIGH:
            notes.append("⚠️ High-impact event - expect volatility")
        
        if event.surprise_direction == "above":
            notes.append("Above-consensus reading may trigger risk-off initially")
        elif event.surprise_direction == "below":
            notes.append("Below-consensus reading may trigger risk-on sentiment")
        
        if event.event_type in [MacroEventType.CPI, MacroEventType.EMPLOYMENT]:
            notes.append("Watch Treasury yields and Fed funds futures for market interpretation")
        
        return " | ".join(notes) if notes else "Standard market reaction expected"
    
    async def _enhance_with_ai(self, event: MacroEvent):
        """Enhance analysis with AI."""
        if not self.openai_client:
            return
            
        prompt = f"""Analyze this economic event for traders:

Event: {event.title}
Actual: {event.actual}, Forecast: {event.forecast}, Previous: {event.previous}
Surprise: {event.surprise_direction}
Impact Level: {event.impact_level.value}

Provide a 2-sentence trading-focused summary of what this means for markets today."""

        try:
            response = await self.openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
                temperature=0.4
            )
            
            event.summary = response.choices[0].message.content
            
        except Exception as e:
            logger.warning(f"AI enhancement failed: {e}")
    
    def generate_macro_outlook(
        self,
        recent_events: List[MacroEvent]
    ) -> MacroOutlook:
        """Generate overall macro outlook."""
        outlook = MacroOutlook(generated_at=datetime.now())
        
        if not recent_events:
            return outlook
        
        # Analyze trends from recent events
        cpi_events = [e for e in recent_events if e.event_type == MacroEventType.CPI]
        employment_events = [e for e in recent_events if e.event_type == MacroEventType.EMPLOYMENT]
        gdp_events = [e for e in recent_events if e.event_type == MacroEventType.GDP]
        
        # Inflation trend
        if cpi_events:
            latest_cpi = cpi_events[0]
            if latest_cpi.surprise_direction == "above":
                outlook.inflation_trend = "rising"
            elif latest_cpi.surprise_direction == "below":
                outlook.inflation_trend = "falling"
        
        # Employment trend
        if employment_events:
            latest_emp = employment_events[0]
            if latest_emp.surprise_direction == "above":
                outlook.employment_trend = "strong"
            elif latest_emp.surprise_direction == "below":
                outlook.employment_trend = "weakening"
        
        # Growth outlook
        if gdp_events:
            latest_gdp = gdp_events[0]
            if latest_gdp.surprise_direction == "above":
                outlook.growth_outlook = "accelerating"
            elif latest_gdp.surprise_direction == "below":
                outlook.growth_outlook = "slowing"
        
        # Fed stance inference
        if outlook.inflation_trend == "rising" and outlook.employment_trend == "strong":
            outlook.fed_stance = "hawkish"
            outlook.rate_path = "hold"
        elif outlook.inflation_trend == "falling" and outlook.employment_trend == "weakening":
            outlook.fed_stance = "dovish"
            outlook.rate_path = "cutting"
        else:
            outlook.fed_stance = "neutral"
            outlook.rate_path = "hold"
        
        # Risk environment
        if outlook.growth_outlook in ["accelerating", "stable"] and outlook.inflation_trend != "rising":
            outlook.risk_environment = "risk_on"
        elif outlook.growth_outlook in ["slowing", "contracting"]:
            outlook.risk_environment = "risk_off"
        else:
            outlook.risk_environment = "neutral"
        
        # Key themes
        outlook.themes = self._identify_themes(recent_events, outlook)
        
        # Generate summary
        outlook.summary = self._generate_outlook_summary(outlook)
        
        return outlook
    
    def _identify_themes(
        self,
        events: List[MacroEvent],
        outlook: MacroOutlook
    ) -> List[str]:
        """Identify key macro themes."""
        themes = []
        
        if outlook.inflation_trend == "rising":
            themes.append("Persistent inflation concerns")
        elif outlook.inflation_trend == "falling":
            themes.append("Disinflation progress")
        
        if outlook.fed_stance == "hawkish":
            themes.append("Higher for longer rate expectations")
        elif outlook.fed_stance == "dovish":
            themes.append("Rate cut expectations building")
        
        if outlook.growth_outlook == "slowing":
            themes.append("Growth deceleration watch")
        
        if outlook.employment_trend == "strong":
            themes.append("Resilient labor market")
        
        return themes[:5]
    
    def _generate_outlook_summary(self, outlook: MacroOutlook) -> str:
        """Generate outlook summary."""
        lines = []
        
        lines.append(f"📊 **Macro Outlook** - {outlook.generated_at.strftime('%Y-%m-%d')}")
        lines.append("")
        lines.append(f"**Growth:** {outlook.growth_outlook.title()}")
        lines.append(f"**Inflation:** {outlook.inflation_trend.title()}")
        lines.append(f"**Employment:** {outlook.employment_trend.title()}")
        lines.append("")
        lines.append(f"**Fed Stance:** {outlook.fed_stance.title()}")
        lines.append(f"**Rate Path:** {outlook.rate_path.title()}")
        lines.append("")
        lines.append(f"**Risk Environment:** {outlook.risk_environment.replace('_', ' ').title()}")
        
        if outlook.themes:
            lines.append("")
            lines.append("**Key Themes:**")
            for theme in outlook.themes:
                lines.append(f"  • {theme}")
        
        return "\n".join(lines)
    
    def format_event_brief(self, event: MacroEvent) -> str:
        """Format event as brief message."""
        impact_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(event.impact_level.value, "⚪")
        
        lines = []
        lines.append(f"{impact_emoji} **{event.title}**")
        
        if event.actual is not None:
            result = ""
            if event.surprise_direction == "above":
                result = "📈 Above Expectations"
            elif event.surprise_direction == "below":
                result = "📉 Below Expectations"
            else:
                result = "➡️ In Line"
            
            lines.append(f"Result: {result}")
            lines.append(f"Actual: {event.actual} | Forecast: {event.forecast} | Prior: {event.previous}")
        
        if event.summary:
            lines.append("")
            lines.append(event.summary)
        
        if event.trading_notes:
            lines.append("")
            lines.append(f"💡 {event.trading_notes}")
        
        return "\n".join(lines)
