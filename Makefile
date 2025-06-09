# Ultimate PDF Parser - Development Toolkit
.PHONY: help install dev-install clean lint format test test-accuracy ci-local docker-test

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

install:  ## Install production dependencies
	pip install -e .

dev-install:  ## Install development dependencies
	pip install -e ".[dev,ai]"
	pre-commit install

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/
	rm -rf htmlcov/ .coverage
	rm -rf .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -delete

lint:  ## Run linting
	ruff check . --fix
	black --check .
	mypy .

format:  ## Format code
	ruff check . --fix
	black .

test:  ## Run tests
	pytest --cov=. --cov-report=html --cov-report=term-missing

test-accuracy:  ## Run accuracy tests only
	pytest tests/test_parser_accuracy.py -v

ci-local:  ## Run full CI pipeline locally
	./scripts/ci_local.sh

docker-test:  ## Test using act (GitHub Actions locally)
	act pull_request --job lint-and-test

validate-golden:  ## Validate all outputs against golden CSVs
	python golden_validator.py
	
ai-parse:  ## Run AI-enhanced parsing
	python ai_enhanced_parser.py

full-corpus:  ## Process all PDFs
	python process_all_pdfs.py

setup-hooks:  ## Setup git hooks
	pre-commit install
	echo "#!/bin/sh\nmake ci-local" > .git/hooks/pre-push
	chmod +x .git/hooks/pre-push
