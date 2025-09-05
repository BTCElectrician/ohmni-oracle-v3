# Ohmni Oracle v3 - Development Makefile
# Usage: make <target>
# Example: make run INPUT=./test_data

.PHONY: help install setup run test clean lint format check-env venv

# Default target
help:
	@echo "Ohmni Oracle v3 - Available Commands:"
	@echo ""
	@echo "Setup & Environment:"
	@echo "  make setup          - Set up virtual environment and install dependencies"
	@echo "  make install        - Install/update Python dependencies"
	@echo "  make venv           - Create virtual environment"
	@echo "  make check-env      - Check if virtual environment is active"
	@echo ""
	@echo "Running the Application:"
	@echo "  make run INPUT=<folder> [OUTPUT=<folder>]  - Run the main script"
	@echo "  make run-example    - Run with example data (if available)"
	@echo ""
	@echo "Development & Testing:"
	@echo "  make test           - Run all tests"
	@echo "  make test-coverage  - Run tests with coverage report"
	@echo "  make lint           - Run code linting (ruff)"
	@echo "  make format         - Format code (ruff)"
	@echo "  make check          - Run linting and type checking"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean          - Clean up temporary files and cache"
	@echo "  make clean-venv     - Remove virtual environment"
	@echo "  make clean-all      - Clean everything including venv"
	@echo ""
	@echo "Examples:"
	@echo "  make run INPUT=./test_data"
	@echo "  make run INPUT=./test_data OUTPUT=./results"
	@echo "  make setup && make run INPUT=./test_data"

# Setup virtual environment and install dependencies
setup: venv install
	@echo "✅ Setup complete! Activate with: source venv/bin/activate"

# Create virtual environment
venv:
	@if [ ! -d "venv" ]; then \
		echo "Creating virtual environment..."; \
		python3 -m venv venv; \
		echo "✅ Virtual environment created"; \
	else \
		echo "✅ Virtual environment already exists"; \
	fi

# Install dependencies
install: check-env
	@echo "Installing dependencies..."
	pip install --upgrade pip
	pip install -r requirements.txt
	@echo "✅ Dependencies installed"

# Check if virtual environment is active
check-env:
	@if [ -z "$$VIRTUAL_ENV" ]; then \
		echo "⚠️  Virtual environment not active. Run: source venv/bin/activate"; \
		echo "   Or use: make setup"; \
		exit 1; \
	fi

# Run the main application
run: check-env
	@if [ -z "$(INPUT)" ]; then \
		echo "❌ Error: INPUT parameter required"; \
		echo "Usage: make run INPUT=<input_folder> [OUTPUT=<output_folder>]"; \
		echo "Example: make run INPUT=./test_data"; \
		exit 1; \
	fi
	@echo "🚀 Running Ohmni Oracle v3..."
	@echo "Input: $(INPUT)"
	@echo "Output: $(if $(OUTPUT),$(OUTPUT),$(INPUT)/output)"
	python main.py "$(INPUT)" $(if $(OUTPUT),"$(OUTPUT)")

# Run with example data (if available)
run-example: check-env
	@if [ -d "tests/test_data" ]; then \
		echo "🚀 Running with test data..."; \
		python main.py "tests/test_data"; \
	else \
		echo "❌ No test data found in tests/test_data/"; \
		echo "Create test data or specify INPUT folder"; \
	fi

# Run tests
test: check-env
	@echo "🧪 Running tests..."
	python -m pytest tests/ -v

# Run tests with coverage
test-coverage: check-env
	@echo "🧪 Running tests with coverage..."
	python -m pytest tests/ --cov=. --cov-report=html --cov-report=term

# Run code linting
lint: check-env
	@echo "🔍 Running code linting..."
	ruff check .

# Format code
format: check-env
	@echo "✨ Formatting code..."
	ruff format .

# Run linting and type checking
check: check-env lint
	@echo "🔍 Running type checking..."
	mypy . --ignore-missing-imports

# Clean up temporary files and cache
clean:
	@echo "🧹 Cleaning up temporary files..."
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleanup complete"

# Remove virtual environment
clean-venv:
	@echo "🧹 Removing virtual environment..."
	rm -rf venv
	@echo "✅ Virtual environment removed"

# Clean everything including virtual environment
clean-all: clean clean-venv
	@echo "✅ Complete cleanup finished"

# Quick development workflow
dev: format lint test
	@echo "✅ Development checks passed"

# Production build check
prod-check: check test
	@echo "✅ Production readiness check passed"
