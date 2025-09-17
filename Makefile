.PHONY: help build clean publish test-publish install lint format dev

help: ## Show this help message
	@echo "Usage: make [target]"
	@echo ""
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-15s %s\n", $$1, $$2}'

build: ## Build the distribution packages
	uv build

clean: ## Remove build artifacts and cache files
	rm -rf dist/
	rm -rf build/
	rm -rf *.egg-info
	rm -rf src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

publish: clean ## Build and publish to PyPI
	rm -rf dist/*
	uv build
	@export $$(grep -v '^#' .env | xargs) && uv publish

test-publish: clean ## Build and publish to TestPyPI
	rm -rf dist/*
	uv build
	@export $$(grep -v '^#' .env | xargs) && uv publish --publish-url https://test.pypi.org/legacy/

install: ## Install the package in development mode
	uv pip install -e .

lint: ## Run linter checks
	uv run ruff check .

format: ## Format code with ruff
	uv run ruff check --fix .
	uv run ruff format .

dev: ## Run the development server
	uv run golinks

check: lint ## Check code quality (alias for lint)
	@echo "All checks passed!"