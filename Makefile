# Ohmni Oracle v3 - Development Makefile
# Usage: make <target>
# Example: make run INPUT=./test_data

.PHONY: help install setup run run-single test clean lint format check-env venv \
	index-pack index-rebuild index-templates index-check index-set-project

ifneq (,$(wildcard .env))
    include .env
    AZURE_SEARCH_ENDPOINT := $(subst ",,$(strip $(AZURE_SEARCH_ENDPOINT)))
    AZURE_SEARCH_API_KEY := $(subst ",,$(strip $(AZURE_SEARCH_API_KEY)))
    INDEX_NAME := $(subst ",,$(strip $(INDEX_NAME)))
    AZURE_SEARCH_API_VERSION := $(subst ",,$(strip $(AZURE_SEARCH_API_VERSION)))
    OPENAI_API_KEY := $(subst ",,$(strip $(OPENAI_API_KEY)))
    export AZURE_SEARCH_ENDPOINT AZURE_SEARCH_API_KEY INDEX_NAME AZURE_SEARCH_API_VERSION OPENAI_API_KEY
endif

PROJECT_FILE ?= .project_id
PROJECT ?= $(shell cat $(PROJECT_FILE) 2>/dev/null || echo ohmni-elecshuffletest)
SOURCE ?= $(CURDIR)/processed
PROCESSED_DIR := $(SOURCE)
TEMPLATES_ROOT ?= $(PROCESSED_DIR)/room-data
INDEX_OUT_DIR ?= $(CURDIR)/tmp/index_out
INDEX_NAME ?= drawings_unified
export INDEX_NAME

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
	@echo "  make run-single FILE=<file_path> [OUTPUT=<folder>]  - Run on a single PDF file"
	@echo "  make run-example    - Run with example data (if available)"
	@echo ""
	@echo "Index Management:"
	@echo "  make index-pack         - Regenerate sheets/facts/templates JSONL payloads"
	@echo "  make index-rebuild      - Recreate drawings_unified and upload all docs"
	@echo "  make index-templates    - Incremental template-only upsert"
	@echo "  make index-check        - Run query_playbook sanity checks"
	@echo "  make index-set-project PROJECT=<id> - Persist default project id for indexing"
	@echo "    (Override source path with SOURCE=/absolute/path/to/processed)"
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
	@echo "  make run-single FILE=/path/to/file.pdf"
	@echo "  make run-single FILE=/path/to/file.pdf OUTPUT=./results"
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

# Run on a single PDF file
run-single: check-env
	@if [ -z "$(FILE)" ]; then \
		echo "❌ Error: FILE parameter required"; \
		echo "Usage: make run-single FILE=<file_path> [OUTPUT=<output_folder>]"; \
		echo "Example: make run-single FILE=/path/to/file.pdf"; \
		exit 1; \
	fi
	@if [ ! -f "$(FILE)" ]; then \
		echo "❌ Error: File '$(FILE)' does not exist"; \
		exit 1; \
	fi
	@echo "🚀 Running Ohmni Oracle v3 on single file..."
	@echo "File: $(FILE)"
	@echo "Output: $(if $(OUTPUT),$(OUTPUT),$(dir $(FILE))output)"
	@# Create temporary folder structure
	@TEMP_DIR=$$(mktemp -d) && \
	FILE_DIR=$$(dirname "$(FILE)") && \
	FILE_NAME=$$(basename "$(FILE)") && \
	FILE_EXT=$${FILE_NAME##*.} && \
	FILE_BASE=$${FILE_NAME%.*} && \
	# Determine drawing type from folder name or file name
	if echo "$$FILE_DIR" | grep -qi "electrical"; then \
		DRAWING_TYPE="Electrical"; \
	elif echo "$$FILE_DIR" | grep -qi "mechanical"; then \
		DRAWING_TYPE="Mechanical"; \
	elif echo "$$FILE_DIR" | grep -qi "plumbing"; then \
		DRAWING_TYPE="Plumbing"; \
	elif echo "$$FILE_DIR" | grep -qi "architectural"; then \
		DRAWING_TYPE="Architectural"; \
	else \
		DRAWING_TYPE="General"; \
	fi && \
	# Create type-specific folder and copy file
	mkdir -p "$$TEMP_DIR/$$DRAWING_TYPE" && \
	cp "$(FILE)" "$$TEMP_DIR/$$DRAWING_TYPE/" && \
	# Set output directory
	if [ -n "$(OUTPUT)" ]; then \
		OUTPUT_DIR="$(OUTPUT)"; \
	else \
		OUTPUT_DIR="$$FILE_DIR/output"; \
	fi && \
	# Run processing
	python main.py "$$TEMP_DIR" "$$OUTPUT_DIR" && \
	# Clean up temp directory
	rm -rf "$$TEMP_DIR" && \
	echo "✅ Processing complete! Output saved to: $$OUTPUT_DIR"

# Run with example data (if available)
run-example: check-env
	@if [ -d "tests/test_data" ]; then \
		echo "🚀 Running with test data..."; \
		python main.py "tests/test_data"; \
	else \
		echo "❌ No test data found in tests/test_data/"; \
		echo "Create test data or specify INPUT folder"; \
	fi

index-pack: check-env
	@mkdir -p $(INDEX_OUT_DIR)
	@echo "📦 Regenerating index payloads for project: $(PROJECT)"
	@echo "   Source: $(PROCESSED_DIR)"
	python3 tools/schedule_postpass/transform.py \
	  $(PROCESSED_DIR) \
	  $(INDEX_OUT_DIR) \
	  $(PROJECT) \
	  --templates-root $(TEMPLATES_ROOT)
	@echo "✅ Payloads written to $(INDEX_OUT_DIR)"

index-rebuild: index-pack
	@echo "🚀 Rebuilding Azure Search index '$(INDEX_NAME)'"
	python3 tools/schedule_postpass/upsert_index.py \
	  --schema tools/schedule_postpass/unified_index.schema.json \
	  --synonyms tools/schedule_postpass/synonyms.seed.json \
	  --sheets $(INDEX_OUT_DIR)/sheets.jsonl \
	  --facts  $(INDEX_OUT_DIR)/facts.jsonl \
	  --drawings $(INDEX_OUT_DIR)/drawings_unified.jsonl \
	  --templates $(INDEX_OUT_DIR)/templates.jsonl \
	  --mode full
	@echo "✅ Index rebuild complete"

index-templates: index-pack
	@echo "🚀 Incrementally updating template docs in '$(INDEX_NAME)'"
	python3 tools/schedule_postpass/upsert_index.py \
	  --schema tools/schedule_postpass/unified_index.schema.json \
	  --templates $(INDEX_OUT_DIR)/templates.jsonl \
	  --mode incremental
	@echo "✅ Template upsert complete"

index-check: check-env
	@echo "🔍 Running query_playbook sanity checks..."
	python3 tools/schedule_postpass/query_playbook.py

index-set-project:
	@if [ -z "$(PROJECT)" ]; then \
		echo "❌ Error: PROJECT parameter required"; \
		echo "Usage: make index-set-project PROJECT=<id>"; \
		exit 1; \
	fi
	@echo $(PROJECT) > $(PROJECT_FILE)
	@echo "✅ Default indexing project set to '$(PROJECT)'"

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
