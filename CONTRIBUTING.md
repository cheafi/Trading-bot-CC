# Contributing to CC

Thank you for your interest in contributing! This guide will help you get
started quickly and understand how the project is organized.

---

## Quick Start for Contributors

```bash
# 1. Fork and clone
git clone https://github.com/<your-username>/TradingAI_Bot.git
cd TradingAI_Bot

# 2. Set up environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -e ".[dev]"

# 3. Copy environment template
cp .env.example .env
# Fill in at minimum: DISCORD_BOT_TOKEN

# 4. Run tests
pytest tests/ -v

# 5. Run linters
black --check .
ruff check .
```

---

## Project Structure

```
src/
├── algo/          # Trading strategies (VCP, momentum, mean reversion, etc.)
├── api/           # FastAPI REST endpoints
├── backtest/      # Backtesting engine
├── brokers/       # Broker integrations (Paper, Alpaca, Futu, IBKR, MT5)
├── core/          # Shared models, config, utilities
├── engines/       # AutoTradingEngine, signal engine, strategy optimizer
├── ingestors/     # Market data and news ingestion
├── ml/            # ML models (regime classification, quality gate)
├── notifications/ # Discord bot (primary), formatters, embeds, tasks
├── performance/   # Performance tracking and attribution
├── research/      # Research artifact generation
├── scanners/      # Market scanners and screeners
├── scheduler/     # Background task scheduling
├── services/      # Shared services (market data, context assembly)
└── strategies/    # Strategy configuration and registry
```

---

## Development Workflow

### Branching

- `main` — stable release branch
- `develop` — integration branch for upcoming release
- Feature branches: `feat/your-feature`
- Bug fixes: `fix/issue-description`

### Commit Messages

Use clear, descriptive commit messages:

```
feat: add sector rotation scanner
fix: correct RSI divergence detection edge case
docs: update Discord alert format examples
refactor: extract signal scoring into dedicated module
test: add VCP strategy validation tests
```

### Pull Requests

1. Create a feature branch from `develop`.
2. Make your changes with tests.
3. Ensure `pytest`, `black`, and `ruff` pass locally.
4. Open a PR against `develop` with a clear description.
5. Link any related issues.

---

## Code Standards

- **Python 3.11+** required.
- **Black** for formatting (default config).
- **Ruff** for linting.
- **Type hints** on all public functions.
- **Pydantic v2** for data models.
- **Docstrings** on modules, classes, and public methods.

### Testing

- All new features should include tests.
- Tests go in `tests/` with `test_` prefix.
- Use `pytest` fixtures for shared setup.
- Mock external APIs (broker, market data, LLM) in tests.

---

## Areas Where Help Is Needed

| Area | Difficulty | Description |
|------|-----------|-------------|
| Strategy implementations | Medium | Add or improve VCP, swing, breakout strategies |
| Backtesting validation | Medium | Improve walk-forward and out-of-sample testing |
| Discord UX | Easy–Medium | Improve embed formatting, alert clarity |
| Documentation | Easy | Improve setup guides, strategy explanations |
| Broker integrations | Hard | Improve Futu, IBKR, Alpaca reliability |
| Test coverage | Easy–Medium | Add unit tests for under-tested modules |
| Multi-language | Easy | Improve Traditional Chinese translations |

---

## Important Guidelines

### Financial Responsibility

- **Never** frame outputs as financial advice in code, docs, or Discord messages.
- Always include appropriate disclaimers.
- Use words like "signal", "research", "informational" — not "recommendation" or "guaranteed".
- If adding a new signal or strategy, document its limitations honestly.

### Security

- Never commit API keys, tokens, or passwords.
- Read [SECURITY.md](SECURITY.md) before handling credentials.
- Use least-privilege access for all integrations.

### Discord Bot Changes

- Test bot commands locally before submitting.
- Ensure embeds stay within Discord's limits (4096 chars description, 25 fields).
- Consider both English and Traditional Chinese users.

---

## Getting Help

- Open a GitHub Issue for bugs or feature discussions.
- Tag issues with appropriate labels (`bug`, `enhancement`, `good first issue`).
- Be respectful and constructive in all interactions.

---

## Code of Conduct

Be professional, respectful, and constructive. We welcome contributors of all
backgrounds and experience levels. Harassment, discrimination, or disrespectful
behavior will not be tolerated.

---

Thank you for helping make CC better! 🚀
