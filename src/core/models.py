"""
TradingAI Bot - Data Models
Pydantic models for all data structures.
"""
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================

class Direction(str, Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    CLOSE = "CLOSE"
    NEUTRAL = "NEUTRAL"


class Horizon(str, Enum):
    INTRADAY = "INTRADAY"
    SWING_1_5D = "SWING_1_5D"
    SWING_5_15D = "SWING_5_15D"
    POSITION_15_60D = "POSITION_15_60D"


class StopType(str, Enum):
    HARD = "HARD"
    CLOSE_BELOW = "CLOSE_BELOW"
    TRAILING_ATR = "TRAILING_ATR"


class SignalStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    CLOSED = "closed"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class VolatilityRegime(str, Enum):
    CRISIS = "CRISIS"
    HIGH_VOL = "HIGH_VOL"
    NORMAL = "NORMAL"
    LOW_VOL = "LOW_VOL"


class TrendRegime(str, Enum):
    STRONG_UPTREND = "STRONG_UPTREND"
    UPTREND = "UPTREND"
    NEUTRAL = "NEUTRAL"
    DOWNTREND = "DOWNTREND"
    STRONG_DOWNTREND = "STRONG_DOWNTREND"


class RiskRegime(str, Enum):
    RISK_ON = "RISK_ON"
    NEUTRAL = "NEUTRAL"
    RISK_OFF = "RISK_OFF"


class SentimentLabel(str, Enum):
    VERY_BEARISH = "very_bearish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    BULLISH = "bullish"
    VERY_BULLISH = "very_bullish"


# =============================================================================
# MARKET DATA MODELS
# =============================================================================

class OHLCV(BaseModel):
    """OHLCV price bar."""
    ts: datetime
    ticker: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    vwap: Optional[float] = None
    trade_count: Optional[int] = None
    
    class Config:
        from_attributes = True


class Quote(BaseModel):
    """Real-time quote."""
    ticker: str
    price: float
    change: float
    change_pct: float
    volume: int
    bid: Optional[float] = None
    ask: Optional[float] = None
    updated_at: datetime


class MarketSnapshot(BaseModel):
    """Market overview snapshot."""
    timestamp: datetime
    
    # Indices
    spx_close: float
    spx_change_pct: float
    ndx_close: float
    ndx_change_pct: float
    djia_close: float
    djia_change_pct: float
    iwm_close: float
    iwm_change_pct: float
    
    # Volatility
    vix: float
    vix_change: float
    vix_term_structure: float  # VIX / VIX3M
    
    # Futures
    es_futures: Optional[float] = None
    nq_futures: Optional[float] = None
    
    # Put/Call
    put_call_ratio: Optional[float] = None


# =============================================================================
# FEATURE MODELS
# =============================================================================

class TechnicalFeatures(BaseModel):
    """Technical analysis features for a ticker."""
    ticker: str
    ts: datetime
    
    # Returns
    return_1d: float
    return_5d: float
    return_21d: float
    return_63d: Optional[float] = None
    
    # Volatility
    volatility_21d: float
    atr_14: float
    rsi_14: float
    
    # Moving averages
    sma_20: float
    sma_50: float
    sma_200: float
    dist_from_sma20: float
    dist_from_sma50: float
    dist_from_sma200: float
    
    # Bollinger bands
    bb_upper: float
    bb_lower: float
    bb_width: float
    
    # Volume
    volume_sma_20: float
    relative_volume: float
    obv: Optional[float] = None
    
    # Trend
    adx_14: float
    macd: float
    macd_signal: float
    macd_histogram: float
    
    # Composite scores
    momentum_score: Optional[float] = None
    trend_score: Optional[float] = None
    volatility_rank: Optional[float] = None


class MarketBreadth(BaseModel):
    """Market breadth indicators."""
    ts: datetime
    
    # Advance/Decline
    advancers: int
    decliners: int
    unchanged: int
    ad_ratio: float
    ad_line: float
    mcclellan_oscillator: float
    mcclellan_summation: float
    
    # Highs/Lows
    new_52w_highs: int
    new_52w_lows: int
    hi_lo_ratio: float
    
    # % Above MAs
    pct_above_sma20: float
    pct_above_sma50: float
    pct_above_sma200: float
    
    # Volatility
    vix_close: float
    vix_term_structure: float
    
    # Sector performance
    sector_performance: Dict[str, float]
    
    # Regime
    risk_on_score: float
    regime_label: str


class MarketRegime(BaseModel):
    """Current market regime classification."""
    timestamp: datetime
    volatility: VolatilityRegime
    trend: TrendRegime
    risk: RiskRegime
    active_strategies: List[str]
    
    @property
    def should_trade(self) -> bool:
        """Check if conditions allow trading."""
        return (
            self.volatility != VolatilityRegime.CRISIS and
            self.trend != TrendRegime.STRONG_DOWNTREND and
            len(self.active_strategies) > 0
        )


# =============================================================================
# SIGNAL MODELS
# =============================================================================

class Target(BaseModel):
    """Price target with position allocation."""
    price: float
    pct_position: float = Field(ge=0, le=100)


class Invalidation(BaseModel):
    """Stop loss / invalidation logic."""
    stop_price: float
    stop_type: StopType
    condition: Optional[str] = None


class Signal(BaseModel):
    """Trading signal output."""
    id: Optional[UUID] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Core signal
    ticker: str = Field(pattern=r"^[A-Z]{1,5}$")
    direction: Direction
    horizon: Horizon
    
    # Price levels
    entry_price: float
    entry_type: str = "market"
    invalidation: Invalidation
    targets: List[Target] = Field(min_length=1, max_length=3)
    
    # Context
    entry_logic: str = Field(max_length=200)
    catalyst: str
    key_risks: List[str] = Field(max_length=5)
    
    # Scoring
    confidence: int = Field(ge=0, le=100)
    rationale: str = Field(max_length=500)
    
    # Risk management
    position_size_pct: Optional[float] = None
    risk_reward_ratio: Optional[float] = None
    
    # Strategy metadata
    strategy_id: Optional[str] = None
    strategy_version: Optional[str] = None
    
    # Feature snapshot for backtesting
    feature_snapshot: Optional[Dict[str, Any]] = None
    
    # Lifecycle
    status: SignalStatus = SignalStatus.PENDING
    gpt_validated: bool = False
    gpt_rationale: Optional[str] = None
    
    def to_table_row(self) -> str:
        """Format as structured table row."""
        targets_str = " / ".join([f"${t.price:.2f} ({t.pct_position}%)" for t in self.targets])
        risks_str = "; ".join(self.key_risks[:3])
        
        return (
            f"| {self.ticker} | {self.direction.value} | {self.horizon.value} | "
            f"{self.entry_logic[:50]}... | ${self.invalidation.stop_price:.2f} | "
            f"{targets_str} | {self.catalyst[:30]}... | {risks_str[:50]}... | "
            f"{self.confidence} | {self.rationale[:50]}... |"
        )
    
    class Config:
        from_attributes = True


class ValidatedSignal(BaseModel):
    """Signal after GPT validation."""
    signal: Signal
    approved: bool
    issues: List[str] = []
    conflicts: List[str] = []
    adjusted_confidence: int
    gpt_rationale: str


# =============================================================================
# DOCUMENT MODELS
# =============================================================================

class NewsArticle(BaseModel):
    """News article with sentiment."""
    id: Optional[UUID] = None
    published_at: datetime
    source: str
    author: Optional[str] = None
    title: str
    summary: Optional[str] = None
    content: Optional[str] = None
    url: str
    
    tickers: List[str] = []
    sectors: List[str] = []
    topics: List[str] = []
    
    sentiment_score: Optional[float] = None  # -100 to +100
    sentiment_label: Optional[SentimentLabel] = None
    sentiment_rationale: Optional[str] = None
    
    article_type: Optional[str] = None
    urgency: Optional[str] = None
    
    class Config:
        from_attributes = True


class SocialPost(BaseModel):
    """Social media post with sentiment."""
    id: Optional[UUID] = None
    platform: str
    post_id: str
    posted_at: datetime
    author_handle: str
    author_followers: Optional[int] = None
    
    content: str
    url: Optional[str] = None
    
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    
    tickers: List[str] = []
    cashtags: List[str] = []
    
    sentiment_score: Optional[float] = None
    sentiment_label: Optional[SentimentLabel] = None
    
    is_influencer: bool = False
    is_verified: bool = False
    spam_score: Optional[float] = None
    
    class Config:
        from_attributes = True


class CalendarEvent(BaseModel):
    """Calendar event (earnings, macro, etc.)."""
    id: Optional[UUID] = None
    event_date: date
    event_time: Optional[str] = None
    
    event_type: str
    ticker: Optional[str] = None
    
    title: str
    description: Optional[str] = None
    
    # Earnings-specific
    eps_estimate: Optional[float] = None
    eps_actual: Optional[float] = None
    revenue_estimate: Optional[float] = None
    revenue_actual: Optional[float] = None
    surprise_pct: Optional[float] = None
    
    importance: str = "medium"
    status: str = "scheduled"
    
    class Config:
        from_attributes = True


# =============================================================================
# REPORT MODELS
# =============================================================================

class DailyReport(BaseModel):
    """Daily market report."""
    id: Optional[UUID] = None
    report_date: date
    generated_at: datetime
    
    markdown_content: str
    html_content: Optional[str] = None
    
    market_summary: Dict[str, Any]
    signals_generated: List[Dict[str, Any]]
    key_events: List[Dict[str, Any]]
    
    generation_time_ms: Optional[int] = None
    gpt_tokens_used: Optional[int] = None


# =============================================================================
# BACKTEST MODELS
# =============================================================================

class BacktestTrade(BaseModel):
    """Individual trade in backtest."""
    ticker: str
    direction: Direction
    entry_date: datetime
    exit_date: datetime
    entry_price: float
    exit_price: float
    pnl_pct: float
    pnl_dollars: float
    holding_days: int
    exit_reason: str


class BacktestResult(BaseModel):
    """Complete backtest results."""
    id: Optional[UUID] = None
    run_id: str
    run_at: datetime
    
    # Config
    strategy_id: str
    strategy_version: str
    parameters: Dict[str, Any]
    
    # Period
    start_date: date
    end_date: date
    universe: List[str]
    
    # Performance
    total_return: float
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown: float
    max_drawdown_days: int
    
    # Trade stats
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    avg_win: float
    avg_loss: float
    profit_factor: float
    expectancy: float
    
    # Risk
    var_95: float
    cvar_95: float
    volatility: float
    beta: float
    alpha: float
    
    # Details
    trades: List[BacktestTrade]
    equity_curve: List[Dict[str, Any]]
    monthly_returns: Dict[str, float]
    
    class Config:
        from_attributes = True
