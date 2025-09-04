# Ohmni Oracle Template - Construction Drawing Processor

<div align="center">
  <img src="assets/github-owl.png" alt="Ohmni Oracle Logo" width="400" height="200">
  <br>
  <em>AI-Powered Construction Drawing Processing & Analysis</em>
</div>

## Overview

The Ohmni Oracle Template is a sophisticated Python-based backend system designed to process PDF construction drawings. It leverages Artificial Intelligence (specifically OpenAI's GPT models) to extract, structure, and normalize information from various types of construction documents, including architectural, electrical, mechanical, and plumbing drawings. The system is built for asynchronous, batch processing and includes features for performance monitoring, AI response caching, and robust error handling.

The primary goal is to convert unstructured data from PDF drawings into structured JSON output, making it usable for downstream analysis, data integration, or other construction technology applications.

## Features

> **💡 Performance Tip**: For optimal performance, ensure `ENABLE_TABLE_EXTRACTION=false` and `ENABLE_AI_CACHE=true` in your `.env` file. See [Performance Configuration](#-performance-configuration) below for details.

### Core Processing
*   **Asynchronous PDF Processing:** Efficiently handles multiple PDF files concurrently using Python's `asyncio`.
*   **Batch Processing:** Processes entire "job sites" (folders of PDFs) with configurable batch sizes and concurrency limits.
*   **Drawing Type Detection:** Automatically identifies the discipline of a drawing (Architectural, Electrical, Mechanical, Plumbing, General, etc.) based on filename conventions.
*   **Content Extraction:**
    *   Utilizes PyMuPDF for robust text and table extraction from PDF documents.
    *   Specialized extractors for different disciplines (Architectural, Electrical, Mechanical, Plumbing) with tailored logic to enhance relevant data (e.g., room information for Architectural, panel details for Electrical).
    *   Handles unreadable or empty PDFs gracefully by generating status files.
*   **AI-Powered Data Extraction:**
    *   Integrates with OpenAI's API (configurable models, e.g., GPT-4o, GPT-4o-mini).
    *   Dynamic model selection based on content length and drawing type (e.g., using more powerful models for large documents or specific schedule types).
    *   Centralized prompt management using a registry system that currently routes all requests to a comprehensive "GENERAL" prompt designed for various construction drawing types.
*   **Data Structuring & Normalization:**
    *   Transforms raw AI responses into structured JSON.
    *   Includes JSON repair capabilities, particularly for complex structures like panel schedules that AI might occasionally malform.
    *   Provides normalization routines to standardize field names and formats for:
        *   Electrical Panel Schedules
        *   Mechanical Equipment Schedules
        *   Plumbing Fixture/Equipment Schedules
    *   Uses Pydantic schemas for validating extracted metadata (e.g., PDF properties, drawing metadata).

### Job & Workflow Management
*   **Prioritized Queue Processing:** Files are queued for processing based on drawing discipline priority (e.g., Architectural first) and then by file size (smallest first within each discipline) to optimize workflow.
*   **Concurrency Control:** Manages the number of concurrent PDF processing tasks and API calls to respect rate limits and system resources.
*   **Worker-Based Architecture:** Employs asynchronous workers to process files from the queue.

### Configuration & Extensibility
*   **Environment-Driven Configuration:** All major settings are controlled via environment variables (loaded from an `.env` file).
*   **Flexible Prompt System:** Uses a registry-based approach with discipline-specific decorators for future extension, though currently defaults to a single general prompt.
*   **Modular Services:** Key functionalities like AI interaction, PDF extraction, data normalization, and storage are encapsulated in separate services.

### Output & Reporting
*   **Structured JSON Output:** Saves processed data as well-organized JSON files, typically one per input PDF.
*   **Status & Error Reporting:** Generates distinct JSON files for successfully processed documents, unreadable documents, or documents that failed during extraction or AI processing.
*   **Room Template Generation:** For architectural floor plans, it can generate `_a_rooms_details.json` and `_e_rooms_details.json` files based on predefined templates and extracted room data.
*   **Comprehensive Logging:**
    *   Structured logging with context.
    *   Logs to both console and timestamped files within the output directory.
    *   Sensitive data in logs (like API keys) is redacted.
*   **Performance Monitoring:**
    *   Tracks duration of key operations (extraction, AI processing, API calls, normalization, etc.).
    *   Saves detailed performance metrics to JSON files for historical analysis and comparison.
    *   Reports average times, slowest operations, and API call statistics.
    *   Includes functionality to detect significant API slowdowns compared to historical performance.

### Utilities
*   **AI Response Caching:** Optionally caches AI responses to disk to avoid redundant API calls for identical inputs, saving costs and time. Cache TTL is configurable.
*   **File System Utilities:** Includes helpers for traversing job folders.
*   **Custom Exceptions:** Defines specific exceptions for better error management.

## Project Structure

```
/
├── config/                 # Application settings and configuration loading
│   ├── settings.py         # Defines and loads all environment variables
├── docs/                   # Documentation and guides
│   ├── PERFORMANCE.md      # Performance analysis and optimization
│   ├── TROUBLESHOOTING.md  # Common issues and solutions
│   └── *.md               # Other technical documentation
├── processing/             # Core processing logic
│   ├── file_processor.py   # Logic for processing a single PDF file
│   └── job_processor.py    # Orchestrates processing of a whole job/folder
├── schemas/                # Pydantic models for data validation
│   └── metadata.py         # Schemas for drawing and extraction metadata
├── services/               # Business logic services
│   ├── ai_service.py       # Handles interaction with AI models (OpenAI)
│   ├── extraction_service.py # PDF content extraction logic
│   ├── normalizers.py      # Data normalization routines
│   └── storage_service.py  # Saving processed data
├── templates/              # Prompt templates and output JSON templates
│   ├── prompts/            # AI prompt definitions for various drawing types
│   │   └── __init__.py     # Empty init file - decorators fire when modules imported
│   ├── base_templates.py   # Base prompt structures
│   ├── prompt_registry.py  # Central registry for managing and retrieving prompts
│   ├── prompt_templates.py # Main interface for accessing prompt templates
│   └── room_templates.py   # Logic for generating room-specific JSON files
├── utils/                  # Utility modules
│   ├── exceptions/         # Custom exception classes
│   ├── ai_cache.py         # AI response caching
│   ├── drawing_utils.py    # Drawing type detection
│   ├── file_utils.py       # File system operations
│   ├── json_utils.py       # JSON parsing and repair utilities
│   ├── logging_utils.py    # Logging setup and structured logging
│   ├── performance_utils.py # Performance tracking and reporting
│   └── security.py         # Security-related utilities (e.g., log sanitization)
├── .env.example            # Example environment file
├── main.py                 # Main entry point of the application
├── requirements.txt        # Python dependencies
├── pyproject.toml          # Project metadata and tool configuration (Ruff)
└── setup.cfg               # Configuration for tools like MyPy
```

### 🗂️ Folder Cheat-Sheet
| Path | What lives here | Typical changes |
|------|-----------------|-----------------|
| config | Runtime settings and environment loaders | Adjusted when adding or deprecating configuration options |
| processing | Job orchestration and file-processing pipelines | Modified when changing workflow logic or concurrency behavior |
| schemas | Pydantic data models for validation | Updated when JSON structures or metadata fields evolve |
| services | Business logic modules for AI, extraction, normalization, storage | Edited when enhancing service capabilities or adding new services |
| templates | Prompt text, room templates, and prompt registry code | Tweaked when refining AI prompts or output templates |
| utils | Shared helper utilities, logging, performance, security | Extended when introducing new common functions or improving tooling |

**Usage**: Add a new row whenever you create or remove a top-level directory. Update the descriptions if a folder's role changes or is relocated.

## Prerequisites

*   Python 3.11 or higher
*   Access to an OpenAI API key

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/BTCElectrician/ohmni-oracle-template.git
    cd ohmni-oracle-template
    ```

2.  **Create and activate a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up environment variables:**
    *   Copy the example environment file:
        ```bash
        cp .env.example .env
        ```
    *   Edit the `.env` file and add your `OPENAI_API_KEY` and any other custom configurations.
        ```dotenv
        OPENAI_API_KEY=your_openai_api_key_here
        # Other settings as needed, see .env.example for all options
        ```
    *   **⚠️ CRITICAL**: Ensure these performance settings are configured:
        ```dotenv
        ENABLE_TABLE_EXTRACTION=false  # Prevents 27x extraction slowdown
        ENABLE_AI_CACHE=true           # Enables 28-38x performance improvement
        AI_CACHE_TTL_HOURS=24         # Cache time-to-live
        ```

## Configuration

The application is configured primarily through environment variables defined in the `.env` file and loaded by `config/settings.py`.

## ⚡ Performance Configuration

### Critical Settings (MUST HAVE in .env)
```bash
# REQUIRED - Prevents 27x slowdown in extraction
ENABLE_TABLE_EXTRACTION=false  

# REQUIRED - Enables caching (28-38x performance difference)
ENABLE_AI_CACHE=true
AI_CACHE_TTL_HOURS=24

# OPTIONAL - Trade speed for potential accuracy
FORCE_MINI_MODEL=false  # true = 29% faster uncached processing
```

### Expected Performance
- **First run (uncached)**: ~3-4 minutes for 9 PDFs
- **Cached runs**: ~11 seconds for 9 PDFs
- **Extraction**: <1 second per PDF (if slow, check ENABLE_TABLE_EXTRACTION)

### Key Environment Variables:

*   `OPENAI_API_KEY` (Required): Your API key for OpenAI.
*   `LOG_LEVEL`: Logging level (e.g., `INFO`, `DEBUG`, `WARNING`). Defaults to `INFO`.
*   `BATCH_SIZE`: Number of PDF files to process concurrently by workers. Defaults to `10`.
*   `MAX_CONCURRENT_API_CALLS`: Maximum number of concurrent calls to the OpenAI API, controlled by a semaphore at the API call site. Defaults to `20`.
*   `API_RATE_LIMIT`: (Currently informational) Intended API calls per minute. Defaults to `60`.
*   `TIME_WINDOW`: (Currently informational) Time window in seconds for the rate limit. Defaults to `60`.
*   `MODEL_UPGRADE_THRESHOLD`: Character count threshold in extracted text above which a more powerful model (GPT-4o) is used instead of the mini model. Defaults to `15000`.
*   `FORCE_MINI_MODEL`: Set to `true` to always use the mini model (GPT-4o-mini), overriding other model selection logic. This setting is reloaded dynamically during runtime. Defaults to `false`.
*   `USE_4O_FOR_SCHEDULES`: Set to `true` to use GPT-4o for schedule drawings (panel, mechanical, etc.) regardless of size (unless `FORCE_MINI_MODEL` is true). Defaults to `true`.
*   `ENABLE_AI_CACHE`: Set to `true` to enable caching of AI responses. Defaults to `false`. **⚠️ CRITICAL: Without this, processing takes 20-30x longer.**
*   `AI_CACHE_DIR`: Directory to store AI cache files. Defaults to `.ai_cache`.
*   `AI_CACHE_TTL_HOURS`: Time-to-live for cache files in hours. Defaults to `24`.
*   `USE_SIMPLIFIED_PROCESSING`: **Deprecated.** This flag is no longer actively used to change processing logic. If set, a warning will be logged.
*   `ENABLE_TABLE_EXTRACTION`: Enable PyMuPDF table detection in extraction. Defaults to `false` for performance. Set to `true` if you need table detection (slower). **⚠️ CRITICAL: Setting this to `true` causes 27x slowdown in extraction.**
*   `DEBUG_MODE`: Set to `true` for additional debug information. Defaults to `false`.

**Note:** Rate limiting is handled by the semaphore `MAX_CONCURRENT_API_CALLS`. The `API_RATE_LIMIT` and `TIME_WINDOW` values are currently informational placeholders.

## Usage

Run the main processing script from the command line:

```bash
python main.py <input_folder> [output_folder]
```

*   `<input_folder>`: Path to the folder containing the PDF drawings to process.
*   `[output_folder]` (Optional): Path to the folder where processed files, logs, and metrics will be saved. If not provided, it defaults to `<input_folder>/output`.

**Example:**
```bash
python main.py /path/to/my/drawings /path/to/my/output
```

The script will:
1.  Traverse the `<input_folder>` to find all PDF files.
2.  Queue them for processing based on type and size.
3.  Process each PDF: extract content, send to AI, parse response, normalize data.
4.  Save structured JSON output, status files, and (if applicable) room templates to the `<output_folder>`.
5.  Log progress and errors to the console and to log files in `<output_folder>/logs/`.
6.  Generate and save performance metrics in `<output_folder>/metrics/`.

## How It Works (Processing Pipeline)

1.  **Initialization (`main.py`):**
    *   Sets up logging.
    *   Initializes the OpenAI client.
    *   Records application settings.

2.  **Job Orchestration (`processing/job_processor.py`):**
    *   Traverses the input job folder to find all PDF files (`utils/file_utils.py`).
    *   Determines the drawing type for each PDF (`utils/drawing_utils.py`, `utils/constants.py`).
    *   Prioritizes files: Architectural > Electrical > Mechanical > Plumbing > General. Within each type, smaller files are processed first.
    *   Puts PDF files into an asynchronous queue.
    *   Manages a pool of asynchronous workers (`process_worker`).
    *   Uses a semaphore to limit concurrent API calls (`MAX_CONCURRENT_API_CALLS`).

3.  **File Processing (`processing/file_processor.py` - `process_pdf_async` for each file):**
    *   **Output Path Determination:** Sets up output paths for structured data, errors, and raw AI responses.
    *   **Content Extraction (`services/extraction_service.py`):**
        *   Selects an extractor based on `drawing_type` (e.g., `ArchitecturalExtractor`, `ElectricalExtractor`, or `PyMuPdfExtractor` as default).
        *   Extracts raw text and tables from the PDF. Discipline-specific extractors may perform enhancements (e.g., highlighting panel schedule sections).
        *   Checks if the extracted content is meaningful (above a minimum length). If not, a `skipped_unreadable` status file is created.
        *   If extraction fails, an `extraction_failed` status file is created.
    *   **Subtype Detection (`utils/drawing_utils.py`):** Further refines drawing type/subtype based on filename.
    *   **AI Processing (`services/ai_service.py` - `process_drawing`):**
        *   Checks AI cache (`utils/ai_cache.py`) if enabled. If a cached response exists and is valid, it's used.
        *   Selects the AI model (GPT-4o-mini or GPT-4o) based on `FORCE_MINI_MODEL`, content length (`MODEL_UPGRADE_THRESHOLD`), and `USE_4O_FOR_SCHEDULES`.
        *   Retrieves the "GENERAL" prompt from the `PromptRegistry` (`templates/prompt_registry.py`).
        *   Makes an API call to OpenAI with the extracted content and the prompt. Includes retry logic.
        *   If caching is enabled, the AI response is saved to the cache.
    *   **JSON Parsing (`utils/json_utils.py` - `parse_json_safely`):**
        *   Attempts to parse the AI's string response into a JSON object.
        *   If parsing fails and the drawing type is "mechanical" or "panel" related, it may attempt to repair the JSON string (`repair_panel_json`) before retrying parsing.
        *   If AI processing or JSON parsing ultimately fails, an `ai_processing_failed` status file is created (potentially with the raw AI response).
    *   **Metadata Validation (`schemas/metadata.py`):** Validates `DRAWING_METADATA` if present in the parsed JSON.
    *   **Data Normalization (`services/normalizers.py`):**
        *   If the parsed JSON corresponds to specific types (e.g., panel schedules, mechanical schedules, plumbing schedules), normalization functions are applied to standardize field names and data formats.
    *   **Save Output (`services/storage_service.py`):**
        *   Saves the structured (and normalized) JSON data to a `_structured.json` file.
        *   Uses `aiofiles` for asynchronous file operations.
        *   Handles `datetime` objects correctly during JSON serialization.
    *   **Room Template Generation (`templates/room_templates.py`):**
        *   If the drawing is an Architectural floor plan, it processes the structured JSON to generate `_a_rooms_details.json` and `_e_rooms_details.json` files.

4.  **Completion (`main.py`):**
    *   Logs total processing time.
    *   Generates and logs a performance report (`utils/performance_utils.py`).
    *   Saves performance metrics to a file.
    *   Checks for API performance degradation against historical data.

## Output

All output files are saved in the specified `output_folder`.

*   **Structured Data:**
    *   Location: `<output_folder>/<DrawingType>/<original_filename_base>_structured.json`
    *   Content: The structured JSON data extracted and processed from the PDF.
*   **Status/Error Files:**
    *   If a PDF is unreadable: `<output_folder>/<DrawingType>/<original_filename_base>_structured.json` (with status "skipped_unreadable").
    *   If extraction fails: `<output_folder>/<DrawingType>/<original_filename_base>_error.json` (with status "extraction_failed").
    *   If AI processing or JSON parsing fails: `<output_folder>/<DrawingType>/<original_filename_base>_error.json` (with status "ai_processing_failed").
    *   If JSON parsing fails but a raw AI response was received: `<output_folder>/<DrawingType>/<original_filename_base>_raw_response_error.txt`
    *   If saving the final JSON fails: `<output_folder>/<DrawingType>/<original_filename_base>_error.json` (with status "json_save_failed").
    *   For unexpected errors: `<output_folder>/<DrawingType>/<original_filename_base>_error.json` (with status "unexpected_error").
*   **Room Templates (for Architectural floor plans):**
    *   Location: `<output_folder>/Architectural/`
    *   Files:
        *   `<original_filename_base>_a_rooms_details.json`
        *   `<original_filename_base>_e_rooms_details.json`
*   **Log Files:**
    *   Location: `<output_folder>/logs/`
    *   File: `process_log_<timestamp>.txt`
    *   Content: Detailed logs of the application's execution.
*   **Performance Metrics:**
    *   Location: `<output_folder>/metrics/`
    *   File: `metrics_<timestamp>.json`
    *   Content: Performance statistics for the processing run.

## Core Components

*   **`main.py`**: Orchestrates the entire application flow.
*   **`config/settings.py`**: Manages application configuration via environment variables.
*   **`processing/job_processor.py`**: Handles the processing of an entire batch of PDF files, managing queues and workers.
*   **`processing/file_processor.py`**: Contains the logic for processing a single PDF file through extraction, AI, and normalization.
*   **`services/ai_service.py`**: Interfaces with the OpenAI API, handles model selection, prompt retrieval, and API call retries.
*   **`services/extraction_service.py`**: Provides PDF content extraction capabilities, with specialized extractors for different drawing disciplines.
*   **`services/normalizers.py`**: Standardizes the structure and field names of the extracted JSON data for specific schedule types.
*   **`services/storage_service.py`**: Manages asynchronous saving of output files (JSON, text).
*   **`templates/prompt_registry.py`**: A central registry for AI prompts. Currently configured to route all requests to a single, comprehensive "GENERAL" prompt regardless of drawing type.
*   **`templates/prompt_templates.py`**: Main interface for accessing prompt templates. Imports discipline-specific prompt modules to register them with the registry.
*   **`templates/room_templates.py`**: Logic for generating structured room data JSON files from architectural drawing outputs.
*   **`utils/performance_utils.py`**: A robust module for tracking, reporting, and saving performance metrics of various operations.
*   **`utils/ai_cache.py`**: Implements caching for AI API responses to reduce costs and improve speed on repeated inputs.
*   **`utils/logging_utils.py`**: Sets up and provides structured logging capabilities.
*   **`utils/json_utils.py`**: Includes utilities for safe JSON parsing and repairing malformed JSON, especially from AI outputs.

## Key Architectural Decisions

*   **Single General Prompt:** The system currently relies on a single, highly detailed "GENERAL" prompt (`templates/prompt_registry.py`) that routes all drawing types to the same comprehensive prompt. This decision is based on the observation that modern AI models (like GPT-4o) can effectively handle various construction drawing types with a well-crafted general prompt, simplifying prompt maintenance. The registry system supports discipline-specific decorators for future extension, but they are not currently used at runtime.
*   **Asynchronous Operations:** The extensive use of `asyncio` allows for high I/O-bound concurrency, making the system efficient for processing many files, especially when waiting for API responses or file operations.
*   **Discipline-Specific Enhancements in Extractors:** While the AI prompt is general, the PDF extraction phase (`services/extraction_service.py`) employs discipline-specific extractor classes. These classes can apply pre-processing or targeted extraction techniques to better prepare the data for the general AI prompt (e.g., `ElectricalExtractor` might add hints about panel schedule structures).
*   **Environment-Driven Configuration:** Centralizing configuration in `.env` files and `config/settings.py` makes the application adaptable to different environments and setups without code changes.
*   **Detailed Performance Tracking:** The `utils/performance_utils.py` module provides deep insights into the performance of different stages of the pipeline, which is crucial for optimization and identifying bottlenecks.

## Specialized Prompts vs. General Prompt (Performance Trade-off)

We maintain discipline- and subtype-specific prompts under `templates/prompts/*.py` (Architectural, Electrical, Mechanical, Plumbing). Through testing, specialized prompts increased token usage and slowed uncached runs with little accuracy benefit on most drawings.

Therefore, at runtime we default to a single comprehensive "GENERAL" prompt for all drawings:
- **Faster cold runs** (fewer prompt tokens)
- **Simpler to maintain**
- **Works well with modern models** (JSON mode + robust extraction/normalization)

**What's enabled today:**
- `PromptRegistry.get(...)` always returns the GENERAL prompt
- Specialized prompts are present in code but are not used at runtime by default

**When to consider specialized prompts:**
- Debugging very tricky sheets where the GENERAL prompt underperforms
- Targeted use in a failure-retry path (e.g., only if JSON parsing fails)
- Small documents where prompt token overhead is negligible

**How to enable (optional):**

1. Ensure prompt modules are imported so their decorators register prompts:
```python
# templates/prompts/__init__.py
from .architectural import *  # noqa
from .electrical import *     # noqa
from .mechanical import *     # noqa
from .plumbing import *       # noqa
from .metadata import *       # noqa
```

2. Add an environment flag:
```dotenv
# .env
USE_SPECIALIZED_PROMPTS=false     # default and recommended
# Optional retry strategy: only use specialized prompts on parse failure (not enabled by default)
RETRY_WITH_SPECIALIZED_PROMPTS=false
```

3. Update the registry to honor the flag:
```python
# templates/prompt_registry.py
import os
# ... keep the rest of the file as-is ...

def get(self, drawing_type: str, subtype: Optional[str] = None) -> str:
    use_specialized = os.getenv("USE_SPECIALIZED_PROMPTS", "false").lower() == "true"
    if use_specialized:
        key = f"{drawing_type}_{subtype}".upper() if subtype else (drawing_type or "").upper()
        if key in self._prompts:
            return self._prompts[key]
        if drawing_type and drawing_type.upper() in self._prompts:
            return self._prompts[drawing_type.upper()]
    # Fallback (and default): single comprehensive prompt
    return self._prompts.get("GENERAL", "")
```

**Note:** Enabling specialized prompts increases token usage and cost; the runtime penalty is largely mitigated on subsequent runs if `ENABLE_AI_CACHE=true`.

## Troubleshooting

*   **Check Log Files:** The primary source of information for diagnosing issues is the log files located in `<output_folder>/logs/`. Set `LOG_LEVEL=DEBUG` in your `.env` file for more verbose logging.
*   **Examine Error Files:** If a PDF fails to process, an `_error.json` file will be created in the output directory for that file, containing details about the failure.
*   **OpenAI API Key:** Ensure your `OPENAI_API_KEY` is correctly set in the `.env` file and has sufficient quota.
*   **File Permissions:** Verify that the application has read permissions for the input folder and write permissions for the output folder.
*   **Dependencies:** Ensure all dependencies in `requirements.txt` are correctly installed in your virtual environment.

### Performance Issues

For detailed performance troubleshooting and optimization, see:
*   **[Performance Documentation](docs/PERFORMANCE.md)** - Comprehensive performance analysis, baselines, and optimization strategies
*   **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** - Common issues and their solutions

**Quick Performance Fixes:**
1. **Extraction slow?** Set `ENABLE_TABLE_EXTRACTION=false` in `.env`
2. **Processing slow?** Set `ENABLE_AI_CACHE=true` in `.env`
3. **First run always slow?** This is normal - subsequent runs will be 20-30x faster
