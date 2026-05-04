.PHONY: help dev prod test lint docker clean install

# Default target
help:
	@echo "CC — Regime-Aware Market Intelligence Platform (v6.1)"
	@echo "Usage:"
	@echo "  make dev     # Local development (venv + services)"
	@echo "  make prod    # Production Docker"
	@echo "  make test    # Run pytest + coverage"
	@echo "  make lint    # Black + ruff + mypy"
	@echo "  make install # pip install -e .[dev]"
	@echo "  make clean   # Clean artifacts"

# ── Development ──────────────────────────────────────────────────────
dev: install
	pip install -e .[dev]
	python -m src.engines.main &  # AutoTradingEngine
	docker compose up -d postgres redis  # Core services
	@echo "✅ Dev environment ready!"
	@echo "• Engine: http://localhost:8001/health"
	@echo "• API: http://localhost:8000/docs"
	@echo "• Run Discord: make discord"
	@echo "• Full stack: make docker-dev"

install:
	pip install poetry
	poetry install --only dev

discord:
	python run_discord_bot.py

# ── Production ───────────────────────────────────────────────────────
prod:
	docker compose up -d

docker-dev:
	docker compose --profile dev up -d

docker-logs:
	docker compose logs -f

# ── Testing ──────────────────────────────────────────────────────────
test:
	pytest tests/ -v --cov=src --cov-report=html

test-sprints:
	pytest tests/sprints/ -v

# ── Quality ──────────────────────────────────────────────────────────
lint:
	black .
	ruff check --fix src tests
	ruff format src tests
	mypy src

format:
	black .
	ruff format src tests

# ── Clean ────────────────────────────────────────────────────────────
clean:
	rm -rf .coverage htmlcov/ dist/ *.egg-info/
	docker compose down -v
	poetry cache clear --all pypi
	find . -name '__pycache__' -exec rm -rf {} +
	find . -name '*.pyc' -delete

# ── Docker ───────────────────────────────────────────────────────────
docker-build:
	docker compose build

docker-push:
	docker compose push

