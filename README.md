## Indexing workflow (CLI commands)

The pipeline writes all outputs for a job to `~/Desktop/<Job>/processed/` and mirrors that layout to Azure Blob. Use these commands to build and load the Azure AI Search index.

### Prerequisites
- Create and activate the venv (`make setup` then `source venv/bin/activate`).
- Add the following to `.env`:  
  - `AZURE_SEARCH_ENDPOINT=https://<service>.search.windows.net`  
  - `AZURE_SEARCH_API_KEY=<admin_or_query_key>`  
  - `INDEX_NAME=drawings_unified`  
  - `AZURE_SEARCH_API_VERSION=2025-09-01` (optional, defaults to 2024-07-01)
  - `OPENAI_API_KEY=<key>` (optional, for embeddings/vectors)

### Command reference

| Command | When to use | What it does |
|---------|-------------|--------------|
| `ohmni process <Job>` | First step for every job | Runs the full processing pipeline on `~/Desktop/<Job>/`; writes outputs to `~/Desktop/<Job>/processed/` and uploads to blob storage. |
| `ohmni search <Job>` | After processing or schema changes | Regenerates JSONL payloads from `<Job>/processed/` and performs a **full rebuild** of the `drawings_unified` index (sheets + facts + templates). |
| `ohmni search-templates <Job>` | After foremen update room templates | Regenerates `templates.jsonl` from `<Job>/processed/room-data/` and performs an **incremental** template-only upsert (sheets/facts unchanged). |
| `ohmni file <Job/Subfolder/file.pdf>` | Process a single PDF within a job | Processes one PDF (temporary copy) and writes results back to the job's output tree. |
| `ohmni help` | Anytime | Shows usage and lists job folders detected on your Desktop. |
| `make index-set-project PROJECT="<id>"` | Once per job (optional) | Persists the default `project_id` in `.project_id`; subsequent `ohmni search` / `ohmni search-templates` will stamp this value into each document. |
| `make index-check` | After indexing (optional) | Runs `query_playbook.py` to validate the index is responding with sample queries. |

### Example workflow for a new job

```bash
# 1. Process the drawings
ohmni process "20th Monroe"

# 2. (Optional) Set the project ID for this job
make index-set-project PROJECT="20th-monroe"

# 3. Full index rebuild (sheets + facts + templates)
ohmni search "20th Monroe"

# 4. Later, after foremen edit templates
ohmni search-templates "20th Monroe"

# 5. (Optional) Sanity check
make index-check
```

### Checking the index

After running `ohmni search <Job>`, you can verify the index contents:

1. **Azure Portal (Search Explorer)**  
   - Navigate to your Search service → `drawings_unified` → **Search explorer**.
   - Query body: `{ "search": "*", "top": 5, "count": true }`
   - Returns document count and sample results (sheet, fact, or template docs).

2. **REST API (curl/Postman)**  
   ```bash
   curl -X POST \
     "https://aisearchohmni.search.windows.net/indexes/drawings_unified/docs/search?api-version=2025-09-01" \
     -H "Content-Type: application/json" \
     -H "api-key: <admin_or_query_key>" \
     -d '{ "search": "*", "top": 5, "count": true }'
   ```

3. **Document count only**  
   ```bash
   curl -X GET \
     "https://aisearchohmni.search.windows.net/indexes/drawings_unified/docs/\$count?api-version=2025-09-01" \
     -H "api-key: <admin_or_query_key>"
   ```

4. **Filter by document type or project**  
   Add `"$filter"` to your search request:
   - `"$filter": "doc_type eq 'template' and tenant_id eq 'ohmni'"`
   - `"$filter": "project_id eq 'ohmni-elecshuffletest'"`

### Notes
- The index supports semantic search (`semconf`) and hybrid vector search.
- If you want vectors populated, ensure `OPENAI_API_KEY` is set in `.env` or exported in your shell before running the indexing commands.
- The CLI wrappers (`ohmni search`, `ohmni search-templates`) automatically resolve `~/Desktop/<Job>/processed` for you—no need to type the full path.
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
- **Per-panel extraction for electrical panel schedules** - prevents cross-panel text bleeding in multi-panel layouts (2x2, 3x2, 5x5 grids, etc.)
- Room template generation for Architectural floor plans (detected by filename or metadata title)
- AI response caching for 20–30x faster repeated runs
- Performance metrics and slowdown detection
- Clear status files for every outcome

## ⚡ Performance

Ohmni Oracle v3 has been optimized for production workloads through systematic refactoring and code cleanup.

### Current Benchmarks (November 2025 - v3.1.1)

| Metric | Performance | Details |
|--------|-------------|---------|
| **Average Processing Time** | 87 seconds per file | End-to-end: extraction → AI processing → JSON output |
| **API Request Time** | 41 seconds per file | ~88% of total processing time |
| **Tokens per Second** | 69.74 tokens/sec | Average API throughput |
| **Large Schedule Files** | 124-161 seconds | Panel schedules, mechanical schedules |
| **Simple Drawings** | 8-64 seconds | Floor plans, details, equipment elevations |
| **OCR Processing** | 10-16 seconds per page | Triggered only for scanned/low-text drawings |

### Optimization History

**v3.1.1 - November 9, 2025 (Current Stable Baseline):**
- **Production stable** with AI search index integration
- **9 operations** processed across 17 API requests
- **Most used model:** `gpt-4.1-mini` (33,944 total completion tokens)
- **Key metrics:**
  - Total processing: 86.80s average
  - AI Processing: 76.61s average
  - Extraction: 7.17s average
  - JSON Parsing: 1.09s average

**Performance by Drawing Type:**
- Plumbing: 106.89s average (AI processing)
- Electrical: 106.22s average (AI processing)
- Mechanical: 87.97s average (AI processing)
- Architectural: 64.24s average (AI processing)
- Technology: 15.23s average (AI processing)
- Equipment: 8.52s average (AI processing)

**October 28, 2025 Refactoring (v3.1.0):**
- **33.5% faster** end-to-end processing (108s → 72s per file)
- **36.0% faster** API requests (55s → 35s per file)
- **Removed 268 net lines** of dead code and redundancy
- **Key improvements:**
  - Eliminated redundant PDF re-opens for OCR decisions
  - Centralized configuration (reduced repeated `os.getenv()` calls)
  - Simplified model selection logic
  - Removed 646 lines of orphaned code and broken imports

**Real-World Impact:**
- **100 files:** 3 hours → 2 hours (1 hour saved)
- **1,000 files:** 30 hours → 20 hours (10 hours saved)
- Lower API costs from faster, more efficient calls

### Performance Tips

For optimal performance:
1. Use batch processing with the job processor (`BATCH_SIZE`, default 10 concurrent workers)
2. Enable AI caching for repeated documents (`ENABLE_AI_CACHE=true`)
3. Adjust OCR threshold based on drawing quality (`OCR_THRESHOLD=1500`)
4. Use appropriate models (from `.env`):
   - Specifications: `LARGE_DOC_MODEL` (e.g., `gpt-5`) for accuracy
   - Schedules: `SCHEDULE_MODEL` (e.g., `gpt-5`) for balanced accuracy/speed
   - Simple drawings: `TINY_MODEL` (e.g., `gpt-5-nano`) if set; else `DEFAULT_MODEL` (e.g., `gpt-5-mini`)

### Monitoring

Track performance using built-in metrics. Metrics files are saved per run:

```bash
python main.py <input_folder> [output_folder]
# Metrics: <output_folder>/metrics/metrics_<run_id>.json
```

## How It Works

1) Extraction (services/extraction_service.py)
- Uses PyMuPDF for text and optional table extraction per page
- Specialized extractors:
  - ArchitecturalExtractor: highlights room info; prioritizes relevant tables
  - ElectricalExtractor: marks/prefers panel schedules; enriches panel metadata
    - **Panel Clipping**: For panel schedules, automatically detects individual panels (via "Panel:" headers) and extracts each panel's content separately to prevent cross-panel text bleeding
    - Supports multi-panel grids (2x2, 3x2, 5x5, etc.) using row/column midpoint calculation
    - See "Panel Schedule Extraction" section below for details
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
- Saves structured JSON to <output>/<Type>/<drawing_slug>/<file>_structured.json (flattened layout, no nested structured/ folder)
- Architectural floor plans trigger room templates (templates/room_templates.py)
  - Generates templates in shared location: <output>/room-data/<drawing_slug>/<file>_a_rooms_details.json and <file>_e_rooms_details.json
  - Floor plan detection: checks filename for "floor" OR metadata title for "FLOOR"/"LEVEL"
- If unreadable/no content, saved status explains why and processing stops early

## Output and Status Files

- Success: <output>/<Type>/<drawing_slug>/<name>_structured.json (success=true)
- Unreadable: <output>/<Type>/<drawing_slug>/<name>_structured.json (status="skipped_unreadable", success=true)
- Extraction failed: <output>/<Type>/<drawing_slug>/<name>_error.json (status="extraction_failed")
- AI/JSON failed: <output>/<Type>/<drawing_slug>/<name>_error.json (status="ai_processing_failed"), may save a raw response file
- Save failed: <output>/<Type>/<drawing_slug>/<name>_error.json (status="json_save_failed")
- Unexpected: <output>/<Type>/<drawing_slug>/<name>_error.json (status="unexpected_error")
- Metadata manifest: <output>/<Type>/<drawing_slug>/meta.json
- Room templates (Architectural floor plans only): <output>/room-data/<drawing_slug>/<name>_a_rooms_details.json and <name>_e_rooms_details.json
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
  - minimal_panel_clip.py .... Panel detection and clipping for multi-panel schedules
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
git clone https://github.com/BTCElectrician/ohmni-oracle-v3.git
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
AI_CACHE_DIR=.ai_cache

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

Batching and rate limits
```dotenv
# Concurrency and rate control
BATCH_SIZE=10
API_RATE_LIMIT=60
TIME_WINDOW=60
MAX_CONCURRENT_API_CALLS=20

# Model selection guard
MODEL_UPGRADE_THRESHOLD=15000
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

Developer & testing
```bash
# Run tests
make test
make test-coverage

# Linting and formatting
make lint
make format

# Type check + lint
make check
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

## Panel Schedule Extraction

The `ElectricalExtractor` automatically detects and separates individual panels in multi-panel schedules to prevent cross-panel text bleeding (e.g., K1 circuits appearing in L1/H1/K1S).

### How It Works

1. **Panel Detection** (`utils/minimal_panel_clip.py`):
   - Scans PDF for "Panel:" headers (also supports "PANEL", "PNL:", "Board:", etc.)
   - Extracts panel names (e.g., "K1", "H1", "L1", "K1S")
   - Groups panels into rows based on Y-position tolerance (default: 300 points)

2. **Rectangle Calculation**:
   - Calculates bounding rectangles for each panel using row/column midpoints
   - Works for any grid layout: 2x2, 3x2, 5x5, etc.
   - Adds configurable padding (default: 10 points)

3. **Per-Panel Extraction**:
   - Extracts text from each panel's rectangle separately
   - Uses block-based extraction for better structure preservation
   - Wraps each panel with clear markers: `===PANEL {NAME} BEGINS===` / `===PANEL {NAME} ENDS===`

4. **Robustness Features**:
   - Column header detection (CKT, TRIP, POLES, A/B/C phases)
   - Column drift protection (maps values to nearest column header)
   - Odd/even circuit normalization (fixes left/right swaps)

### Testing Different Grid Layouts

Use `test_panel_grid_layouts.py` to analyze and validate panel detection:

```bash
# Analyze any panel schedule PDF
python test_panel_grid_layouts.py path/to/panel_schedule.pdf

# Test specific expected layout (e.g., 3x2 = 6 panels)
python test_panel_grid_layouts.py path/to/panel_schedule.pdf --expect 2x3

# Test with custom Y tolerance
python test_panel_grid_layouts.py path/to/panel_schedule.pdf --tolerance 200
```

The test script will:
- Show detected panel anchors and their positions
- Analyze Y-spacing between rows and suggest optimal `y_tolerance`
- Test different tolerance values to find the best grouping
- Report detected grid layout (e.g., "2x2 grid (4 total panels)")

### Tuning Parameters

If panels aren't being detected correctly, adjust these in `utils/minimal_panel_clip.py`:

- **`y_tolerance`** (default: 300.0): Controls how panels are grouped into rows
  - Too small: Panels in the same row might be split into separate rows
  - Too large: Panels from different rows might be grouped together
  - Rule of thumb: Should be larger than Y-variance within a row, smaller than gap between rows

- **`pad`** (default: 10.0): Padding around panel boundaries
  - Increase if panel content is being cut off
  - Decrease if you're getting too much bleed from adjacent panels

### Files to Modify

- **`utils/minimal_panel_clip.py`**: Core panel detection and clipping logic
  - `_find_panel_anchors()`: Detects "Panel:" headers
  - `_group_rows()`: Groups panels into rows (key for different grids)
  - `panel_rects()`: Calculates panel boundaries
  - `normalize_left_right()`: Fixes odd/even circuit placement

- **`services/extraction_service.py`**: Integration point
  - `ElectricalExtractor._extract_panels_separately()`: Applies clipping to panel schedules

### Common Edge Cases

- **3x2 grid (6 panels)**: Usually works with default tolerance; may need to reduce to 100-200 if panels are tightly spaced
- **5x5 grid (25 panels)**: May need smaller tolerance (50-100) and reduced padding (5-8 points)
- **Single column (1xN)**: Works automatically; no special handling needed
- **Irregular layouts**: The midpoint approach adapts to any arrangement

The system automatically detects panel schedules and applies clipping - no configuration needed for standard layouts.

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
  - There's no global API semaphore; limit queue concurrency via BATCH_SIZE
- Panel schedules showing cross-panel bleeding (circuits from one panel appearing in another)?
  - This should be automatically handled by panel clipping
  - If issues persist, run `python test_panel_grid_layouts.py <pdf_path>` to analyze panel detection
  - Adjust `y_tolerance` in `utils/minimal_panel_clip.py` if panels aren't being grouped correctly
  - Check logs for "Found X panels on page Y" messages to verify detection

## Permissions

- Network: requires outbound access to the OpenAI API.
- Filesystem: writes to `output/` tree and the AI cache directory (`.ai_cache` or `AI_CACHE_DIR`).

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