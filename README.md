# TradingAI Bot - US Equities Market Intelligence System

[![Docker](https://img.shields.io/badge/Docker-Ready-blue)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://www.python.org/)
[![Azure OpenAI](https://img.shields.io/badge/Azure%20OpenAI-Supported-0078D4)](https://azure.microsoft.com/en-us/products/ai-services/openai-service)

> **⚠️ RISK DISCLAIMER**: This system is for educational and research purposes only. It does not constitute personalized financial advice. Past performance does not guarantee future results. Trading involves substantial risk of loss. Never trade with money you cannot afford to lose.

## Overview

An automated AI-powered market intelligence and signal generation system for US equities, leveraging:
- **Azure OpenAI / OpenAI GPT** for summarization, classification, and reasoning
- **Multi-source data ingestion** (prices, news, social sentiment)
- **Telegram notifications** for real-time signal alerts
- **Docker-first deployment** with PostgreSQL + TimescaleDB persistence
- **Backtesting + walk-forward validation** framework

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           TRADINGAI BOT SYSTEM                                  │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Market    │  │    News     │  │   Social    │  │  Calendar   │            │
│  │  Data API  │  │  Ingestors  │  │  Listeners  │  │   Sync      │            │
│  │ (Polygon/  │  │ (NewsAPI/   │  │  (X/Reddit  │  │ (Earnings/  │            │
│  │  IEX/Alpaca│  │  Benzinga)  │  │   APIs)     │  │  Macro)     │            │
│  └─────┬───────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘            │
│        │                 │                │                │                   │
│        └────────────────┼────────────────┼────────────────┘                   │
│                         ▼                ▼                                     │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                        DATA LAYER (PostgreSQL + Redis)                    │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐        │ │
│  │  │  Prices  │ │   News   │ │  Social  │ │ Features │ │ Signals  │        │ │
│  │  │  (OHLCV) │ │ Articles │ │  Posts   │ │  Store   │ │  Store   │        │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────────┘        │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                           │
│                                    ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                         FEATURE ENGINE                                    │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │ │
│  │  │   Technical  │ │  Sentiment   │ │   Breadth    │ │    Regime    │     │ │
│  │  │   Features   │ │   Scores     │ │   Metrics    │ │   Detector   │     │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘     │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                           │
│                                    ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                         SIGNAL ENGINE                                     │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │ │
│  │  │  Momentum    │ │  Mean-Revert │ │   Breakout   │ │  Event-Driven│     │ │
│  │  │  Strategy    │ │   Strategy   │ │   Strategy   │ │   Strategy   │     │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘     │ │
│  │                           │                                               │ │
│  │                           ▼                                               │ │
│  │  ┌────────────────────────────────────────────────────────────────────┐  │ │
│  │  │   RISK MODEL: Position Sizing | Correlation | VaR | Drawdown Limit │  │ │
│  │  └────────────────────────────────────────────────────────────────────┘  │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                           │
│                                    ▼                                           │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │                      CHATGPT REASONING LAYER                              │ │
│  │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐     │ │
│  │  │   Market     │ │   Signal     │ │   Report     │ │   Conflict   │     │ │
│  │  │   Summary    │ │   Validation │ │   Generation │ │   Resolution │     │ │
│  │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘     │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                           │
│                                    ▼                                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐            │
│  │   Daily     │  │   Signal    │  │  Execution  │  │ Monitoring  │            │
│  │   Report    │  │   Output    │  │  Interface  │  │  Dashboard  │            │
│  │  (Markdown) │  │   (JSON)    │  │   (API)     │  │  (Grafana)  │            │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘            │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your API keys

# Start all services
docker-compose up -d

# Run initial data sync
docker-compose exec scheduler python -m src.jobs.initial_sync

# View logs
docker-compose logs -f signal_engine
```

## Documentation

- [Architecture Deep Dive](docs/ARCHITECTURE.md)
- [Data Schema](docs/SCHEMA.md)
- [Signal Engine](docs/SIGNALS.md)
- [Backtesting Guide](docs/BACKTESTING.md)
- [API Reference](docs/API.md)

## License

MIT License - See [LICENSE](LICENSE) for details.
