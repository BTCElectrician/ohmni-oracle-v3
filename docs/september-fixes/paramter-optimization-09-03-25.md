<artifact identifier="gpt5-size-bucket-implementation" type="text/markdown" title="GPT-5 Size Bucket Implementation Instructions">
# GPT-5 Size Bucket Model Selection Implementation

## Instructions for Cursor Agent

Make the following surgical changes to implement the new size-based model selection logic with proper safety overrides.

---

## Step 1: Update config/settings.py

**File:** `config/settings.py`

**Action:** Add the following lines after the existing model configuration constants (around line 25-30, after `TINY_MODEL_THRESHOLD`):

```python
# Model Size Thresholds for tiered selection
NANO_CHAR_THRESHOLD = int(os.getenv("NANO_CHAR_THRESHOLD", "3000"))
MINI_CHAR_THRESHOLD = int(os.getenv("MINI_CHAR_THRESHOLD", "15000"))
```

---

## Step 2: Update ai_service.py - Add imports

**File:** `services/ai_service.py`

**Action:** Update the imports from config.settings (around line 20) to include the new thresholds:

**Find this block:**
```python
from config.settings import (
    get_force_mini_model,
    MODEL_UPGRADE_THRESHOLD,
    USE_4O_FOR_SCHEDULES,
    DEFAULT_MODEL, LARGE_DOC_MODEL, SCHEDULE_MODEL,
    TINY_MODEL, TINY_MODEL_THRESHOLD,
    DEFAULT_MODEL_TEMP, DEFAULT_MODEL_MAX_TOKENS,
    LARGE_MODEL_TEMP, LARGE_MODEL_MAX_TOKENS,
    TINY_MODEL_TEMP, TINY_MODEL_MAX_TOKENS,
    ACTUAL_MODEL_MAX_COMPLETION_TOKENS
)
```

**Replace with:**
```python
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
    NANO_CHAR_THRESHOLD,  # NEW
    MINI_CHAR_THRESHOLD   # NEW
)
```

---

## Step 3: Replace optimize_model_parameters function

**File:** `services/ai_service.py`

**Action:** Replace the ENTIRE `optimize_model_parameters` function (approximately lines 50-115) with the following:

```python
def optimize_model_parameters(
    drawing_type: str, raw_content: str, pdf_path: str
) -> Dict[str, Any]:
    """
    Determine optimal model parameters based on drawing type and content.
    
    Model selection priority:
    1. Schedules ALWAYS get full model (accuracy critical)
    2. Force mini override applies to non-schedules only (cost control)
    3. Size-based buckets for everything else:
       - < 3K chars: nano/tiny model
       - 3K-15K chars: mini model  
       - > 15K chars: full model
    """
    content_length = len(raw_content) if raw_content else 0

    # Validate configuration
    if not DEFAULT_MODEL:
        raise ValueError("DEFAULT_MODEL not configured in settings")

    # Detect if this is a schedule (schedules need maximum accuracy)
    is_schedule = (
        "panel" in drawing_type.lower()
        or "schedule" in drawing_type.lower()
        or ("mechanical" in drawing_type.lower() and "schedule" in pdf_path.lower())
        or ("plumbing" in drawing_type.lower() and "schedule" in pdf_path.lower())
    )

    # Get force mini override status
    force_mini = get_force_mini_model()

    # PRIORITY 1: Schedules ALWAYS use full model regardless of size or overrides
    if is_schedule:
        model = SCHEDULE_MODEL  # Will map to gpt-5 when USE_GPT5_API=true
        temperature = LARGE_MODEL_TEMP
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for schedule document ({content_length} chars)")
    
    # PRIORITY 2: Force mini override for non-schedules (emergency cost control)
    elif force_mini:
        model = DEFAULT_MODEL  # Will map to gpt-5-mini when USE_GPT5_API=true
        temperature = DEFAULT_MODEL_TEMP
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Force-mini override active; using mini model for non-schedule ({content_length} chars)")
    
    # PRIORITY 3: Size-based bucket selection for normal operation
    elif content_length < NANO_CHAR_THRESHOLD:
        # Small documents < 3K chars: Use nano/tiny
        model = TINY_MODEL  # Will map to gpt-5-nano when USE_GPT5_API=true
        temperature = TINY_MODEL_TEMP
        max_tokens = TINY_MODEL_MAX_TOKENS
        logger.info(f"Using nano/tiny model for small document ({content_length} chars)")
    
    elif content_length < MINI_CHAR_THRESHOLD:
        # Medium documents 3K-15K chars: Use mini
        model = DEFAULT_MODEL  # Will map to gpt-5-mini when USE_GPT5_API=true
        temperature = DEFAULT_MODEL_TEMP
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using mini model for medium document ({content_length} chars)")
    
    else:
        # Large documents > 15K chars: Use full model
        model = LARGE_DOC_MODEL  # Will map to gpt-5 when USE_GPT5_API=true
        temperature = LARGE_MODEL_TEMP
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for large document ({content_length} chars)")

    # Map to GPT-5 models if enabled (existing logic)
    if USE_GPT5_API:
        original_model = model
        model = GPT5_MODEL_MAP.get(model, model)
        if model != original_model:
            logger.info(f"Mapped {original_model} -> {model} (GPT-5 mode)")

    # Dynamic token allocation for large documents (existing logic)
    if model in [LARGE_DOC_MODEL, SCHEDULE_MODEL] or (USE_GPT5_API and model == "gpt-5"):
        # Scale tokens based on input size
        if content_length > 35000:  # Massive specs/drawings
            max_tokens = min(ACTUAL_MODEL_MAX_COMPLETION_TOKENS, max_tokens * 2)
            logger.info(f"Boosting max_tokens to {max_tokens} for very large document")
        elif content_length > 25000:  # Large complex documents
            max_tokens = min(ACTUAL_MODEL_MAX_COMPLETION_TOKENS, int(max_tokens * 1.5))
            logger.info(f"Boosting max_tokens to {max_tokens} for large document")

    # Build parameters
    params = {
        "model": model,
        "temperature": temperature,
        "max_tokens": min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS),
    }

    # Special handling for panel schedules - always use 0 temperature (existing logic)
    if "panel" in drawing_type.lower() or "schedule" in drawing_type.lower():
        params["temperature"] = 0.0

    # Log final selection with size bucket info
    size_bucket = "nano" if content_length < NANO_CHAR_THRESHOLD else \
                  "mini" if content_length < MINI_CHAR_THRESHOLD else "full"
    
    logger.info(
        f"Model selection: type={drawing_type}, length={content_length}, "
        f"bucket={size_bucket}, schedule={is_schedule}, force_mini={force_mini}, "
        f"model={params['model']}, temp={params['temperature']}, max_tokens={params['max_tokens']}"
    )
    return params
```

---

## Summary of Changes

1. **Added two new configurable thresholds** in `config/settings.py`:
   - `NANO_CHAR_THRESHOLD` (default: 3000)
   - `MINI_CHAR_THRESHOLD` (default: 15000)

2. **Updated imports** in `ai_service.py` to include the new thresholds

3. **Replaced `optimize_model_parameters` function** with new logic that:
   - Prioritizes schedules (always full model)
   - Respects force_mini override for non-schedules
   - Implements 3-tier size buckets for normal operation
   - Preserves all existing features (GPT-5 mapping, dynamic tokens, temp=0 for schedules)
   - Adds better logging with size bucket information

## Testing Checklist

After implementing, verify:
- [ ] Small file (< 3K chars, non-schedule) → uses nano/tiny
- [ ] Medium file (3K-15K chars, non-schedule) → uses mini
- [ ] Large file (> 15K chars, non-schedule) → uses full
- [ ] Any schedule (regardless of size) → uses full with temp=0
- [ ] Force mini enabled + non-schedule → uses mini
- [ ] Force mini enabled + schedule → still uses full
- [ ] GPT-5 mapping works (check logs for "Mapped X -> Y")
</artifact>

The instructions above are structured for a cursor agent to execute surgically. The key points:

1. **Two new constants** get added to config/settings.py
2. **Import statement** gets updated to include those constants  
3. **The entire optimize_model_parameters function** gets replaced with the new logic

The new logic maintains all your safety features:
- Schedules always get full model (overrides everything else)
- Force mini works as emergency cost control (but schedules still override it)
- Size buckets apply when neither of the above conditions are met
- All existing features preserved (GPT-5 mapping, dynamic tokens, temperature adjustments)

The thresholds are configurable via environment variables, so you can tune them without code changes later.