# ==========================================
# FilantropiaSolar - Development Makefile
# ==========================================

.PHONY: help install test lint format typecheck docs clean build docker dev-setup run

# Default target
.DEFAULT_GOAL := help

# Variables
PYTHON := python3
PIP := pip
VENV := venv
SRC_DIR := src
TEST_DIR := tests
DOCS_DIR := docs
PACKAGE_NAME := filantropia_solar

# Colors for output
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RED := \033[31m
RESET := \033[0m

# Help target
help: ## Show this help message
	@echo "$(BLUE)FilantropiaSolar Development Commands$(RESET)"
	@echo "======================================"
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-15s$(RESET) %s\n", $$1, $$2 } /^##@/ { printf "\n$(YELLOW)%s$(RESET)\n", substr($$0, 5) } ' $(MAKEFILE_LIST)
	@echo ""

##@ Development Environment

dev-setup: ## Run the automated development setup script
	@echo "$(BLUE)Running development setup...$(RESET)"
	@chmod +x scripts/dev-setup.sh
	@./scripts/dev-setup.sh

venv: ## Create virtual environment
	@echo "$(BLUE)Creating virtual environment...$(RESET)"
	@$(PYTHON) -m venv $(VENV)
	@echo "$(GREEN)Virtual environment created. Activate with: source $(VENV)/bin/activate$(RESET)"

install: ## Install dependencies
	@echo "$(BLUE)Installing dependencies...$(RESET)"
	@$(PIP) install --upgrade pip setuptools wheel
	@$(PIP) install -r requirements-dev.txt
	@$(PIP) install -e .
	@echo "$(GREEN)Dependencies installed$(RESET)"

install-prod: ## Install production dependencies only
	@echo "$(BLUE)Installing production dependencies...$(RESET)"
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@$(PIP) install -e .
	@echo "$(GREEN)Production dependencies installed$(RESET)"

##@ Code Quality

lint: ## Run linting with ruff
	@echo "$(BLUE)Running linting...$(RESET)"
	@ruff check --select=E9,F63,F7,F82 --target-version=py311 .
	@ruff check . --statistics
	@echo "$(GREEN)Linting completed$(RESET)"

format: ## Format code with ruff
	@echo "$(BLUE)Formatting code...$(RESET)"
	@ruff format .
	@ruff check --fix .
	@echo "$(GREEN)Code formatted$(RESET)"

typecheck: ## Run type checking with mypy
	@echo "$(BLUE)Running type checking...$(RESET)"
	@mypy $(SRC_DIR)/ --config-file=pyproject.toml
	@echo "$(GREEN)Type checking completed$(RESET)"

security: ## Run security scan with bandit
	@echo "$(BLUE)Running security scan...$(RESET)"
	@bandit -r $(SRC_DIR)/ -c pyproject.toml
	@echo "$(GREEN)Security scan completed$(RESET)"

pre-commit: ## Run pre-commit hooks on all files
	@echo "$(BLUE)Running pre-commit hooks...$(RESET)"
	@pre-commit run --all-files
	@echo "$(GREEN)Pre-commit hooks completed$(RESET)"

quality: lint typecheck security ## Run all code quality checks

##@ Testing

test: ## Run tests with pytest
	@echo "$(BLUE)Running tests...$(RESET)"
	@pytest $(TEST_DIR)/ -v
	@echo "$(GREEN)Tests completed$(RESET)"

test-cov: ## Run tests with coverage
	@echo "$(BLUE)Running tests with coverage...$(RESET)"
	@pytest $(TEST_DIR)/ -v \
		--cov=$(SRC_DIR)/$(PACKAGE_NAME) \
		--cov-report=html \
		--cov-report=xml \
		--cov-report=term-missing \
		--cov-fail-under=80
	@echo "$(GREEN)Coverage report generated: htmlcov/index.html$(RESET)"

test-unit: ## Run unit tests only
	@echo "$(BLUE)Running unit tests...$(RESET)"
	@pytest $(TEST_DIR)/ -v -m "unit"
	@echo "$(GREEN)Unit tests completed$(RESET)"

test-integration: ## Run integration tests only
	@echo "$(BLUE)Running integration tests...$(RESET)"
	@pytest $(TEST_DIR)/ -v -m "integration"
	@echo "$(GREEN)Integration tests completed$(RESET)"

test-performance: ## Run performance benchmarks
	@echo "$(BLUE)Running performance benchmarks...$(RESET)"
	@pytest $(TEST_DIR)/performance/ -v --benchmark-only
	@echo "$(GREEN)Performance benchmarks completed$(RESET)"

test-ml: ## Run ML model tests
	@echo "$(BLUE)Running ML model tests...$(RESET)"
	@pytest $(TEST_DIR)/ -v -m "ml" --timeout=300
	@echo "$(GREEN)ML model tests completed$(RESET)"

##@ Documentation

docs: ## Build documentation
	@echo "$(BLUE)Building documentation...$(RESET)"
	@mkdocs build
	@echo "$(GREEN)Documentation built: site/index.html$(RESET)"

docs-serve: ## Serve documentation locally
	@echo "$(BLUE)Serving documentation at http://localhost:8000$(RESET)"
	@mkdocs serve

docs-deploy: ## Deploy documentation to GitHub Pages
	@echo "$(BLUE)Deploying documentation...$(RESET)"
	@mkdocs gh-deploy
	@echo "$(GREEN)Documentation deployed$(RESET)"

##@ Application

run: ## Run the application
	@echo "$(BLUE)Running FilantropiaSolar...$(RESET)"
	@$(PYTHON) -m $(PACKAGE_NAME).cli

run-gui: ## Run GUI application
	@echo "$(BLUE)Running FilantropiaSolar GUI...$(RESET)"
	@$(PYTHON) -m $(PACKAGE_NAME).gui.main

run-api: ## Run API server
	@echo "$(BLUE)Starting API server at http://localhost:8000$(RESET)"
	@uvicorn $(PACKAGE_NAME).api.main:app --reload --host 0.0.0.0 --port 8000

##@ Docker

docker-build: ## Build Docker image
	@echo "$(BLUE)Building Docker image...$(RESET)"
	@docker build -t filantropia-solar:latest .
	@echo "$(GREEN)Docker image built$(RESET)"

docker-build-dev: ## Build development Docker image
	@echo "$(BLUE)Building development Docker image...$(RESET)"
	@docker build --target development -t filantropia-solar:dev .
	@echo "$(GREEN)Development Docker image built$(RESET)"

docker-run: ## Run Docker container
	@echo "$(BLUE)Running Docker container...$(RESET)"
	@docker run -it --rm \
		-v $(PWD)/data:/app/data:ro \
		-v $(PWD)/exports:/app/exports \
		filantropia-solar:latest

docker-up: ## Start all services with docker-compose
	@echo "$(BLUE)Starting all services...$(RESET)"
	@docker-compose up -d
	@echo "$(GREEN)All services started$(RESET)"

docker-down: ## Stop all services
	@echo "$(BLUE)Stopping all services...$(RESET)"
	@docker-compose down
	@echo "$(GREEN)All services stopped$(RESET)"

docker-logs: ## View Docker logs
	@docker-compose logs -f

##@ Build & Release

build: ## Build package
	@echo "$(BLUE)Building package...$(RESET)"
	@$(PYTHON) -m build
	@echo "$(GREEN)Package built in dist/$(RESET)"

build-check: ## Check package build
	@echo "$(BLUE)Checking package build...$(RESET)"
	@twine check dist/*
	@echo "$(GREEN)Package build verified$(RESET)"

release-test: build build-check ## Release to TestPyPI
	@echo "$(BLUE)Uploading to TestPyPI...$(RESET)"
	@twine upload --repository testpypi dist/*
	@echo "$(GREEN)Package uploaded to TestPyPI$(RESET)"

release: build build-check ## Release to PyPI
	@echo "$(YELLOW)Uploading to PyPI...$(RESET)"
	@twine upload dist/*
	@echo "$(GREEN)Package uploaded to PyPI$(RESET)"

##@ Maintenance

clean: ## Clean up build artifacts and cache
	@echo "$(BLUE)Cleaning up...$(RESET)"
	@rm -rf build/
	@rm -rf dist/
	@rm -rf *.egg-info/
	@rm -rf .pytest_cache/
	@rm -rf .mypy_cache/
	@rm -rf .ruff_cache/
	@rm -rf htmlcov/
	@rm -rf site/
	@find . -type d -name __pycache__ -exec rm -rf {} +
	@find . -type f -name "*.pyc" -delete
	@find . -type f -name "*.pyo" -delete
	@find . -type f -name "*.orig" -delete
	@find . -type f -name ".coverage" -delete
	@echo "$(GREEN)Cleanup completed$(RESET)"

clean-all: clean ## Clean everything including virtual environment
	@echo "$(BLUE)Cleaning everything...$(RESET)"
	@rm -rf $(VENV)/
	@rm -rf models/
	@rm -rf logs/
	@echo "$(GREEN)Complete cleanup finished$(RESET)"

update-deps: ## Update dependencies
	@echo "$(BLUE)Updating dependencies...$(RESET)"
	@$(PIP) install --upgrade pip setuptools wheel
	@$(PIP) install --upgrade -r requirements-dev.txt
	@echo "$(GREEN)Dependencies updated$(RESET)"

##@ Monitoring & Profiling

profile: ## Run performance profiling
	@echo "$(BLUE)Running performance profiling...$(RESET)"
	@$(PYTHON) -m cProfile -s tottime -m $(PACKAGE_NAME).cli > profile.txt
	@echo "$(GREEN)Profile saved to profile.txt$(RESET)"

memory-profile: ## Run memory profiling
	@echo "$(BLUE)Running memory profiling...$(RESET)"
	@mprof run $(PYTHON) -m $(PACKAGE_NAME).cli
	@mprof plot
	@echo "$(GREEN)Memory profile completed$(RESET)"

benchmark: ## Run benchmarks
	@echo "$(BLUE)Running benchmarks...$(RESET)"
	@$(PYTHON) -m pytest tests/performance/ --benchmark-only --benchmark-sort=mean
	@echo "$(GREEN)Benchmarks completed$(RESET)"

##@ Database

db-init: ## Initialize database
	@echo "$(BLUE)Initializing database...$(RESET)"
	@docker-compose exec postgres psql -U fs_user -d filantropia_solar -c "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;"
	@echo "$(GREEN)Database initialized$(RESET)"

db-migrate: ## Run database migrations
	@echo "$(BLUE)Running database migrations...$(RESET)"
	@alembic upgrade head
	@echo "$(GREEN)Database migrations completed$(RESET)"

db-reset: ## Reset database
	@echo "$(YELLOW)Resetting database...$(RESET)"
	@docker-compose down -v
	@docker-compose up -d postgres
	@sleep 5
	@make db-init
	@make db-migrate
	@echo "$(GREEN)Database reset completed$(RESET)"

##@ Information

version: ## Show version information
	@echo "$(BLUE)Version Information:$(RESET)"
	@echo "Python: $$($(PYTHON) --version)"
	@echo "Pip: $$($(PIP) --version)"
	@echo "Package: $$($(PYTHON) -c 'import $(PACKAGE_NAME); print($(PACKAGE_NAME).__version__)')" 2>/dev/null || echo "Package not installed"

env-info: ## Show environment information
	@echo "$(BLUE)Environment Information:$(RESET)"
	@echo "OS: $$(uname -s)"
	@echo "Architecture: $$(uname -m)"
	@echo "Python Path: $$(which $(PYTHON))"
	@echo "Virtual Environment: $${VIRTUAL_ENV:-Not activated}"
	@echo "Working Directory: $$(pwd)"

deps-check: ## Check for outdated dependencies
	@echo "$(BLUE)Checking for outdated dependencies...$(RESET)"
	@$(PIP) list --outdated

##@ Aliases (shortcuts)

t: test ## Alias for test
f: format ## Alias for format
l: lint ## Alias for lint
r: run ## Alias for run
c: clean ## Alias for clean
b: build ## Alias for build
d: docs ## Alias for docs