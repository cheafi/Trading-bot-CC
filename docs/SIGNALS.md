# C) Signal Engine - Strategy Framework

> **⚠️ RISK DISCLAIMER**: These signals are for educational/research purposes only. Past performance does not guarantee future results. Always perform your own due diligence.

## Signal Output Schema

Every signal must conform to this structured format:

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│ Ticker | Direction | Horizon | Entry Logic | Invalidation | Targets | Catalyst |       │
│ Key Risks | Confidence (0-100) | Rationale Summary                                      │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

### JSON Schema

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["ticker", "direction", "horizon", "entry_logic", "invalidation", 
               "targets", "catalyst", "key_risks", "confidence", "rationale"],
  "properties": {
    "ticker": {"type": "string", "pattern": "^[A-Z]{1,5}$"},
    "direction": {"enum": ["LONG", "SHORT", "CLOSE"]},
    "horizon": {"enum": ["INTRADAY", "SWING_1_5D", "SWING_5_15D", "POSITION_15_60D"]},
    "entry_logic": {"type": "string", "maxLength": 200},
    "invalidation": {
      "type": "object",
      "properties": {
        "stop_price": {"type": "number"},
        "stop_type": {"enum": ["HARD", "CLOSE_BELOW", "TRAILING_ATR"]},
        "condition": {"type": "string"}
      }
    },
    "targets": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "price": {"type": "number"},
          "pct_position": {"type": "number", "minimum": 0, "maximum": 100}
        }
      },
      "minItems": 1,
      "maxItems": 3
    },
    "catalyst": {"type": "string"},
    "key_risks": {"type": "array", "items": {"type": "string"}, "maxItems": 5},
    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
    "rationale": {"type": "string", "maxLength": 500}
  }
}
```

---

## Strategy Framework Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           SIGNAL ENGINE PIPELINE                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                        REGIME DETECTION                                  │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                   │   │
│   │  │ Volatility   │  │ Trend/Mean-  │  │   Risk-On/   │                   │   │
│   │  │   Regime     │  │   Reversion  │  │   Risk-Off   │                   │   │
│   │  │ (VIX-based)  │  │    Regime    │  │    Regime    │                   │   │
│   │  └──────────────┘  └──────────────┘  └──────────────┘                   │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                      STRATEGY LAYER (Parallel)                           │   │
│   │                                                                          │   │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐             │   │
│   │  │   MOMENTUM     │  │  MEAN-REVERT   │  │   BREAKOUT     │             │   │
│   │  │   (Trend)      │  │  (Oversold)    │  │  (Volume+ATR)  │             │   │
│   │  └────────────────┘  └────────────────┘  └────────────────┘             │   │
│   │                                                                          │   │
│   │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐             │   │
│   │  │ EVENT-DRIVEN  │  │   SENTIMENT    │  │   RELATIVE     │             │   │
│   │  │ (Earnings/FDA)│  │   (News/Social)│  │   STRENGTH     │             │   │
│   │  └────────────────┘  └────────────────┘  └────────────────┘             │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                         RISK MODEL                                       │   │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐  │   │
│   │  │  Position    │  │ Correlation  │  │   Sector     │  │  Portfolio  │  │   │
│   │  │   Sizing     │  │    Check     │  │   Exposure   │  │    VaR      │  │   │
│   │  └──────────────┘  └──────────────┘  └──────────────┘  └─────────────┘  │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│   ┌─────────────────────────────────────────────────────────────────────────┐   │
│   │                    GPT VALIDATION LAYER                                  │   │
│   │  - Coherence check (signals don't contradict each other)                 │   │
│   │  - News/event conflict detection                                         │   │
│   │  - Rationale generation                                                  │   │
│   │  - Final approval or rejection                                           │   │
│   └─────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                             │
│                                    ▼                                             │
│                         FINAL SIGNAL OUTPUT                                      │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Strategy Implementations

### Strategy 1: Momentum (Trend-Following)

```python
class MomentumStrategy(BaseStrategy):
    """
    Core idea: Buy winners, sell losers. Stocks with positive momentum
    tend to continue in the same direction.
    
    Entry conditions:
    - Price > SMA(50) > SMA(200) [uptrend confirmation]
    - 21-day return in top quintile of universe
    - RSI between 50-70 (not overbought)
    - ADX > 25 (trending market)
    - Relative volume > 1.0
    
    Exit conditions:
    - Trailing stop: 2x ATR(14)
    - Price closes below SMA(50)
    - RSI > 80 (overbought)
    """
    
    STRATEGY_ID = "momentum_v1"
    HORIZON = "SWING_5_15D"
    
    def __init__(self, config: dict):
        self.lookback = config.get("lookback", 21)
        self.holding_period = config.get("holding_period", 10)
        self.quintile_threshold = config.get("quintile", 0.8)  # top 20%
        self.atr_multiplier = config.get("atr_stop", 2.0)
    
    def generate_signals(self, universe: List[str], features: pd.DataFrame) -> List[Signal]:
        signals = []
        
        # Filter for uptrend
        uptrend_mask = (
            (features['close'] > features['sma_50']) &
            (features['sma_50'] > features['sma_200']) &
            (features['adx_14'] > 25)
        )
        
        # Rank by momentum
        features['momentum_rank'] = features['return_21d'].rank(pct=True)
        
        # Filter for top quintile
        candidates = features[
            uptrend_mask &
            (features['momentum_rank'] >= self.quintile_threshold) &
            (features['rsi_14'].between(50, 70)) &
            (features['relative_volume'] > 1.0)
        ]
        
        for ticker, row in candidates.iterrows():
            stop_price = row['close'] - (self.atr_multiplier * row['atr_14'])
            target_1 = row['close'] + (1.5 * row['atr_14'])
            target_2 = row['close'] + (3.0 * row['atr_14'])
            
            signal = Signal(
                ticker=ticker,
                direction="LONG",
                horizon=self.HORIZON,
                entry_logic=f"Momentum breakout: price above rising SMAs, ADX={row['adx_14']:.1f}, "
                           f"21d return={row['return_21d']*100:.1f}% (top quintile)",
                invalidation={"stop_price": stop_price, "stop_type": "TRAILING_ATR",
                             "condition": "Close below SMA(50) or RSI > 80"},
                targets=[
                    {"price": target_1, "pct_position": 50},
                    {"price": target_2, "pct_position": 50}
                ],
                catalyst="Technical momentum + relative strength",
                key_risks=[
                    "Market regime shift to risk-off",
                    "Sector rotation away from this name",
                    "Earnings within holding period"
                ],
                confidence=self._calculate_confidence(row),
                rationale=f"Strong momentum with controlled pullback. "
                         f"Volume confirms move. Risk/reward = {((target_1-row['close'])/(row['close']-stop_price)):.1f}x"
            )
            signals.append(signal)
        
        return signals
    
    def _calculate_confidence(self, row: pd.Series) -> int:
        """Score confidence 0-100 based on signal quality"""
        score = 50  # base
        
        # Momentum strength
        if row['momentum_rank'] >= 0.9: score += 15
        elif row['momentum_rank'] >= 0.85: score += 10
        
        # Trend strength
        if row['adx_14'] >= 35: score += 10
        elif row['adx_14'] >= 30: score += 5
        
        # Volume confirmation
        if row['relative_volume'] >= 1.5: score += 10
        elif row['relative_volume'] >= 1.2: score += 5
        
        # Not near resistance
        if row['dist_from_52w_high'] > 0.05: score += 5
        
        # Sentiment alignment
        if row.get('news_sentiment_7d', 0) > 20: score += 5
        
        return min(score, 95)  # cap at 95, never 100% confident
```

### Strategy 2: Mean Reversion (Oversold Bounce)

```python
class MeanReversionStrategy(BaseStrategy):
    """
    Core idea: Stocks that deviate significantly from their mean tend to
    revert. Buy oversold stocks in uptrends, sell overbought stocks in downtrends.
    
    Entry conditions (LONG):
    - Price > SMA(200) [still in long-term uptrend]
    - RSI(14) < 30 OR price < lower Bollinger Band
    - Z-score of 21-day return < -2.0
    - No negative catalyst (earnings miss, guidance cut)
    - VIX not in panic mode (< 35)
    
    Exit conditions:
    - RSI > 50 (mean reversion complete)
    - Close above SMA(20)
    - Time stop: 5 trading days
    """
    
    STRATEGY_ID = "mean_reversion_v1"
    HORIZON = "SWING_1_5D"
    
    def __init__(self, config: dict):
        self.zscore_threshold = config.get("zscore_threshold", -2.0)
        self.rsi_threshold = config.get("rsi_threshold", 30)
        self.max_vix = config.get("max_vix", 35)
    
    def generate_signals(self, universe: List[str], features: pd.DataFrame, 
                        market_data: dict) -> List[Signal]:
        signals = []
        
        # Check market regime - skip if VIX too high
        if market_data.get('vix', 0) > self.max_vix:
            return []  # NO TRADE condition
        
        # Calculate z-score
        features['zscore_21d'] = (
            (features['return_21d'] - features['return_21d'].mean()) / 
            features['return_21d'].std()
        )
        
        # Filter for oversold in uptrend
        candidates = features[
            (features['close'] > features['sma_200']) &  # still uptrend
            (
                (features['rsi_14'] < self.rsi_threshold) |
                (features['close'] < features['bb_lower'])
            ) &
            (features['zscore_21d'] < self.zscore_threshold) &
            (features.get('negative_catalyst', False) == False)
        ]
        
        for ticker, row in candidates.iterrows():
            stop_price = row['low'] * 0.97  # 3% below recent low
            target = row['sma_20']  # target mean reversion to 20-day SMA
            
            signal = Signal(
                ticker=ticker,
                direction="LONG",
                horizon=self.HORIZON,
                entry_logic=f"Oversold bounce: RSI={row['rsi_14']:.1f}, "
                           f"Z-score={row['zscore_21d']:.2f}, below BB lower",
                invalidation={"stop_price": stop_price, "stop_type": "HARD",
                             "condition": "Break below recent swing low or time > 5 days"},
                targets=[{"price": target, "pct_position": 100}],
                catalyst="Mean reversion to SMA(20)",
                key_risks=[
                    "Continued selling pressure",
                    "Negative news/catalyst not yet public",
                    "Market-wide selloff"
                ],
                confidence=self._calculate_confidence(row, market_data),
                rationale=f"Statistically oversold with Z-score {row['zscore_21d']:.2f}. "
                         f"Long-term uptrend intact (above SMA200). "
                         f"Historical mean reversion within 3-5 days."
            )
            signals.append(signal)
        
        return signals
```

### Strategy 3: Breakout (Volume + ATR)

```python
class BreakoutStrategy(BaseStrategy):
    """
    Core idea: Breakouts from consolidation with volume confirmation
    often lead to continuation moves.
    
    Entry conditions:
    - Price breaks above 20-day high
    - Volume > 2x average (confirmation)
    - ATR expansion (volatility breakout)
    - Consolidation period >= 10 days (base building)
    - BB width was contracting (squeeze release)
    
    Exit conditions:
    - Initial stop: bottom of consolidation range
    - Trailing stop after 1 ATR profit: 1.5x ATR
    """
    
    STRATEGY_ID = "breakout_v1"
    HORIZON = "SWING_5_15D"
    
    def generate_signals(self, universe: List[str], features: pd.DataFrame) -> List[Signal]:
        signals = []
        
        # Identify breakout candidates
        candidates = features[
            (features['close'] > features['high_20d'].shift(1)) &  # new 20d high
            (features['relative_volume'] >= 2.0) &  # volume surge
            (features['atr_14'] > features['atr_14'].shift(1) * 1.1) &  # ATR expanding
            (features['consolidation_days'] >= 10) &  # base built
            (features['bb_width'] < features['bb_width'].rolling(20).mean())  # was squeezed
        ]
        
        for ticker, row in candidates.iterrows():
            consolidation_low = row['consolidation_low']
            stop_price = consolidation_low * 0.99
            target_1 = row['close'] + (row['high_20d'] - consolidation_low)  # measured move
            target_2 = row['close'] + 2 * (row['high_20d'] - consolidation_low)
            
            signal = Signal(
                ticker=ticker,
                direction="LONG",
                horizon=self.HORIZON,
                entry_logic=f"Breakout from {row['consolidation_days']}-day consolidation, "
                           f"volume {row['relative_volume']:.1f}x average",
                invalidation={"stop_price": stop_price, "stop_type": "HARD",
                             "condition": "Close back inside consolidation range"},
                targets=[
                    {"price": target_1, "pct_position": 50},
                    {"price": target_2, "pct_position": 50}
                ],
                catalyst="Technical breakout with volume confirmation",
                key_risks=[
                    "False breakout (bull trap)",
                    "Sector weakness",
                    "Broad market reversal"
                ],
                confidence=self._calculate_confidence(row),
                rationale=f"Clean breakout from {row['consolidation_days']}-day base. "
                         f"Volume confirms institutional interest. "
                         f"Measured move target: {target_1:.2f}"
            )
            signals.append(signal)
        
        return signals
```

### Strategy 4: Event-Driven (Earnings/Catalyst)

```python
class EventDrivenStrategy(BaseStrategy):
    """
    Core idea: Position for known catalysts where sentiment/technicals
    suggest favorable risk/reward.
    
    Entry conditions (Earnings):
    - Earnings within 1-5 days
    - Options IV rank > 70 (high premium available for selling)
    - OR: IV rank < 30 with positive sentiment (cheap to buy)
    - Historical earnings reaction analysis favorable
    - Whisper number vs consensus analysis
    
    NOT a prediction of direction - structured for defined risk.
    """
    
    STRATEGY_ID = "event_driven_v1"
    HORIZON = "SWING_1_5D"
    
    def generate_signals(self, universe: List[str], features: pd.DataFrame,
                        calendar: pd.DataFrame, options_data: dict) -> List[Signal]:
        signals = []
        
        # Find earnings within 5 days
        upcoming_earnings = calendar[
            (calendar['event_type'] == 'earnings') &
            (calendar['event_date'] <= (datetime.now() + timedelta(days=5)).date()) &
            (calendar['event_date'] >= datetime.now().date())
        ]
        
        for _, event in upcoming_earnings.iterrows():
            ticker = event['ticker']
            if ticker not in features.index:
                continue
            
            row = features.loc[ticker]
            iv_rank = options_data.get(ticker, {}).get('iv_rank', 50)
            
            # High IV scenario - potential for premium selling (not directional)
            if iv_rank > 70:
                signal = Signal(
                    ticker=ticker,
                    direction="NEUTRAL",  # This is a volatility play
                    horizon="SWING_1_5D",
                    entry_logic=f"Earnings in {(event['event_date'] - datetime.now().date()).days} days, "
                               f"IV rank {iv_rank}% suggests premium selling opportunity",
                    invalidation={"condition": "Defined risk via options structure"},
                    targets=[{"price": row['close'], "pct_position": 100}],  # defined risk
                    catalyst=f"Earnings on {event['event_date']}",
                    key_risks=[
                        "Earnings surprise exceeds implied move",
                        "Guidance materially different from expectations",
                        "Post-earnings gap and continuation"
                    ],
                    confidence=55,  # Lower confidence for binary events
                    rationale=f"High IV rank ({iv_rank}%) suggests elevated premiums. "
                             f"Consider iron condor or short strangle if neutral view. "
                             f"Historical implied move: typically overstated."
                )
                signals.append(signal)
        
        return signals
```

---

## Regime Detection

```python
class RegimeDetector:
    """
    Identifies market regime to filter which strategies should be active.
    """
    
    def detect(self, market_data: dict) -> MarketRegime:
        vix = market_data['vix']
        vix_term = market_data['vix_term_structure']  # VIX / VIX3M
        trend_score = market_data['trend_score']  # % stocks above SMA50
        credit_spread = market_data.get('hy_spread', 0)
        
        # Volatility regime
        if vix > 35:
            vol_regime = "CRISIS"
        elif vix > 25:
            vol_regime = "HIGH_VOL"
        elif vix > 18:
            vol_regime = "NORMAL"
        else:
            vol_regime = "LOW_VOL"
        
        # Trend regime
        if trend_score > 70:
            trend_regime = "STRONG_UPTREND"
        elif trend_score > 55:
            trend_regime = "UPTREND"
        elif trend_score > 45:
            trend_regime = "NEUTRAL"
        elif trend_score > 30:
            trend_regime = "DOWNTREND"
        else:
            trend_regime = "STRONG_DOWNTREND"
        
        # Risk regime
        if vix_term < 0.9 and credit_spread > 400:
            risk_regime = "RISK_OFF"
        elif vix_term > 1.05 and credit_spread < 350:
            risk_regime = "RISK_ON"
        else:
            risk_regime = "NEUTRAL"
        
        return MarketRegime(
            volatility=vol_regime,
            trend=trend_regime,
            risk=risk_regime,
            active_strategies=self._get_active_strategies(vol_regime, trend_regime, risk_regime)
        )
    
    def _get_active_strategies(self, vol: str, trend: str, risk: str) -> List[str]:
        """Map regime to active strategies"""
        
        # NO TRADE CONDITIONS
        if vol == "CRISIS":
            return []  # Stand aside during crisis
        
        if trend == "STRONG_DOWNTREND" and risk == "RISK_OFF":
            return []  # Stand aside in bear market
        
        active = []
        
        # Momentum works in trends
        if trend in ["UPTREND", "STRONG_UPTREND"] and vol != "HIGH_VOL":
            active.append("momentum_v1")
        
        # Mean reversion works in normal/low vol
        if vol in ["NORMAL", "LOW_VOL"] and trend != "STRONG_DOWNTREND":
            active.append("mean_reversion_v1")
        
        # Breakouts work in low vol (pre-breakout) transitioning to normal
        if vol in ["LOW_VOL", "NORMAL"]:
            active.append("breakout_v1")
        
        # Event-driven always active (but with position sizing adjustments)
        if vol != "CRISIS":
            active.append("event_driven_v1")
        
        return active
```

---

## Risk Model

```python
class RiskModel:
    """
    Position sizing, correlation management, and portfolio-level risk controls.
    """
    
    def __init__(self, config: RiskConfig):
        self.max_position_pct = config.max_position_pct  # e.g., 5%
        self.max_sector_pct = config.max_sector_pct  # e.g., 25%
        self.max_correlation = config.max_correlation  # e.g., 0.7
        self.max_portfolio_var = config.max_portfolio_var  # daily VaR limit
        self.max_drawdown_pct = config.max_drawdown_pct  # e.g., 10%
    
    def filter_and_size(self, signals: List[Signal], portfolio: Portfolio) -> List[Signal]:
        """Apply risk filters and determine position sizes"""
        
        filtered = []
        
        for signal in sorted(signals, key=lambda s: s.confidence, reverse=True):
            # Check correlation with existing positions
            if self._exceeds_correlation(signal, portfolio):
                continue
            
            # Check sector exposure
            if self._exceeds_sector_exposure(signal, portfolio):
                continue
            
            # Calculate position size
            position_size = self._calculate_position_size(signal, portfolio)
            
            # Check if adding this position exceeds VaR
            if self._exceeds_var(signal, position_size, portfolio):
                continue
            
            signal.position_size_pct = position_size
            filtered.append(signal)
        
        return filtered
    
    def _calculate_position_size(self, signal: Signal, portfolio: Portfolio) -> float:
        """
        Position sizing using:
        1. Kelly Criterion (capped)
        2. Volatility-adjusted sizing
        3. Confidence weighting
        """
        
        # Base size from risk per trade
        risk_per_trade = 0.01  # 1% of portfolio
        stop_distance = abs(signal.entry_price - signal.invalidation['stop_price'])
        stop_pct = stop_distance / signal.entry_price
        
        # Volatility-adjusted base size
        base_size = risk_per_trade / stop_pct
        
        # Confidence adjustment
        confidence_factor = signal.confidence / 100
        
        # Volatility scaling (reduce size in high vol)
        vol_factor = min(1.0, 0.20 / signal.volatility_21d) if signal.volatility_21d > 0.20 else 1.0
        
        position_size = base_size * confidence_factor * vol_factor
        
        # Cap at max position size
        return min(position_size, self.max_position_pct)
    
    def _exceeds_correlation(self, signal: Signal, portfolio: Portfolio) -> bool:
        """Check if new position is too correlated with existing"""
        for position in portfolio.positions:
            corr = self._get_correlation(signal.ticker, position.ticker)
            if corr > self.max_correlation:
                return True
        return False
```

---

## NO TRADE Conditions Checklist

The system should **NOT** generate signals when:

| Condition | Reason | Implementation |
|-----------|--------|----------------|
| VIX > 40 | Crisis mode, normal strategies fail | `RegimeDetector` |
| Market -3% intraday | Liquidation risk, don't catch knives | Pre-filter check |
| Fed day (FOMC) | Binary event, undefined risk | Calendar filter |
| Circuit breaker triggered | Market structure impaired | Data feed flag |
| Data staleness > 15 min | Stale signals are dangerous | Data freshness check |
| API errors > threshold | System integrity compromised | Health check |
| Correlation breach | Too concentrated | `RiskModel` |
| Drawdown > 10% | Reduce risk, reassess | Portfolio monitor |
| No edge signals | Forcing trades is -EV | Confidence < 50 |

```python
def should_generate_signals(self) -> Tuple[bool, str]:
    """Pre-flight check before signal generation"""
    
    checks = [
        (self.market_data['vix'] < 40, "VIX too high (crisis mode)"),
        (self.market_data['spx_change_pct'] > -3.0, "Market circuit breaker risk"),
        (not self.calendar.is_fomc_day(), "FOMC day - stand aside"),
        (self.data_freshness_seconds < 900, "Data too stale"),
        (self.api_error_rate < 0.1, "API errors too high"),
        (self.portfolio.drawdown_pct < 10.0, "Drawdown limit reached"),
    ]
    
    for condition, reason in checks:
        if not condition:
            return False, f"NO TRADE: {reason}"
    
    return True, "OK"
```

---

## GPT Validation Layer

```python
class GPTSignalValidator:
    """
    Uses GPT to validate signals for coherence and conflict detection.
    NOT for prediction - for sanity checking.
    """
    
    VALIDATION_PROMPT = """
You are a risk manager reviewing trading signals. Analyze the following signal for potential issues.

SIGNAL:
{signal_json}

MARKET CONTEXT:
{market_context}

RECENT NEWS FOR {ticker}:
{recent_news}

EXISTING POSITIONS:
{existing_positions}

Evaluate and return JSON:
{{
    "approved": true/false,
    "issues": ["list of concerns"],
    "conflicts": ["any conflicting information"],
    "adjusted_confidence": 0-100,
    "rationale": "brief explanation"
}}

Be skeptical. Flag if:
- Signal contradicts recent material news
- Signal conflicts with existing positions
- Risk/reward math doesn't check out
- Catalyst timing is wrong
- Stop placement is too tight/wide for the thesis
"""
    
    def validate(self, signal: Signal, context: dict) -> ValidatedSignal:
        prompt = self.VALIDATION_PROMPT.format(
            signal_json=signal.to_json(),
            market_context=context['market_summary'],
            ticker=signal.ticker,
            recent_news=context['news'].get(signal.ticker, "No recent news"),
            existing_positions=context['positions']
        )
        
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        result = json.loads(response.choices[0].message.content)
        
        return ValidatedSignal(
            signal=signal,
            approved=result['approved'],
            issues=result['issues'],
            adjusted_confidence=result['adjusted_confidence'],
            gpt_rationale=result['rationale']
        )
```
