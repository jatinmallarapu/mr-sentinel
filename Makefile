# Run the same model-free evaluation locally and in CI.
.PHONY: dev serve test eval lint

dev:
	python -m mr_sentinel.demo

serve:
	python -m uvicorn mr_sentinel.api:app --host 127.0.0.1 --port 8000

test:
	python -m pytest --cov=mr_sentinel --cov-report=term-missing --cov-fail-under=85

eval:
	python evals/run_eval.py --fixture --output runs/smoke.json

lint:
	ruff check .
	ruff format --check .
