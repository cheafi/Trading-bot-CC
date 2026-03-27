"""
TradingAI Bot - Data Models
Pydantic models for all data structures.
"""
from datetime import datetime, date, timezone
from typing import Optional, List, Dict, Any
from enum import Enum
from uuid import UUID
from pydantic import BaseModel, Field, ConfigDict


def _utcnow() -> datetime:
    """Timezone-aware UTC now (replaces deprecated datetime.utcnow)."""
    return datetime.now(timezone.utc)


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
    model_config = ConfigDict(from_attributes=True)


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
    strategy_weights: Dict[str, float] = Field(default_factory=dict)
    
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
    generated_at: datetime = Field(default_factory=_utcnow)
    
    # Core signal — supports US (AAPL), HK (0700.HK), JP (7203.T), Crypto (BTC)
    ticker: str = Field(pattern=r"^[A-Z0-9]{1,10}(\.[A-Z]{1,3})?$")
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
    
    # --- v6: Pro Desk fields ---
    setup_grade: Optional[str] = None          # A / B / C / D
    edge_type: Optional[str] = None            # trend / reversion / pattern / swing / mixed
    time_stop_days: Optional[int] = None       # max holding period before forced exit
    event_risk: Optional[str] = None           # e.g. "AAPL earnings in 2d"
    scenario_plan: Optional[Dict[str, Any]] = None  # base / bull / bear cases
    portfolio_fit: Optional[str] = None        # "good" / "overlap" / "concentrated"
    evidence: List[str] = Field(default_factory=list)  # supporting data points
    expected_value: Optional[float] = None     # EV from edge model
    approval_status: str = "conditional"       # approved / conditional / rejected
    approval_flags: Dict[str, bool] = Field(default_factory=dict)  # per-check flags
    why_now: Optional[str] = None              # catalyst + timing rationale
    
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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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
    model_config = ConfigDict(from_attributes=True)


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

# =============================================================================
# V5: INSIGHT ENGINE MODELS  (Market Playbook · Trade Brief · Edge Model)
# =============================================================================

class ExecutionPlan(BaseModel):
    """How and when to enter a trade — not just 'market buy'."""
    order_type: str = "STOP_LIMIT"  # MARKET, LIMIT, STOP, STOP_LIMIT
    entry_window: str = "first_90_min_or_after_11am"
    avoid_times: List[str] = Field(default_factory=list)
    scale_in: List[Dict[str, Any]] = Field(default_factory=list)
    # e.g. [{"pct": 50, "condition": "breakout + volume"}, {"pct": 50, "condition": "retest holds"}]


class RiskPlan(BaseModel):
    """Per-trade risk budget derived from portfolio-level risk model."""
    risk_per_trade_pct: float = 1.0
    position_size_pct: float = 0.0
    rr_to_t1: float = 0.0
    rr_to_t2: Optional[float] = None
    gap_risk_flag: bool = False
    liquidity_tier: str = "B"  # A (>$50M/day), B ($10-50M), C (<$10M)


class EdgeModel(BaseModel):
    """
    Calibrated probabilities + EV conditioned on strategy × regime × setup.
    Replaces vague 'confidence' with historically-backed numbers.
    """
    p_stop: float = Field(ge=0, le=1, default=0.5)
    p_t1: float = Field(ge=0, le=1, default=0.5)
    p_t2: float = Field(ge=0, le=1, default=0.3)
    expected_return_pct: float = 0.0
    expected_mae_pct: float = 0.0
    expected_holding_days: float = 7.0
    calibration_bucket: str = ""
    sample_size: int = 0

    @property
    def ev_positive(self) -> bool:
        return self.expected_return_pct > 0


class SetupBlock(BaseModel):
    """Structured setup metadata per signal."""
    setup_tags: List[str] = Field(default_factory=list)
    trigger: str = ""
    time_stop_days: Optional[int] = None


class EvidenceBlock(BaseModel):
    """Data sources that informed this signal."""
    market_regime: Dict[str, str] = Field(default_factory=dict)
    features: Dict[str, float] = Field(default_factory=dict)
    sources_used: Dict[str, List[str]] = Field(default_factory=dict)


class KeyLevel(BaseModel):
    """A technically significant price level."""
    label: str
    price: float
    significance: str = ""  # e.g. "20D breakout", "SPX 200-day SMA"


class ChangeItem(BaseModel):
    """A single 'what changed?' item for daily brief."""
    category: str  # "regime", "breadth", "volatility", "leadership", "macro"
    description: str
    severity: str = "info"  # "info", "warning", "critical"


class MarketPlaybook(BaseModel):
    """
    Daily decision document: regime → recommended strategies → risk stance.
    One per trading session.
    """
    playbook_date: date
    session: str = "US_RTH"

    # Regime snapshot
    regime_label: str = ""
    volatility_regime: str = ""
    trend_regime: str = ""
    risk_regime: str = ""
    risk_on_score: float = 0.0

    # Playbook
    playbook_text: str = ""
    recommended_strategies: List[str] = Field(default_factory=list)
    sizing_stance: str = "normal"  # "full", "normal", "half", "cash_up"

    # Key levels
    key_levels: List[KeyLevel] = Field(default_factory=list)

    # What changed since yesterday
    change_summary: List[ChangeItem] = Field(default_factory=list)

    # Risk bulletin
    risk_bulletin: List[str] = Field(default_factory=list)


class TradeBrief(BaseModel):
    """
    Institutional trade brief — one per signal.
    Answers: why now, how to enter, what kills it, historical edge.
    """
    ticker: str
    direction: Direction
    horizon: Horizon

    entry_logic: str
    invalidation_sentence: str
    catalyst: str
    key_risks: List[str] = Field(default_factory=list, max_length=5)
    confidence: int = Field(ge=0, le=100)
    rationale: str

    setup: SetupBlock = Field(default_factory=SetupBlock)
    execution_plan: ExecutionPlan = Field(default_factory=ExecutionPlan)
    risk_plan: RiskPlan = Field(default_factory=RiskPlan)
    edge_model: EdgeModel = Field(default_factory=EdgeModel)
    evidence: EvidenceBlock = Field(default_factory=EvidenceBlock)

    what_changes_mind: str = ""  # "If VIX > 30 and breadth < 30%, downgrade"


class RiskBulletin(BaseModel):
    """Portfolio-level + market-structure warning bulletin."""
    generated_at: datetime = Field(default_factory=_utcnow)
    warnings: List[str] = Field(default_factory=list)
    earnings_cluster_risk: bool = False
    correlation_spike_risk: bool = False
    event_windows: List[str] = Field(default_factory=list)
    max_open_risk_pct: float = 0.0
    recommendation: str = ""


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
    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# V6: PRO DESK MODELS  (Scenario · Flows · Delta · Scoreboard · Diagnostics · DQ)
# =============================================================================

class ScenarioPlan(BaseModel):
    """Base / bull / bear scenario map attached to a regime scoreboard."""
    base_case: Dict[str, Any] = Field(default_factory=dict)
    bull_case: Dict[str, Any] = Field(default_factory=dict)
    bear_case: Dict[str, Any] = Field(default_factory=dict)
    triggers: List[str] = Field(default_factory=list)


class FlowsPositioning(BaseModel):
    """Options flow and market positioning snapshot."""
    put_call_ratio: Optional[float] = None
    put_call_trend: Optional[str] = None           # "rising" / "falling" / "flat"
    iv_rank_spy: Optional[float] = None             # 0-100
    iv_vs_rv: Optional[str] = None                  # "premium" / "discount" / "fair"
    gamma_zone: Optional[str] = None                # "positive" / "negative" / "neutral"
    etf_flow_signals: List[str] = Field(default_factory=list)
    crowding_flags: List[str] = Field(default_factory=list)


class DeltaSnapshot(BaseModel):
    """What changed since yesterday / last week — the 'delta deck'."""
    snapshot_date: date
    session: str = "US_RTH"

    # Index moves
    spx_1d_pct: Optional[float] = None
    spx_5d_pct: Optional[float] = None
    ndx_1d_pct: Optional[float] = None
    ndx_5d_pct: Optional[float] = None
    iwm_1d_pct: Optional[float] = None
    iwm_5d_pct: Optional[float] = None

    # Volatility
    vix_close: Optional[float] = None
    vix_1d_change: Optional[float] = None
    vix_5d_change: Optional[float] = None

    # Rates
    yield_10y: Optional[float] = None
    yield_10y_1d_bp: Optional[float] = None
    yield_10y_5d_bp: Optional[float] = None

    # Breadth
    pct_above_50dma: Optional[float] = None
    pct_above_50dma_1d_change: Optional[float] = None
    new_highs: Optional[int] = None
    new_lows: Optional[int] = None

    # Sector leadership
    top_3_sectors: List[str] = Field(default_factory=list)
    bottom_3_sectors: List[str] = Field(default_factory=list)

    # Sentiment
    news_sentiment_change: Optional[float] = None
    social_sentiment_change: Optional[float] = None

    # Options
    put_call_ratio: Optional[float] = None
    iv_rank_spy: Optional[float] = None


class RegimeScoreboard(BaseModel):
    """Regime summary → strategy playbook → risk budget."""
    regime_label: str = "NEUTRAL"
    risk_on_score: float = 0.0
    trend_state: str = "NEUTRAL"
    vol_state: str = "NORMAL"

    # Risk budget
    max_gross_pct: float = 100.0
    net_long_target_low: float = 0.0
    net_long_target_high: float = 100.0
    max_single_name_pct: float = 5.0
    max_sector_pct: float = 25.0

    # Strategy playbook
    strategies_on: List[str] = Field(default_factory=list)
    strategies_conditional: List[Dict[str, str]] = Field(default_factory=list)
    strategies_off: List[str] = Field(default_factory=list)

    # Context
    no_trade_triggers: List[str] = Field(default_factory=list)
    top_drivers: List[str] = Field(default_factory=list)
    scenarios: Optional[ScenarioPlan] = None


class BacktestDiagnostic(BaseModel):
    """Sliced backtest metrics for edge model calibration."""
    slice_type: str          # "regime", "volatility", "sector", "setup_grade"
    slice_label: str         # e.g. "RISK_ON", "HIGH_VOL", "Technology", "A"
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: float = 0.0
    avg_pnl_pct: float = 0.0
    avg_rr_realized: float = 0.0
    sharpe: float = 0.0
    avg_mae_pct: float = 0.0
    avg_mfe_pct: float = 0.0
    avg_holding_days: float = 0.0
    stop_exits: int = 0
    time_stop_exits: int = 0
    target_exits: int = 0
    trail_stop_exits: int = 0


class DataQualityReport(BaseModel):
    """Result of a single data-quality check."""
    check_time: datetime = Field(default_factory=_utcnow)
    feed_name: str                             # "ohlcv", "features", "news", etc.
    check_type: str                            # "freshness", "missing_bars", "outlier", etc.
    passed: bool = True
    severity: str = "info"                     # "info" / "warning" / "critical"
    details: Optional[Dict[str, Any]] = None   # free-form context
    affected_tickers: List[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# TRADE RECOMMENDATION LAYER (Sprint 3)
# ═══════════════════════════════════════════════════════════════════

class InstrumentType(str, Enum):
    """What vehicle to use for the trade."""
    STOCK = "stock"
    CALL = "call"
    PUT = "put"
    VERTICAL_SPREAD = "vertical_spread"
    DEBIT_SPREAD = "debit_spread"
    CREDIT_SPREAD = "credit_spread"
    NO_TRADE = "no_trade"


class SetupGrade(str, Enum):
    """Quality grade for a setup."""
    A = "A"
    B = "B"
    C = "C"
    REJECT = "Reject"


class MistakeType(str, Enum):
    """Categories for post-trade learning."""
    CHASED_ENTRY = "chased_entry"
    IGNORED_REGIME = "ignored_regime"
    OVERSIZED = "oversized"
    HELD_THROUGH_EVENT = "held_through_event"
    WRONG_EXPRESSION = "wrong_expression"
    PREMATURE_EXIT = "premature_exit"
    NO_EDGE = "no_edge"
    CORRECT_PROCESS = "correct_process"


class LearningTag(str, Enum):
    """Tags for outcome attribution."""
    REGIME_CORRECT = "regime_correct"
    REGIME_WRONG = "regime_wrong"
    EXPRESSION_OPTIMAL = "expression_optimal"
    EXPRESSION_SUBOPTIMAL = "expression_suboptimal"
    SIZING_CORRECT = "sizing_correct"
    SIZING_WRONG = "sizing_wrong"
    TIMING_GOOD = "timing_good"
    TIMING_BAD = "timing_bad"


class OptionLeg(BaseModel):
    """Single leg of an options trade."""
    action: str = "buy"          # "buy" or "sell"
    right: str = "call"          # "call" or "put"
    strike: float = 0.0
    expiry: str = ""             # ISO date string
    quantity: int = 1
    premium: Optional[float] = None
    iv: Optional[float] = None
    delta: Optional[float] = None


class ExpressionPlan(BaseModel):
    """How to express the trade thesis (stock, option, spread)."""
    instrument_type: str = "stock"       # InstrumentType value
    legs: List[OptionLeg] = Field(default_factory=list)
    expiry_logic: str = ""               # e.g. "30-45 DTE for swing"
    strike_logic: str = ""               # e.g. "ATM call, 70-delta"
    iv_rank: Optional[float] = None      # 0-100
    iv_percentile: Optional[float] = None
    theta_note: Optional[str] = None
    liquidity_note: Optional[str] = None
    max_risk_dollars: Optional[float] = None
    spread_width: Optional[float] = None
    open_interest_min: Optional[int] = None
    why_this_expression: str = ""


class TradeRecommendation(BaseModel):
    """
    Canonical decision artifact: signal → ensemble → execution.

    Replaces ad-hoc dicts that previously flowed through the pipeline:
    - signal_dicts built in AutoTradingEngine._run_cycle
    - opportunity dicts returned by OpportunityEnsembler.rank_opportunities
    - opp parameter consumed by _execute_signal
    - _cached_recommendations entries served to the API

    Lifecycle:
      1. Created from a Signal via ``from_signal()``
      2. Scored by OpportunityEnsembler (sets composite_score, etc.)
      3. Consumed by AutoTradingEngine._execute_signal
      4. Serialised for API via ``to_api_dict()``

    Supports dict-like access (``rec["composite_score"]``,
    ``rec.get("key", default)``) for backward compatibility with
    code that previously used plain dicts.
    """

    # ── Identity ──────────────────────────────────────────────
    ticker: str
    direction: str = "LONG"               # Direction enum .value
    strategy_id: str = "unknown"
    recommendation_id: str = ""
    timestamp: datetime = Field(default_factory=_utcnow)

    # ── Signal origin ─────────────────────────────────────────
    signal_confidence: int = 50            # 0-100 raw from Signal
    score: float = 0.5                     # 0-1 normalised (confidence / 100)
    entry_price: float = 0.0
    stop_price: float = 0.0
    risk_reward_ratio: float = 1.5
    expected_return: float = 0.02
    horizon: str = "SWING_1_5D"
    entry_logic: str = ""
    catalyst: str = ""

    # ── Edge Calculator ───────────────────────────────────────
    edge_p_t1: float = 0.0                # calibrated win probability
    edge_p_stop: float = 0.0              # calibrated stop probability
    edge_ev: float = 0.0                  # expected value %

    # ── Ensemble scoring (set by OpportunityEnsembler) ────────
    composite_score: float = 0.0
    trade_decision: bool = False
    suppression_reason: str = ""
    components: Dict[str, float] = Field(default_factory=dict)
    penalties: Dict[str, float] = Field(default_factory=dict)

    # ── Regime context ────────────────────────────────────────
    regime_label: str = ""
    regime_fit: float = 0.0
    regime_weight: float = 1.0

    # ── Strategy health ───────────────────────────────────────
    strategy_health: float = 0.5
    sizing_multiplier: float = 1.0

    # ── Entry snapshot (for ML learning loop) ─────────────────
    vix_at_entry: float = 20.0
    rsi_at_entry: float = 50.0
    adx_at_entry: float = 25.0
    relative_volume: float = 1.0
    distance_from_sma50: float = 0.0

    # ── Quality ───────────────────────────────────────────────
    setup_grade: str = "C"
    ml_grade: str = ""
    ml_win_probability: float = 0.0

    # ── Ensemble component inputs ─────────────────────────────
    timing_score: float = 0.5
    strategy_agreement: float = 0.5
    days_to_earnings: int = 999
    sector: str = ""

    # ── Expression (Sprint 3 — options-aware) ─────────────────
    instrument_type: str = "stock"
    expression: ExpressionPlan = Field(default_factory=ExpressionPlan)

    # ── Sizing (set during execution) ─────────────────────────
    position_size_shares: int = 0
    kelly_fraction: float = 0.0

    # ── Execution state ───────────────────────────────────────
    executed: bool = False
    execution_time: Optional[datetime] = None
    fill_price: float = 0.0

    # ── Source tracking ───────────────────────────────────────
    source_signal_id: Optional[str] = None
    source_strategies: List[str] = Field(default_factory=list)

    # ── Explanations ──────────────────────────────────────────
    key_risks: List[str] = Field(default_factory=list)
    execution_notes: List[str] = Field(default_factory=list)

    # ── Metadata (catch-all for extensions) ───────────────────
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)

    # ── Dict-like protocol (backward compat) ──────────────────

    def __getitem__(self, key: str):
        try:
            return getattr(self, key)
        except AttributeError:
            if key in self.metadata:
                return self.metadata[key]
            raise KeyError(key)

    def __setitem__(self, key: str, value):
        if key in self.model_fields:
            setattr(self, key, value)
        else:
            self.metadata[key] = value

    def __contains__(self, key: str) -> bool:
        return key in self.model_fields or key in self.metadata

    def get(self, key: str, default=None):
        """Dict-compatible .get() for backward compat."""
        if key in self.model_fields:
            return getattr(self, key)
        return self.metadata.get(key, default)

    # ── Serialisation helpers ─────────────────────────────────

    def to_api_dict(self) -> Dict[str, Any]:
        """JSON-safe dict for API / Discord serialisation."""
        d = self.model_dump(exclude={"expression"})
        d["instrument_type"] = self.instrument_type
        for ts_key in ("timestamp", "execution_time"):
            if d.get(ts_key) and hasattr(d[ts_key], "isoformat"):
                d[ts_key] = d[ts_key].isoformat()
        return d

    def to_entry_snapshot(self) -> Dict[str, Any]:
        """Extract ML entry snapshot for learning loop / DB.

        Sprint 29: now includes composite_score, ml_grade,
        regime_label so the learning loop has full decision
        context for each trade.
        """
        return {
            "confidence": self.signal_confidence,
            "vix_at_entry": self.vix_at_entry,
            "rsi_at_entry": self.rsi_at_entry,
            "adx_at_entry": self.adx_at_entry,
            "relative_volume": self.relative_volume,
            "distance_from_sma50": self.distance_from_sma50,
            "composite_score": self.composite_score,
            "ml_grade": self.ml_grade,
            "regime_label": self.regime_label,
        }

    # ── Factory methods ───────────────────────────────────────

    @classmethod
    def from_signal(
        cls,
        signal,
        edge=None,
        regime_state: Optional[Dict[str, Any]] = None,
        **overrides,
    ) -> "TradeRecommendation":
        """Build from a Signal object + optional EdgeModel + regime."""
        regime_state = regime_state or {}
        direction_val = (
            signal.direction.value
            if hasattr(signal.direction, "value")
            else str(signal.direction)
        )
        _strat = (
            getattr(signal, "strategy_id", None)
            or getattr(signal, "strategy_name", None)
            or "unknown"
        )
        _conf = getattr(signal, "confidence", 50) or 50
        _stop = 0.0
        inv = getattr(signal, "invalidation", None)
        if inv and getattr(inv, "stop_price", 0):
            _stop = inv.stop_price

        fields: Dict[str, Any] = dict(
            ticker=signal.ticker,
            direction=direction_val,
            strategy_id=_strat,
            signal_confidence=_conf,
            score=_conf / 100.0,
            entry_price=getattr(signal, "entry_price", 0) or 0,
            stop_price=_stop,
            risk_reward_ratio=getattr(signal, "risk_reward_ratio", 1.5) or 1.5,
            expected_return=getattr(signal, "expected_return", 0.02) or 0.02,
            horizon=(
                signal.horizon.value
                if hasattr(signal, "horizon") and hasattr(signal.horizon, "value")
                else str(getattr(signal, "horizon", "SWING_1_5D"))
            ),
            entry_logic=getattr(signal, "entry_logic", ""),
            catalyst=getattr(signal, "catalyst", ""),
            setup_grade=getattr(signal, "setup_grade", "C") or "C",
            source_signal_id=str(getattr(signal, "id", "")) or None,
            key_risks=list(getattr(signal, "key_risks", [])),
            # Entry snapshot for ML
            rsi_at_entry=getattr(signal, "rsi", 50),
            adx_at_entry=getattr(signal, "adx", 25),
            relative_volume=getattr(signal, "relative_volume", 1.0),
            distance_from_sma50=getattr(signal, "distance_from_sma50", 0),
            vix_at_entry=regime_state.get("vix", 20),
            regime_label=regime_state.get("regime", ""),
        )

        # Edge calculator data
        if edge is not None:
            fields["edge_p_t1"] = getattr(edge, "p_t1", 0)
            fields["edge_p_stop"] = getattr(edge, "p_stop", 0)
            fields["edge_ev"] = getattr(edge, "expected_return_pct", 0)

        fields.update(overrides)
        return cls(**fields)

    @classmethod
    def from_dict(
        cls, d: Dict[str, Any],
    ) -> "TradeRecommendation":
        """Build from a legacy signal dict (backward compat).

        Maps old field names (``strategy_name``, ``score``, etc.)
        to the canonical TradeRecommendation field names.
        """
        _score = d.get("score", 0.5)
        _conf = d.get("confidence", int(_score * 100))
        _rr = d.get("risk_reward_ratio", d.get("risk_reward", 1.5))

        rec = cls(
            ticker=d.get("ticker", "???"),
            direction=d.get("direction", "LONG"),
            strategy_id=d.get("strategy_name", d.get("strategy_id", "unknown")),
            signal_confidence=_conf,
            score=_score,
            entry_price=d.get("entry_price", 0),
            risk_reward_ratio=_rr if _rr else 1.5,
            expected_return=d.get("expected_return", 0.02),
            edge_p_t1=d.get("edge_p_t1", 0),
            edge_p_stop=d.get("edge_p_stop", 0),
            edge_ev=d.get("edge_ev", 0),
            timing_score=d.get("timing_score", 0.5),
            strategy_agreement=d.get("strategy_agreement", 0.5),
            days_to_earnings=d.get("days_to_earnings", 999),
            sector=d.get("sector", ""),
        )

        # Stash original dict in metadata (preserves _signal_obj etc.)
        rec.metadata["_original_dict"] = d
        return rec


class RegimeState(BaseModel):
    """Probabilistic regime assessment."""
    risk_on_uptrend: float = 0.0
    neutral_range: float = 0.0
    risk_off_downtrend: float = 0.0
    entropy: float = 1.0
    should_trade: bool = True
    confidence: float = 0.0
    vix: float = 0.0
    vix_term_slope: float = 0.0
    breadth_pct: float = 0.5
    credit_spread_z: float = 0.0
    realized_vol_20d: float = 0.0
    timestamp: datetime = Field(default_factory=_utcnow)


class StrategyScore(BaseModel):
    """Leaderboard entry for a strategy."""
    strategy_id: str
    regime_bucket: str = ""
    horizon: str = ""
    asset_class: str = "equity"
    oos_sharpe: float = 0.0
    oos_sortino: float = 0.0
    walk_forward_stability: float = 0.0
    live_expectancy: float = 0.0
    live_trades: int = 0
    live_drawdown: float = 0.0
    recent_degradation: float = 0.0
    liquidity_score: float = 1.0
    options_suitability: float = 0.0
    correlation_penalty: float = 0.0
    composite_score: float = 0.0
    status: str = "active"           # active / reduced / cooldown / retired
    cooldown_until: Optional[datetime] = None
    last_updated: datetime = Field(default_factory=_utcnow)
