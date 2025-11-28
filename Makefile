.PHONY: help install test run demo docker-build docker-run clean

help:
	@echo "Available commands:"
	@echo "  make install       - Install dependencies"
	@echo "  make test          - Run pytest suite"
	@echo "  make run           - Start server locally"
	@echo "  make demo          - Run demo script"
	@echo "  make docker-build  - Build Docker image"
	@echo "  make docker-run    - Run Docker container"
	@echo "  make clean         - Remove temp files and logs"

install:
	pip install -r requirements.txt
	playwright install chromium

test:
	pytest tests/ -v --tb=short

run:
	uvicorn main:app --reload --host 0.0.0.0 --port 8000

demo:
	bash run_demo.sh

docker-build:
	docker build -t llm-quiz-solver .

docker-run:
	docker run -e QUIZ_SECRET="test_secret" -p 8000:8000 llm-quiz-solver

clean:
	rm -rf temp/* logs/* __pycache__ .pytest_cache *.pyc
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true