.PHONY: dev dev-reload lint test smoke test-api clean migrate migrate-create db-shell install docker-build docker-up

# ── Development ──
dev:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

dev-no-reload:
	uvicorn backend.app.main:app --host 0.0.0.0 --port 8000

prod:
	gunicorn backend.app.main:app --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4

# ── Quality ──
lint:
	python3 -m py_compile backend/app/main.py
	find backend -name "*.py" -exec python3 -m py_compile {} \;

lint-frontend:
	@echo "Checking HTML files for common issues..."
	@for f in frontend/*.html; do \
		grep -q '</html>' $$f || echo "WARNING: $$f missing closing html tag"; \
	done
	@echo "Frontend check complete."

# ── Testing ──
test:
	python3 -m pytest tests/ -v --tb=short

smoke:
	python3 -m pytest tests/test_deployment_smoke.py tests/test_security_headers.py -v --tb=short

test-api:
	python3 -m pytest tests/test_api.py -v --tb=short

test-auth:
	python3 -m pytest tests/test_auth.py -v --tb=short

test-coverage:
	python3 -m pytest tests/ -v --tb=short --cov=backend/app --cov-report=term

# ── Database ──
migrate:
	alembic upgrade head

migrate-create:
	@read -p "Migration name: " name; alembic revision --autogenerate -m "$$name"

db-shell:
	sqlite3 backend/data/nexus.db

# ── Docker ──
docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down

docker-logs:
	docker compose logs -f

# ── Cleanup ──
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	rm -rf .pytest_cache
	rm -rf backend/data/*.db
	@echo "Cleaned."

# ── Setup ──
install:
	pip install -r requirements.txt

setup-dev: install
	pip install pytest pytest-asyncio pytest-cov httpx
	@echo "Dev dependencies installed."
	python3 -c "from backend.app.core.config import settings; print('Config OK:', settings.OLLAMA_MODEL)"
	@echo "Setup complete."

# ── Help ──
help:
	@echo "Nexus-UGC Makefile"
	@echo "──────────────────"
	@grep -E '^[a-zA-Z_-]+:' Makefile | sed 's/://' | sort | while read cmd; do \
		sed -n '/^'"$$cmd"':/,/^$$/p' Makefile | head -1 | grep -q "##" && \
		echo "  $$cmd: $$(grep -A1 '^'"$$cmd"':' Makefile | tail -1 | sed 's/#//')" || \
		echo "  $$cmd"; \
	done
