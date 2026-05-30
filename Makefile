# ── Aiden Makefile ────────────────────────────────────────────

.PHONY: help install dev api ui cli test lint clean docker docker-up

VENV = venv
PYTHON = python3
PIP = $(VENV)/bin/pip

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
	awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install dependencies
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt
	@echo "✅ Done. Activate: source $(VENV)/bin/activate"

dev: ## Install dev dependencies (including test)
	$(PYTHON) -m venv $(VENV)
	$(PIP) install -r requirements.txt
	@echo "✅ Dev environment ready."

api: ## Start the FastAPI server
	uvicorn aiden.api.server:app --reload --host 0.0.0.0 --port 8000

ui: ## Start the Streamlit web UI
	streamlit run web/app.py

cli: ## Start the CLI REPL
	$(PYTHON) -m aiden

test: ## Run tests
	$(PYTHON) -m pytest tests/ -v --asyncio-mode=auto

test-coverage: ## Run tests with coverage
	$(PYTHON) -m pytest tests/ -v --asyncio-mode=auto --cov=aiden

lint: ## Run linter
	$(PYTHON) -m pip install -q ruff
	$(PYTHON) -m ruff check aiden/ tests/
	$(PYTHON) -m py_compile aiden/core/config.py

clean: ## Clean temp files
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf *.egg-info
	@echo "✅ Cleaned."

docker: ## Build Docker images
	docker compose build

docker-up: ## Start Docker services
	docker compose up -d
	@echo "✅ API: http://localhost:8000  UI: http://localhost:8501"

docker-down: ## Stop Docker services
	docker compose down

setup: ## Quick setup: install + init .env
	cp -n .env.example .env 2>/dev/null || true
	$(MAKE) install
	@echo ""
	@echo "╔══════════════════════════════════════════╗"
	@echo "║   Aiden setup complete!                  ║"
	@echo "║                                          ║"
	@echo "║   Edit .env with your ANTHROPIC_API_KEY   ║"
	@echo "║   Then: make api        (API server)     ║"
	@echo "║         make ui         (Web UI)         ║"
	@echo "║         make cli        (Terminal chat)  ║"
	@echo "╚══════════════════════════════════════════╝"
