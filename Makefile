.PHONY: install install-dev bootstrap init-db test-run test-analysis run run-date dashboard scheduler test test-unit test-integration clean verify-phases

install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements-dev.txt

init-db:
	python -c "from src.storage.db import init_db; init_db(); print('DB initialised')"

bootstrap: init-db
	python scripts/bootstrap_universe.py

test-run:
	python scripts/test_run.py

test-analysis:
	python scripts/test_analysis.py

run:
	python main.py run

run-date:
	python main.py run --date $(DATE)

dashboard:
	streamlit run src/dashboard/app.py --server.port 8501

scheduler:
	python -m src.scheduler

test:
	pytest tests/ -v --tb=short

test-unit:
	pytest tests/unit/ -v --tb=short

test-integration:
	pytest tests/integration/ -v --tb=short

verify-phases:
	@echo "=== Phase 1 verification ==="
	python scripts/test_run.py
	@echo "=== Phase 2 verification ==="
	python scripts/test_analysis.py

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
