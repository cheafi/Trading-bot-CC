# A) System Architecture - Deep Dive

## Service Breakdown

### 1. Data Ingestion Layer

| Service | Purpose | Schedule | Data Source |
|---------|---------|----------|-------------|
| `market_data_ingestor` | OHLCV, quotes, volume | Real-time + EOD | Polygon.io / Alpaca / IEX Cloud |
| `news_ingestor` | News articles, press releases | Every 5 min | NewsAPI / Benzinga / Finnhub |
| `social_ingestor` | Social posts, sentiment | Every 15 min | X API v2 / Reddit API (ToS-compliant) |
| `calendar_sync` | Earnings, dividends, macro events | Daily 6AM ET | Earnings Whispers / Fed Calendar |
| `fundamentals_sync` | Financials, ratios | Weekly | SEC EDGAR / Financial Modeling Prep |

### 2. Data Storage Layer

```
┌─────────────────────────────────────────────────────────────┐
│                    PostgreSQL (Primary)                      │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐            │
│  │  time_series│ │  documents  │ │  analytics  │            │
│  │   schema    │ │   schema    │ │   schema    │            │
│  └─────────────┘ └─────────────┘ └─────────────┘            │
└─────────────────────────────────────────────────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────┐    ┌─────────────────────────────┐
│   Redis (Cache + Queue) │    │   TimescaleDB Extension     │
│   - Feature cache       │    │   - Hypertables for OHLCV   │
│   - Job queue           │    │   - Continuous aggregates   │
│   - Rate limiting       │    │   - Compression policies    │
└─────────────────────────┘    └─────────────────────────────┘
```

### 3. Feature Engine

**Technical Features (per ticker):**
- Price momentum: 5d, 10d, 21d, 63d returns
- Volatility: ATR, Bollinger width, IV rank
- Volume: Relative volume, OBV, volume profile
- Trend: SMA crossovers, ADX, Ichimoku signals
- Mean reversion: RSI, distance from VWAP, z-score

**Market Breadth Features:**
- Advance/Decline ratio
- New highs vs new lows
- % stocks above 50/200 DMA
- McClellan Oscillator
- Sector rotation metrics

**Sentiment Features:**
- News sentiment score (0-100)
- Social mention velocity
- Sentiment divergence (price vs sentiment)
- Unusual options activity flag

**Regime Detection:**
- VIX level + term structure
- Credit spreads (HY-IG)
- Correlation regime
- Trend vs mean-reversion regime classifier

### 4. Signal Engine

```python
# Signal Generation Pipeline
class SignalPipeline:
    def __init__(self):
        self.strategies = [
            MomentumStrategy(lookback=21, holding=5),
            MeanReversionStrategy(zscore_threshold=2.0),
            BreakoutStrategy(atr_multiple=1.5),
            EventDrivenStrategy(catalyst_types=['earnings', 'fda'])
        ]
        self.regime_detector = RegimeDetector()
        self.risk_model = RiskModel()
        self.gpt_validator = GPTSignalValidator()
    
    def generate_signals(self, universe: List[str], date: datetime) -> List[Signal]:
        regime = self.regime_detector.detect(date)
        active_strategies = self.filter_strategies_by_regime(regime)
        
        raw_signals = []
        for strategy in active_strategies:
            signals = strategy.generate(universe, date)
            raw_signals.extend(signals)
        
        # Risk-adjusted and deduplicated
        filtered_signals = self.risk_model.filter_and_size(raw_signals)
        
        # GPT validation for coherence
        validated_signals = self.gpt_validator.validate(filtered_signals)
        
        return validated_signals
```

### 5. ChatGPT Integration Layer

**Use Cases (NOT as sole source of truth):**

| Function | Input | Output | Model |
|----------|-------|--------|-------|
| News Summarization | Raw articles | Structured summary | GPT-5.2-mini |
| Sentiment Classification | Text snippet | Score + rationale | GPT-5.2-mini |
| Signal Validation | Signal + context | Approval/flag + reasoning | GPT-5.2 |
| Report Generation | Structured data | Markdown report | GPT-5.2 |
| Conflict Resolution | Opposing signals | Recommendation | GPT-5.2 |

**Prompt Engineering Principles:**
1. Always ground prompts with retrieved factual data
2. Explicit output schema (JSON mode)
3. Include uncertainty quantification
4. Chain-of-thought for complex reasoning
5. Never ask GPT to predict prices directly

### 6. Output Layer

| Output | Format | Delivery | Frequency |
|--------|--------|----------|-----------|
| Daily Market Brief | Markdown + PDF | Email / Slack / S3 | 6:30 AM ET |
| Trade Signals | JSON + Webhook | API / Broker integration | Real-time |
| Position Monitor | Dashboard | Grafana | Continuous |
| Weekly Digest | HTML Report | Email | Sunday 6 PM ET |

### 7. Monitoring & Observability

```
┌─────────────────────────────────────────────────────────────┐
│                    Monitoring Stack                          │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Prometheus  │  │   Grafana    │  │   Alerting   │       │
│  │   Metrics    │  │  Dashboards  │  │  (PagerDuty) │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                 │                 │                │
│         └────────────────┴────────────────┘                │
│                          │                                   │
│  ┌──────────────────────┴───────────────────────────────┐  │
│  │                   Tracked Metrics                      │  │
│  │  - Data freshness (staleness alerts)                  │  │
│  │  - Signal generation latency                          │  │
│  │  - API error rates                                    │  │
│  │  - Model prediction drift                             │  │
│  │  - P&L tracking (paper/live)                          │  │
│  │  - Hit rate rolling window                            │  │
│  └────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Service Communication

```yaml
# Inter-service communication patterns
communication:
  synchronous:
    - REST APIs between services
    - gRPC for high-frequency internal calls
  
  asynchronous:
    - Redis Pub/Sub for real-time events
    - PostgreSQL LISTEN/NOTIFY for data changes
    - Celery for background job queue
  
  data_flow:
    - Ingestors → PostgreSQL → Feature Engine
    - Feature Engine → Redis Cache → Signal Engine
    - Signal Engine → GPT API → Output Layer
```

## Scalability Considerations

1. **Horizontal Scaling**: Ingestors and feature calculators are stateless
2. **Data Partitioning**: TimescaleDB hypertables auto-partition by time
3. **Caching Strategy**: Redis for hot data, PostgreSQL for cold storage
4. **Rate Limiting**: Distributed rate limiting via Redis for API calls
5. **Backpressure**: Queue-based ingestion prevents overload

## Security Model

```
┌─────────────────────────────────────────────────────────────┐
│                    Security Layers                           │
│                                                              │
│  1. Network: Docker network isolation, no public ports      │
│  2. Secrets: Docker secrets / HashiCorp Vault               │
│  3. API Keys: Rotation policy, usage monitoring             │
│  4. Data: Encryption at rest (PostgreSQL), TLS in transit   │
│  5. Access: RBAC for dashboard, API key authentication      │
└─────────────────────────────────────────────────────────────┘
```
