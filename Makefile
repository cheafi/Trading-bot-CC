.PHONY: help dev prod test lint docker clean install cleanup-inventory cleanup-dry-run git-maintenance

# Default target
help:
	@echo "CC — Regime-Aware Market Intelligence Platform (v9.6)"
	@echo "Usage:"
	@echo "  make dev     # Local development (venv + services)"
	@echo "  make prod    # Production Docker"
	@echo "  make test    # Run pytest (sprints 100-103)"
	@echo "  make lint    # Black + ruff + mypy"
	@echo "  make install # pip install -e .[dev]"
	@echo "  make clean   # Remove caches, logs, build artefacts"

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
	bash cleanup.sh

cleanup-inventory:
	bash cleanup.sh inventory

cleanup-dry-run:
	bash cleanup.sh dry-run

git-maintenance:
	git count-objects -vH
	git gc --prune=now
	git repack -Ad
	git commit-graph write --reachable --changed-paths

# ── Docker ───────────────────────────────────────────────────────────
docker-build:
	docker compose build

docker-push:
	docker compose push

