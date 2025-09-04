# PDF Processing Performance Fix - Product Requirements Document

## Executive Summary
Fix the 2.6x performance degradation in PDF processing by correcting semaphore placement and making table extraction optional. This will restore extraction times from 13.78s to ~7.76s per PDF and parallel efficiency from 3.8x to 5.5x.

## Problem Statement
- **Current State**: PDF processing takes 32.82 seconds for 9 PDFs
- **Target State**: Restore to May 2025 baseline of ~12-13 seconds for 9 PDFs
- **Root Causes**:
  1. Semaphore incorrectly limits entire pipeline instead of just API calls
  2. Expensive table extraction added to every PDF page

## Implementation Tasks

### Task 1: Fix Semaphore Placement in AI Service
**File**: `services/ai_service.py`

#### Step 1.1: Add imports and semaphore helper
At the top of the file, update imports:
```python
# Add asyncio to existing imports
import asyncio

# Update the config.settings import to include MAX_CONCURRENT_API_CALLS
from config.settings import (
    get_force_mini_model,
    MODEL_UPGRADE_THRESHOLD,
    USE_4O_FOR_SCHEDULES,
    DEFAULT_MODEL, LARGE_DOC_MODEL, SCHEDULE_MODEL,
    TINY_MODEL, TINY_MODEL_THRESHOLD,
    DEFAULT_MODEL_TEMP, DEFAULT_MODEL_MAX_TOKENS,
    LARGE_MODEL_TEMP, LARGE_MODEL_MAX_TOKENS,
    TINY_MODEL_TEMP, TINY_MODEL_MAX_TOKENS,
    ACTUAL_MODEL_MAX_COMPLETION_TOKENS,
    MAX_CONCURRENT_API_CALLS,  # ADD THIS LINE
)
```

#### Step 1.2: Add semaphore management
After the line `logger = logging.getLogger(__name__)`, add:
```python
# Global API semaphore for rate limiting
_api_semaphore: Optional[asyncio.Semaphore] = None

def get_api_semaphore() -> asyncio.Semaphore:
    """Get or create the global API semaphore."""
    global _api_semaphore
    if _api_semaphore is None:
        _api_semaphore = asyncio.Semaphore(MAX_CONCURRENT_API_CALLS or 20)
        logger.info(f"API semaphore created with limit={MAX_CONCURRENT_API_CALLS}")
    return _api_semaphore
```

#### Step 1.3: Wrap only the OpenAI call
In the `make_openai_request` function, find this block:
```python
start_time = time.time()
try:
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
    )
```

Replace it with:
```python
start_time = time.time()
try:
    async with get_api_semaphore():  # Add this line
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
```

### Task 2: Remove Pipeline-Wide Semaphore
**File**: `processing/job_processor.py`

#### Step 2.1: Update imports
Find this line:
```python
from config.settings import BATCH_SIZE, MAX_CONCURRENT_API_CALLS
```

Replace with:
```python
from config.settings import BATCH_SIZE
```

#### Step 2.2: Remove semaphore creation
Find and DELETE these lines (around line 86-88):
```python
# Create a semaphore to limit concurrent API calls
semaphore = asyncio.Semaphore(MAX_CONCURRENT_API_CALLS)
logger.info(f"Using semaphore to limit concurrent API calls to {MAX_CONCURRENT_API_CALLS}")
```

#### Step 2.3: Update process_worker function signature
Find the `process_worker` function definition:
```python
async def process_worker(
    queue: asyncio.Queue,
    client,
    output_folder: str,
    templates_created: Dict[str, bool],
    results: List[Dict[str, Any]],
    worker_id: int,
    semaphore: asyncio.Semaphore,  # REMOVE THIS LINE
) -> None:
```

Remove the `semaphore` parameter.

#### Step 2.4: Remove semaphore usage in worker
Inside `process_worker`, find this block:
```python
async with semaphore:
    logger.info(f"Worker {worker_id} acquired semaphore for {os.path.basename(pdf_file)}")
    result = await asyncio.wait_for(
        process_pdf_async(...),
        timeout=600,
    )
```

Replace with:
```python
# No semaphore needed here - extraction can run in parallel
result = await asyncio.wait_for(
    process_pdf_async(
        pdf_path=pdf_file,
        client=client,
        output_folder=output_folder,
        drawing_type=drawing_type,
        templates_created=templates_created,
    ),
    timeout=600,
)
```

#### Step 2.5: Update worker creation
Find the worker creation loop (around line 134):
```python
for i in range(max_workers):
    worker = asyncio.create_task(
        process_worker(
            queue,
            client,
            output_folder,
            templates_created,
            all_results,
            i + 1,
            semaphore,  # REMOVE THIS LINE
        )
    )
```

Remove the `semaphore` argument.

### Task 3: Make Table Extraction Optional
**File**: `services/extraction_service.py`

#### Step 3.1: Add import for environment variable
At the top of the file, add to imports:
```python
import os
```

#### Step 3.2: Make table extraction conditional
In the `_extract_content` method of `PyMuPdfExtractor`, find the section that processes tables (around line 141-165).

Replace the entire table extraction block with:
```python
# Check if table extraction is enabled
enable_table_extraction = os.getenv("ENABLE_TABLE_EXTRACTION", "true").lower() == "true"
table_notice_logged = False

# Process each page individually to avoid reference issues
for i, page in enumerate(doc):
    # Add page header
    page_text = f"PAGE {i+1}:\n"

    # Try block-based extraction first
    try:
        blocks = page.get_text("blocks")
        for block in blocks:
            if block[6] == 0:  # Text block (type 0)
                page_text += block[4] + "\n"
    except Exception as e:
        self.logger.warning(
            f"Block extraction error on page {i+1} of {os.path.basename(file_path)}: {str(e)}"
        )
        # Fall back to regular text extraction
        try:
            page_text += page.get_text() + "\n\n"
        except Exception as e2:
            self.logger.warning(
                f"Error extracting text from page {i+1}: {str(e2)}"
            )
            page_text += "[Error extracting text from this page]\n\n"

    # Add to overall text
    raw_text += page_text

    # Extract tables safely (ONLY if enabled)
    if enable_table_extraction:
        try:
            # Only attempt table extraction if page has text
            page_text = page.get_text("text")
            if page_text and page_text.strip():
                try:
                    table_finder = page.find_tables()
                    if table_finder and hasattr(table_finder, "tables"):
                        for j, table in enumerate(table_finder.tables or []):
                            try:
                                if hasattr(table, 'to_markdown'):
                                    table_markdown = table.to_markdown()
                                    if table_markdown:
                                        tables.append({
                                            "page": i + 1,
                                            "table_index": j,
                                            "content": table_markdown,
                                        })
                            except Exception as e:
                                self.logger.debug(f"Skipping table {j} on page {i+1}: {str(e)}")
                except AttributeError:
                    self.logger.debug(f"Page {i+1} doesn't support table extraction")
        except Exception as e:
            self.logger.debug(f"Table extraction skipped for page {i+1}: {str(e)}")
    else:
        if not table_notice_logged:
            self.logger.info("ENABLE_TABLE_EXTRACTION=false; skipping PyMuPDF table detection for speed")
            table_notice_logged = True
```

### Task 4: Update Environment Configuration
**File**: `.env`

Add this line:
```
ENABLE_TABLE_EXTRACTION=false
```

### Task 5: Update Example Environment File
**File**: `.env.example`

Add this line in the configuration section:
```
# PDF Processing Performance
ENABLE_TABLE_EXTRACTION=false  # Set to true if you need table detection (slower)
```

## Testing Instructions

### Step 1: Apply all changes above
Run the changes in the order listed.

### Step 2: Run performance test
```bash
python main.py /Users/collin/Desktop/ElecShuffleTest
```

### Step 3: Verify improvements
Check the metrics file for:
1. **Extraction average**: Should drop from 13.78s to ~7-8s
2. **Total processing time**: Should drop from 32.82s to ~12-15s
3. **Parallel efficiency**: Should improve from 3.8x to ~5.5x

### Step 4: Compare metrics
```bash
# Compare new metrics with previous
ls -la output/metrics/
# Open the newest metrics file and verify extraction times
```

## Success Criteria
- [ ] Extraction average time: < 8.5 seconds
- [ ] Total processing time for 9 PDFs: < 15 seconds  
- [ ] Parallel speedup: > 5x
- [ ] No errors in processing
- [ ] All 9 PDFs successfully processed

## Rollback Plan
If issues occur:
1. Set `ENABLE_TABLE_EXTRACTION=true` in `.env` to restore table extraction
2. Revert the semaphore changes if API rate limits are hit

## Notes
- The semaphore fix allows full parallelism for extraction while still limiting API calls
- Disabling table extraction removes expensive operations that were added after May 2025
- These changes restore the original May 2025 performance characteristics
- Table extraction can be re-enabled if needed for specific use cases