Here’s a lean-up pass with concrete, low-risk edits and a punch‑list of additional cleanups to consider.

High-impact issues found
- Missing function: templates.prompt_registry.verify_registry is imported in main.py but not defined. This will crash at startup.
- OCR double work: run_ocr_if_needed re-opens the PDF and re-runs the OCR decision even when you already computed page_count and should_ocr in file_processor._step_extract_content. This wastes time and I/O.
- Redundant env lookups: ai_service.optimize_model_parameters re-reads temps from the environment even though they’re already in config.settings.
- Redundant timeout definition: RESPONSES_TIMEOUT_SECONDS defined in ai_service and returned as a string in settings.get_all_settings. Centralize in settings and import where needed.
- Progress bar mismatch: job_processor uses total=len(pdf_files) even though duplicates are deduplicated; use len(enqueued_files).
- Dead or unused code:
  - AiResponse class in services/ai_service.py appears unused.
  - extraction_service._extract_project_name_from_titleblock is never called.
  - File-processing status helper stored timestamp uses asyncio’s monotonic event loop time; better to use epoch seconds for logs.
  - Minor unused imports (e.g., uuid, Union, datetime in file_processor).

Proposed safe edits
These are scoped, low-risk changes that fix bugs and remove redundancy without changing behavior.

1) Add verify_registry and centralize the prompt registry check
File: templates/prompt_registry.py
```py
# ... existing imports and code above ...

def get_registry() -> PromptRegistry:
    """Get the global prompt registry instance."""
    return _registry

def verify_registry() -> bool:
    """
    Verify required prompt keys are present.
    Returns True if all required prompts are available, else False.
    """
    try:
        registry = get_registry()
        required = ["GENERAL", "METADATA_REPAIR"]
        missing = [k for k in required if not registry.contains(k)]
        if missing:
            logger.warning(f"Prompt registry missing keys: {missing}")
            return False
        return True
    except Exception as e:
        logger.warning(f"Failed to verify prompt registry: {e}")
        return False
```

2) Centralize RESPONSES_TIMEOUT_SECONDS in settings and use it in ai_service
File: config/settings.py
```py
# ... existing settings above ...

# Maximum completion tokens supported by the specific model version being used
ACTUAL_MODEL_MAX_COMPLETION_TOKENS = int(os.getenv("ACTUAL_MODEL_MAX_COMPLETION_TOKENS", "32000"))

# API timeouts
RESPONSES_TIMEOUT_SECONDS = int(os.getenv("RESPONSES_TIMEOUT_SECONDS", "200"))

# Threshold character count for using GPT-4o instead of GPT-4o-mini
MODEL_UPGRADE_THRESHOLD = int(os.getenv("MODEL_UPGRADE_THRESHOLD", "15000"))

# ... later in get_all_settings():
def get_all_settings() -> Dict[str, Any]:
    return {
        # ...
        "ACTUAL_MODEL_MAX_COMPLETION_TOKENS": ACTUAL_MODEL_MAX_COMPLETION_TOKENS,
        "RESPONSES_TIMEOUT_SECONDS": RESPONSES_TIMEOUT_SECONDS,
        # OCR Configuration visibility
        # ...
    }
```

File: services/ai_service.py
```py
# ... existing imports ...
from config.settings import (
    get_force_mini_model,
    MODEL_UPGRADE_THRESHOLD,
    DEFAULT_MODEL, LARGE_DOC_MODEL, SCHEDULE_MODEL,
    TINY_MODEL, TINY_MODEL_THRESHOLD,
    DEFAULT_MODEL_TEMP, DEFAULT_MODEL_MAX_TOKENS,
    LARGE_MODEL_TEMP, LARGE_MODEL_MAX_TOKENS,
    TINY_MODEL_TEMP, TINY_MODEL_MAX_TOKENS,
    ACTUAL_MODEL_MAX_COMPLETION_TOKENS,
    NANO_CHAR_THRESHOLD,
    MINI_CHAR_THRESHOLD,
    RESPONSES_TIMEOUT_SECONDS,  # NEW: import centralized timeout
)
# remove: RESPONSES_TIMEOUT_SECONDS = int(os.getenv("RESPONSES_TIMEOUT_SECONDS", "200"))
```

3) Remove redundant env fetching in optimize_model_parameters and split schedule/spec detection to avoid double scans
File: services/ai_service.py
```py
# Add helpers near _is_schedule_or_spec
def _is_schedule_doc(drawing_type: Optional[str], pdf_path: Optional[str]) -> bool:
    dt = (drawing_type or "").lower()
    name = os.path.basename(pdf_path or "").lower()
    return ("panel" in dt or "schedule" in dt) or ("panel" in name or "schedule" in name)

def _is_spec_doc(drawing_type: Optional[str], pdf_path: Optional[str]) -> bool:
    dt = (drawing_type or "").lower()
    name = os.path.basename(pdf_path or "").lower()
    return ("spec" in dt or "specification" in dt) or ("spec" in name or "specification" in name)

def optimize_model_parameters(
    drawing_type: str, raw_content: str, pdf_path: str
) -> Dict[str, Any]:
    content_length = len(raw_content) if raw_content else 0
    is_schedule = _is_schedule_doc(drawing_type, pdf_path)
    force_mini = get_force_mini_model()

    if is_schedule:
        model = SCHEDULE_MODEL
        temperature = LARGE_MODEL_TEMP
        max_tokens = min(LARGE_MODEL_MAX_TOKENS, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        logger.info(f"Using schedule model for {content_length} char document")
    elif force_mini:
        model = DEFAULT_MODEL
        temperature = DEFAULT_MODEL_TEMP
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Force-mini override active ({content_length} chars)")
    elif content_length < NANO_CHAR_THRESHOLD:
        model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
        temperature = TINY_MODEL_TEMP if TINY_MODEL else DEFAULT_MODEL_TEMP
        max_tokens = TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using nano model for simple extraction ({content_length} chars)")
    elif content_length < MINI_CHAR_THRESHOLD:
        model = DEFAULT_MODEL
        temperature = DEFAULT_MODEL_TEMP
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using mini model for structured extraction ({content_length} chars)")
    else:
        model = LARGE_DOC_MODEL
        temperature = LARGE_MODEL_TEMP
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for complex extraction ({content_length} chars)")

    # spec doc limit
    if _is_spec_doc(drawing_type, pdf_path):
        spec_max_tokens = int(os.getenv("SPEC_MAX_TOKENS", "16384"))
        max_tokens = min(max_tokens, spec_max_tokens)
        logger.info(f"Specification document detected - limiting to {max_tokens} tokens")
    elif model in [LARGE_DOC_MODEL, SCHEDULE_MODEL]:
        if content_length > 35000:
            max_tokens = min(12000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
            logger.info(f"Capping max_tokens to {max_tokens} for very large document")
        elif content_length > 25000:
            max_tokens = min(14000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
            logger.info(f"Setting max_tokens to {max_tokens} for large document")
        elif content_length > 15000:
            max_tokens = min(15000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)

    max_tokens = min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
    logger.info(f"Model: {model}, Max tokens: {max_tokens}, Input: {content_length} chars")
    return {"model": model, "temperature": float(temperature), "max_tokens": int(max_tokens)}
```

4) Avoid re-opening PDFs and re-computing the OCR decision
File: services/ocr_service.py
```py
# signature: add optional page_count and assume_ocr_needed
async def run_ocr_if_needed(
    client: AsyncOpenAI,
    pdf_path: str,
    current_text: str,
    threshold: int = 1500,
    max_pages: int = 2,
    page_count: int | None = None,
    assume_ocr_needed: bool | None = None,
) -> str:
    # determine page_count once if not provided
    if page_count is None:
        try:
            with fitz.open(pdf_path) as doc:
                page_count = len(doc)
        except Exception as e:
            logger.warning(f"Could not read PDF for OCR decision: {e}")
            return ""

    # honor prior decision when provided
    if assume_ocr_needed is not None:
        should_ocr = assume_ocr_needed
        reason = "Pre-decided by caller" if assume_ocr_needed else "Pre-decided skip by caller"
    else:
        should_ocr, reason = should_perform_ocr(
            extracted_text=current_text,
            pdf_path=pdf_path,
            page_count=page_count,
            ocr_enabled=True,
            ocr_threshold=threshold
        )

    if not should_ocr:
        logger.info(f"OCR SKIPPED: {reason}")
        return ""

    logger.info(f"🎯 OCR TRIGGERED: {reason}")
    # ... rest of function unchanged ...
```

File: processing/file_processor.py
```py
# imports: remove unused
# from datetime import datetime  # remove
# from typing import ..., Union  # remove Union import if unused
# Add: ensure time is imported (already at top)

async def _save_status_file(...):
    status_data = {
        "original_file": original_pdf_path,
        "status": status,
        "message": message,
        "timestamp": time.time(),  # use epoch seconds instead of event loop time
    }
    # ...

async def _step_extract_content(self) -> bool:
    # ... existing code computes page_count and should_ocr ...
    if OCR_ENABLED:
        try:
            from services.ocr_service import run_ocr_if_needed
            ocr_start_time = time.time()
            ocr_text = await run_ocr_if_needed(
                client=self.client,
                pdf_path=self.pdf_path,
                current_text=extraction_result.raw_text,
                threshold=OCR_THRESHOLD,
                max_pages=OCR_MAX_PAGES,
                page_count=page_count,                 # reuse computed page_count
                assume_ocr_needed=should_ocr           # honor prior decision
            )
            # ... rest unchanged ...
```

5) Fix total for overall progress bar and remove stale doc text
File: processing/job_processor.py
```py
async def process_worker(...):
    """
    Enhanced worker process that takes jobs from the queue and processes them.
    Uses per-file timeouts and records queue wait times.
    """
    # docstring updated; removed mention of semaphore
    # ...

async def process_job_site_async(job_folder: str, output_folder: str, client) -> None:
    # ...
    with tqdm(total=len(enqueued_files), desc="Overall Progress") as overall_pbar:
        original_queue_size = queue.qsize()
        # ... rest unchanged ...
```

6) Remove unused code in ai_service
File: services/ai_service.py
```py
# remove unused imports:
# import uuid
# from typing import TypeVar, Generic
# remove AiResponse class entirely

# Delete:
# T = TypeVar("T")
# class AiResponse(Generic[T]): ...
```

Optional but recommended cleanups
- Use MAX_CONCURRENT_API_CALLS: You define it in settings but never use it. The simplest integration is a global asyncio.Semaphore in ai_service.make_chat_completion_request and in services/ocr_service OCR calls. That gives you a hard cap on concurrent LLM calls without restructuring workers.
- Consider deferring the OPENAI_API_KEY check in settings.py. Raising at import-time makes testing and introspection brittle. A lazy check where the key is needed (e.g., in main or when constructing AsyncOpenAI) is friendlier.
- Remove unused constants and code if tests don’t rely on them:
  - MODEL_UPGRADE_THRESHOLD is defined but unused.
  - utils/constants.DRAWING_TYPES dict is unused (get_drawing_type uses drawing_utils).
  - Extraction: _extract_project_name_from_titleblock in services/extraction_service isn’t referenced.
  - StructuredLogger in utils/logging_utils isn’t used anywhere; either remove or wire it in.
- Unify prompt logic: PromptRegistry.get always returns GENERAL, but ai_service still logs drawing_type/subtype specific keys. If you intend to keep a single prompt, simplify the logs and remove unused enums in templates/prompt_types.py. If you want per-type prompts later, wire registry.get to actually use keys and store them in PromptRegistry.
- JSON parse twice: process_drawing already json.loads the model output; file_processor then calls parse_json_safely on the returned string again. If possible, return a dict from process_drawing to eliminate a second parse step and reduce failure modes.
- OCR defaults comment drift: ocr_service says “3x3 @ 600 DPI” but GRID defaults to 1 and DPI to 300 in code. Align the commentary or defaults to avoid confusion.
- Timestamp consistency: use epoch seconds everywhere you persist a timestamp (you already adjusted _save_status_file in this patch).
- Tests: Some tests may refer to prompt-related behavior. If you flip PromptRegistry.get behavior or remove AiResponse, verify tests in tests/test_prompt_templates.py and tests/test_ai_service.py.

Why these edits help
- Prevents a hard crash at startup (verify_registry).
- Cuts unnecessary PyMuPDF open/close operations and redundant OCR decision logic.
- Ensures consistent configuration for API timeouts across modules.
- Removes code that isn’t exercised and potential confusion sources.
- Fixes progress tracking so users see accurate progress.

If you’d like, I can follow up with:
- A small semaphore-based concurrency cap for API calls.
- A pass to convert process_drawing to return a dict directly and trim a parse pass.
- Removing additional dead code tied to prompts and types, if tests allow.

<chatName="Repo lean-up: fixes + redundancy cuts + OCR/timeout centralization"/>