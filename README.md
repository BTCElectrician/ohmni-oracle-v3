Here's an updated README that reflects the current codebase (Chat Completions for extraction, OCR with tiling, improved title-block logic, JSON repair toggles, and normalization pipeline). Replace your README.md with the following:

```md
# Ohmni Oracle v3 — Construction Drawing Processor

<div align="center">
  <img src="assets/github-owl.png" alt="Ohmni Oracle Logo" width="400" height="200">
  <br>
  <em>AI-Powered Construction Drawing Extraction & Normalization</em>
</div>

## Overview

Ohmni Oracle v3 processes PDF construction drawings at scale. It extracts text and tables via PyMuPDF, augments content via OCR when needed, and converts everything into structured JSON using OpenAI’s Chat Completions API. The pipeline includes JSON repair, field normalization for schedules, metadata repair from title blocks, room template generation, caching, and detailed performance tracking.

Core disciplines supported:
- Architectural
- Electrical (incl. panel schedules)
- Mechanical (incl. equipment schedules)
- Plumbing (incl. fixture/equipment schedules)
- General/specification documents

## Features

- Asynchronous batch processing with worker queue and progress bars (tqdm)
- Intelligent OCR fallback with memory-safe tiling and 10% overlap
- Chat Completions API with strict JSON-only output
- Robust metadata repair from title blocks with non-destructive fallback filling
- JSON parsing with optional repair for tricky schedules
- Discipline-specific normalization (panel, mechanical, plumbing)
- Room file generation for Architectural floor plans
- AI response caching for 20–30x faster repeated runs
- Performance metrics and slowdown detection
- Clear status files for every outcome

## How It Works

1) Extraction (services/extraction_service.py)
- Uses PyMuPDF for text and optional table extraction per page
- Specialized extractors:
  - ArchitecturalExtractor: highlights room info; prioritizes relevant tables
  - ElectricalExtractor: marks/prefers panel schedules; enriches panel metadata
  - MechanicalExtractor: highlights equipment schedules
  - PlumbingExtractor: highlights fixtures/equipment/piping schedules
- Title block detection on page 1 with rotation handling, scoring, and truncation checks
- Configurable table extraction (ENABLE_TABLE_EXTRACTION)
- Produces ExtractionResult (raw_text, tables, metadata, titleblock_text, has_content)

2) OCR (services/ocr_service.py)
- Triggered when extracted text density is low:
  - per-page character threshold (OCR_THRESHOLD, default 1500 chars/page)
  - minimal total text heuristic
- Memory-safe tiling with 10% overlap (GRID x GRID, default 1x1) at configurable DPI (default 300)
- Uses OpenAI Responses API vision for OCR tiles (default model gpt-4o-mini)
- Processes up to OCR_MAX_PAGES pages (default 2)
- Appends OCR text to the extraction result and tracks metrics

3) AI Processing (services/ai_service.py)
- Single, comprehensive “GENERAL” prompt via PromptRegistry (templates/prompt_registry.py)
  - Registry always returns the GENERAL prompt at runtime
- Chat Completions API with response_format={"type": "json_object"}
- Dynamic model selection based on content size and document type
  - DEFAULT_MODEL (e.g., gpt-5-mini), LARGE_DOC_MODEL (e.g., gpt-5), SCHEDULE_MODEL (e.g., gpt-5), optional TINY_MODEL
  - NANO_CHAR_THRESHOLD and MINI_CHAR_THRESHOLD determine model tiers
  - Force mini override via FORCE_MINI_MODEL=true
  - Specification docs get token constraints (SPEC_MAX_TOKENS)
- AI cache for responses (ENABLE_AI_CACHE=true strongly recommended)

4) JSON Validation & Repair
- Strict JSON mode (response_format) + safe parse (utils/json_utils.py)
- Optional repair for complex schedules (ENABLE_JSON_REPAIR) using heuristics:
  - Fixes common bracket/comma/key quoting issues and truncated tails
- Mechanical drawings may perform a second AI attempt when MECH_SECOND_PASS=true

5) Metadata Repair
- Non-destructive fallback fill (_fill_critical_metadata_fallback)
  - Fill sheet/drawing numbers from filename
  - Clear bogus revision values
  - Extract revision and project_name from title block if present
- Optional focused repair pass (ENABLE_METADATA_REPAIR=true)
  - Runs a small model with a targeted metadata prompt
  - Merges fields into DRAWING_METADATA

6) Normalization (services/normalizers.py)
- Electrical: normalize panel schedule fields and validate structure
- Mechanical: re-group equipment into typed categories (fans, pumps, AHUs, etc.)
- Plumbing: normalize fixtures, water heaters, and piping fields

7) Output & Templates
- Saves structured JSON to <output>/<Type>/<file>_structured.json
- Architectural floor plans trigger room templates (templates/room_templates.py)
  - Generates <file>_a_rooms_details.json and <file>_e_rooms_details.json
- If unreadable/no content, saved status explains why and processing stops early

## Output and Status Files

- Success: <output>/<Type>/<name>_structured.json (success=true)
- Unreadable: <output>/<Type>/<name>_structured.json (status="skipped_unreadable", success=true)
- Extraction failed: <output>/<Type>/<name>_error.json (status="extraction_failed")
- AI/JSON failed: <output>/<Type>/<name>_error.json (status="ai_processing_failed"), may save a raw response file
- Save failed: <output>/<Type>/<name>_error.json (status="json_save_failed")
- Unexpected: <output>/<Type>/<name>_error.json (status="unexpected_error")
- Room files (Architectural): <output>/Architectural/<name>_a_rooms_details.json and _e_rooms_details.json
- Logs: <output>/logs/...; Performance metrics: <output>/metrics/...

Status values are defined in processing/file_processor.py (ProcessingStatus enum).

## Project Structure

- config/
  - settings.py .............. Environment-driven configuration
- processing/
  - file_processor.py ........ Orchestrates the per-file pipeline
  - job_processor.py ......... Manages queue, workers, and progress
- services/
  - extraction_service.py .... PDF text/tables extraction + discipline enhancers + title block
  - ai_service.py ............ Chat Completions integration, model routing, metadata repair
  - normalizers.py ........... Field normalization for panel/mech/plumbing
  - storage_service.py ....... Async JSON/text/binary save/read with date handling
  - ocr_service.py ........... OCR tiling via Responses API vision; per-page threshold trigger
- templates/
  - prompt_registry.py ....... Single-source prompt registry (GENERAL prompt runtime)
  - room_templates.py ........ Generates A/E room details JSONs
  - a_rooms_template.json .... Base template for architectural rooms
  - e_rooms_template.json .... Base template for electrical rooms
- utils/
  - ai_cache.py .............. Disk cache for AI responses
  - drawing_utils.py ......... Type/subtype detection from filenames
  - json_utils.py ............ JSON parsing and repair helpers
  - file_utils.py ............ Folder traversal
  - logging_utils.py ......... Logging configuration
  - performance_utils.py ..... Metrics aggregation and reporting
  - exceptions/ .............. Custom exception definitions
- main.py .................... Entry point (async)
- ohmni ...................... Convenience CLI wrapper (bash)
- Makefile ................... Dev workflow (install, run, test, lint)

## Installation

Prerequisites
- Python 3.11+
- OpenAI API key

Setup
```bash
git clone https://github.com/BTCElectrician/ohmni-oracle.git
cd ohmni-oracle-v3

python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set OPENAI_API_KEY plus recommended settings below
```

## Recommended .env Settings

Minimum
```dotenv
OPENAI_API_KEY=your_openai_api_key
LOG_LEVEL=INFO
```

Performance and stability
```dotenv
# Strongly recommended
ENABLE_AI_CACHE=true
AI_CACHE_TTL_HOURS=24

# Extraction performance (disable for max speed; enables for richer tables)
ENABLE_TABLE_EXTRACTION=false

# OCR
OCR_ENABLED=true
OCR_THRESHOLD=1500         # chars per page
OCR_MAX_PAGES=2
OCR_GRID_SIZE=1            # tiling grid (1=off)
OCR_DPI=300
OCR_MODEL=gpt-4o-mini
OCR_TOKENS_PER_TILE=3000

# AI model routing (text → Chat Completions)
DEFAULT_MODEL=gpt-5-mini
LARGE_DOC_MODEL=gpt-5
SCHEDULE_MODEL=gpt-5
TINY_MODEL=                 # optional (e.g., gpt-5-nano)
NANO_CHAR_THRESHOLD=3000
MINI_CHAR_THRESHOLD=15000
ACTUAL_MODEL_MAX_COMPLETION_TOKENS=32000

# Temperatures and max tokens
DEFAULT_MODEL_TEMP=0.1
DEFAULT_MODEL_MAX_TOKENS=16000
LARGE_MODEL_TEMP=0.1
LARGE_MODEL_MAX_TOKENS=16000
TINY_MODEL_TEMP=0.0
TINY_MODEL_MAX_TOKENS=8000

# Behavior toggles
FORCE_MINI_MODEL=false
ENABLE_METADATA_REPAIR=true
ENABLE_JSON_REPAIR=true
MECH_SECOND_PASS=true       # allow second AI attempt for mechanical
SPEC_MAX_TOKENS=16384

# Logging
PIPELINE_LOG_LEVEL=INFO     # to see detailed pipeline logs
RESPONSES_TIMEOUT_SECONDS=200
DEBUG_MODE=false
```

## Usage

Run a job (entire folder of PDFs)
```bash
python main.py <input_folder> [output_folder]
```
- Output defaults to <input_folder>/output when not provided.

Examples
```bash
# with Makefile helpers
make setup
make run INPUT=./my_job_folder
make run-single FILE=/path/to/my.pdf
```

Convenience CLI
```bash
# From repo root with venv active
./ohmni process MyProjectFolderOnDesktop
./ohmni file MyProjectFolderOnDesktop/Electrical/E1.01.pdf
```

## Model Routing Details

- Schedule/specification detection:
  - Determined by filename and drawing_type hints
  - SCHEDULE_MODEL is used for schedules/spec docs
- Size-based routing:
  - < NANO_CHAR_THRESHOLD → TINY_MODEL (if set) or DEFAULT_MODEL
  - < MINI_CHAR_THRESHOLD → DEFAULT_MODEL
  - >= MINI_CHAR_THRESHOLD → LARGE_DOC_MODEL
- Force-mini override: FORCE_MINI_MODEL=true routes non-schedules to DEFAULT_MODEL
- Specifications cap output tokens via SPEC_MAX_TOKENS

All text processing uses Chat Completions with response_format=json_object. OCR tiles use the Responses API vision endpoint.

## Architectural Room Templates

- Triggered for Architectural floor plans (file naming + metadata)
- Generates:
  - <name>_a_rooms_details.json (architectural)
  - <name>_e_rooms_details.json (electrical)
- Merges AI-parsed data onto template, with multiple fallbacks for room discovery

## Performance

- Caching (ENABLE_AI_CACHE=true): 20–30x faster on repeated runs
- Table extraction: ENABLE_TABLE_EXTRACTION=false avoids major extraction slowdowns
- OCR runs only when per-page density is low
- Metrics saved to <output>/metrics and summarized in logs
- Slowdown detection compares current API timing to historical averages

## Troubleshooting

- No output or empty JSON?
  - Check <output>/logs for warnings/errors
  - Verify ENABLE_TABLE_EXTRACTION=false for speed (or true if you need heavy table parsing)
  - Verify OCR settings; look for “OCR TRIGGERED/SKIPPED” logs
- JSON parsing failed?
  - Set ENABLE_JSON_REPAIR=true
  - Inspect saved _error.json and any raw response snippet
- Metadata incorrect or missing?
  - Set ENABLE_METADATA_REPAIR=true
  - Ensure title block text was extracted (logs show char counts and title block status)
- Timeouts?
  - Increase RESPONSES_TIMEOUT_SECONDS
  - Reduce max tokens (DEFAULT_MODEL_MAX_TOKENS / LARGE_MODEL_MAX_TOKENS)
- Rate limits / concurrency?
  - Adjust BATCH_SIZE to control number of workers
  - There’s no global API semaphore; limit queue concurrency via BATCH_SIZE

## Notes on Prompts

- The PromptRegistry always returns the GENERAL prompt at runtime
- Discipline-specific prompt modules are present but not used by default
- Modern models perform well with a single comprehensive JSON-focused prompt

## License and Credits

Private project — all rights reserved.

Developer: Collin (BTCElectrician)
- GitHub: https://github.com/BTCElectrician
- Email: Velardecollin@gmail.com
```

<chatName="Updated README with OCR, Chat Completions, JSON repair, and normalization details"/>