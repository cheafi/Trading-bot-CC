# CC — Capability SKILL Sheet

> What this platform **can** and **cannot** do.

## Core Capabilities

| Domain                 | Capability                                            | Status                    |
| ---------------------- | ----------------------------------------------------- | ------------------------- |
| **Regime**             | Market regime classification (risk/trend/vol)         | ✅ Live                   |
| **Signals**            | Multi-factor trade signals with lifecycle tracking    | ✅ Live                   |
| **Recommendations**    | Engine-backed recommendations with trust metadata     | ✅ Live                   |
| **Performance Lab**    | Equity curve, drawdown, Sharpe — auditable            | ✅ Live                   |
| **Portfolio Brief**    | Catalyst-enriched portfolio summary                   | ✅ Live                   |
| **Compare Overlay**    | Multi-instrument date-aligned comparison              | ✅ Live                   |
| **Strategy Lab**       | Multi-strategy sleeve optimizer (max-Sharpe / min-DD) | ✅ Live                   |
| **Options Screen**     | Chain mapping + ExpressionEngine decision             | ✅ Live (synthetic chain) |
| **Macro Intel**        | Rates, political risk, war basket, correlations       | ✅ Live                   |
| **Market Intel API**   | Read-only regime, VIX, breadth, rates, SPY return     | ✅ Live                   |
| **Research Artifacts** | Immutable JSON/CSV/MD bundles with replay             | ✅ Live                   |
| **Discord Bot**        | Full Discord interface for all surfaces               | ✅ Live                   |

## Data Sources

| Source                   | Use                              | Integration                |
| ------------------------ | -------------------------------- | -------------------------- |
| MarketDataService        | All price / volume / history     | Singleton, TTL cache       |
| AutoTradingEngine        | Signals, recommendations, regime | Singleton, lazy init       |
| ExpressionEngine         | Options vs stock decision        | Per-request                |
| SyntheticOptionsProvider | Options chain (demo)             | Fallback only              |
| yfinance (upstream)      | Underlying market data           | Via MarketDataService only |

## What We Do NOT Do

- ❌ **Execute live trades** in production by default (`dry_run=True`)
- ❌ **Provide financial advice** — all outputs are research / informational
- ❌ **Guarantee data accuracy** — synthetic data is clearly labelled
- ❌ **Provide real-time options chains** — currently synthetic; real provider pluggable
- ❌ **Back-test with tick data** — daily resolution only

## Architecture Constraints

- All endpoints use the **singleton engine** — no ad-hoc instantiation
- All market data flows through **MarketDataService** — no direct yfinance
- All research surfaces produce **immutable artifacts** with replay IDs
- Every response includes a **trust block** (`mode`, `source`, `data_warning`)
- The ExpressionEngine gates options features behind `OPTIONS_ENABLED` config

## External API Contract

The `/api/market-intel/*` endpoints provide a stable, read-only contract
suitable for external consumers (dashboards, bots, partner integrations).

See [API_MARKET_INTEL.md](./API_MARKET_INTEL.md) for the full specification.
