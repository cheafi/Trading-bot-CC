# Market Intel API — External Contract

> Stable, read-only endpoints for market macro data.
> No authentication required (respects global rate limit).

## Base Path

```
/api/market-intel
```

---

## `GET /api/market-intel/regime`

Current market regime classification.

**Response**

```json
{
  "regime_label": "RISK-ON",
  "risk": "LOW",
  "trend": "BULLISH",
  "volatility": "NORMAL",
  "strategy_playbook": { ... },
  "as_of": "2025-01-15T12:00:00Z"
}
```

| Field               | Type   | Description                                     |
| ------------------- | ------ | ----------------------------------------------- |
| `regime_label`      | string | Composite label (RISK-ON / RISK-OFF / NEUTRAL)  |
| `risk`              | string | Risk level (LOW / MODERATE / HIGH / EXTREME)    |
| `trend`             | string | Trend direction (BULLISH / BEARISH / NEUTRAL)   |
| `volatility`        | string | Vol regime (LOW / NORMAL / HIGH / EXTREME)      |
| `strategy_playbook` | object | Recommended strategy weights for current regime |

---

## `GET /api/market-intel/vix`

Current CBOE VIX level with human-readable classification.

**Response**

```json
{
  "vix": 18.45,
  "label": "NORMAL",
  "as_of": "2025-01-15T12:00:00Z"
}
```

| VIX Range | Label    |
| --------- | -------- |
| < 15      | LOW      |
| 15–20     | NORMAL   |
| 20–30     | ELEVATED |
| 30–40     | HIGH     |
| > 40      | EXTREME  |

---

## `GET /api/market-intel/breadth`

Market breadth indicators (advance/decline, new highs/lows).

**Response**

```json
{
  "breadth": {
    "advancers": 320,
    "decliners": 180,
    "ad_ratio": 1.78,
    "new_highs": 42,
    "new_lows": 8
  },
  "as_of": "2025-01-15T12:00:00Z"
}
```

---

## `GET /api/market-intel/spy-return`

SPY returns across multiple periods.

**Response**

```json
{
  "spy_returns": {
    "1w_pct": 1.23,
    "1m_pct": 3.45,
    "3m_pct": 7.89,
    "ytd_pct": 12.34
  },
  "as_of": "2025-01-15T12:00:00Z"
}
```

---

## `GET /api/market-intel/rates`

US Treasury yield curve snapshot.

**Response**

```json
{
  "yields": {
    "3M": 5.25,
    "5Y": 4.1,
    "10Y": 4.45,
    "30Y": 4.65
  },
  "spread_10y_3m": -0.8,
  "curve_status": "INVERTED",
  "as_of": "2025-01-15T12:00:00Z"
}
```

| Curve Status | Condition        |
| ------------ | ---------------- |
| INVERTED     | 10Y − 3M < 0     |
| FLAT         | 0 ≤ spread < 0.5 |
| NORMAL       | spread ≥ 0.5     |

---

## Rate Limits

All market-intel endpoints share the global rate limiter:
**120 requests / minute** per API key or IP.

Headers returned:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`

---

## Error Responses

```json
{
  "error": "Rate limit exceeded",
  "detail": "Too many requests. Please try again later.",
  "retry_after": 60
}
```

Status codes: `200` (success), `429` (rate limited), `500` (internal error).
