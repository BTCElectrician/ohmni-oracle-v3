# PRD: Construction Drawing OCR & Processing Optimization

## Executive Summary
Fix critical performance issues causing timeouts and excessive API costs in the construction drawing processing pipeline. Main issues: OCR making 90 API calls per drawing, GPT-5 timeouts, and circuit breaker not functioning.

## Current Problems
1. **OCR is making 90 API calls per PDF** (3x3 tiling × 10 pages)
2. **GPT-5 timeouts** on large documents despite 240s timeout
3. **Circuit breaker doesn't prevent failed calls** from continuing
4. **Token limits too high** (16K) causing long generation times
5. **Poor error visibility** - can't tell timeout from other failures

## Proposed Solution

### 1. OCR Optimization
**Current State:** 3×3 tiling @ 600 DPI using GPT-5 = 90 API calls per drawing
**Target State:** Full-page @ 300 DPI using GPT-4o-mini = 2 API calls per drawing

**Implementation:**
- Change OCR model from GPT-5 to GPT-4o-mini
- Eliminate tiling (change from 3×3 grid to 1×1)
- Reduce DPI from 600 to 300
- Reduce max pages from 10 to 2
- Adjust trigger threshold to 1500 chars/page

### 2. Circuit Breaker Fix
Make the circuit breaker actually prevent doomed API calls by checking the flag BEFORE making calls.

### 3. Error Handling Improvements
- Distinguish timeouts from other errors
- Log specific failure reasons
- Save raw API responses for debugging

### 4. Token Limit Optimization
- Cap output tokens based on document size
- Reduce overall max from 16K to 12K
- Set reasonable limits per document tier

## Implementation Changes

### File: `services/ocr_service.py`

**Lines 14-17, change:**
```python
# FROM:
GRID = 3  # 3x3 tiling
DPI = 600  # High quality
MODEL = "gpt-5"  # Use GPT-5 Responses API for OCR
TOKENS_PER_TILE = 1000  # Enough for construction text

# TO:
GRID = int(os.getenv("OCR_GRID_SIZE", "1"))  # Default to no tiling (1x1)
DPI = int(os.getenv("OCR_DPI", "300"))  # 300 DPI is sufficient for text
MODEL = os.getenv("OCR_MODEL", "gpt-4o-mini")  # Fast, cheap, accurate enough
TOKENS_PER_TILE = int(os.getenv("OCR_TOKENS_PER_TILE", "3000"))  # Enough for full page
```

### File: `services/ai_service.py`

**1. Fix Circuit Breaker (around line 195):**
Add after building params in `make_responses_api_request`:
```python
# Check circuit breaker BEFORE making the call
if _gpt5_circuit_open and str(model).startswith("gpt-5"):
    logger.warning(f"GPT-5 circuit breaker OPEN, skipping {model}")
    raise AIProcessingError("gpt5_circuit_open - failing fast to trigger fallback")
```

**2. Improve Error Handling (replace exception handler at end of `make_responses_api_request`):**
```python
except asyncio.TimeoutError as e:
    request_time = time.time() - start_time
    _gpt5_note_failure(f"timeout@{RESPONSES_TIMEOUT_SECONDS}s")
    logger.error(
        "Responses API request timed out",
        extra={
            "duration": f"{request_time:.2f}s", 
            "model": model,
            "timeout": RESPONSES_TIMEOUT_SECONDS,
            "file": os.path.basename(file_path) if file_path else "unknown",
        },
    )
    raise AIProcessingError(f"Timeout after {RESPONSES_TIMEOUT_SECONDS}s") from e
    
except Exception as e:
    request_time = time.time() - start_time
    
    # Extract better error information
    error_type = e.__class__.__name__
    status = getattr(getattr(e, "response", None), "status_code", None)
    
    # Better reason for logging
    if status:
        reason = f"{error_type}_status_{status}"
    elif "timeout" in str(e).lower():
        reason = "timeout"
    else:
        reason = error_type or "unknown"
        
    _gpt5_note_failure(reason)
    
    logger.error(
        "Responses API request failed",
        extra={
            "duration": f"{request_time:.2f}s",
            "error": str(e),
            "error_type": error_type,
            "status": status,
            "model": model,
            "file": os.path.basename(file_path) if file_path else "unknown",
        },
    )
    raise AIProcessingError(f"Responses API request failed: {str(e)}")
```

**3. Cap Output Tokens (in `optimize_model_parameters`):**
Replace the dynamic token allocation section:
```python
# Token policy: keep large outputs reasonable to avoid timeouts
if model in [LARGE_DOC_MODEL, SCHEDULE_MODEL]:
    if content_length > 35000:
        max_tokens = min(6000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        logger.info(f"Capping max_tokens to {max_tokens} for very large document")
    elif content_length > 25000:
        max_tokens = min(8000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        logger.info(f"Setting max_tokens to {max_tokens} for large document")
    elif content_length > 15000:
        max_tokens = min(10000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
    # else: use default max_tokens
```

### File: `processing/file_processor.py`

**Save Raw Output (in `_step_ai_processing_and_parsing`, after line ~340):**
Add after getting structured_json_str:
```python
# Save raw output immediately for debugging
if structured_json_str:
    try:
        await self.storage.save_text(
            structured_json_str,
            self.raw_error_output_path
        )
        self.logger.debug(f"Saved raw AI response to {self.raw_error_output_path}")
    except Exception as e:
        self.logger.warning(f"Could not save raw output: {e}")
```

### File: `.env` - Complete Updated Configuration

```bash
# ============== OPENAI API CONFIGURATION ==============
OPENAI_API_KEY=your-key-here

# ============== GPT-5 CONFIGURATION ==============
# Use the GPT-5 Responses API
USE_GPT5_API=true

# Optional Configuration
LOG_LEVEL=INFO
BATCH_SIZE=10
API_RATE_LIMIT=60
TIME_WINDOW=60

# Processing Configuration
# [DEPRECATED] USE_SIMPLIFIED_PROCESSING=false
FORCE_MINI_MODEL=false
MAX_CONCURRENT_API_CALLS=20
MECH_SECOND_PASS=false
ENABLE_METADATA_REPAIR=false

# Model Selection Settings
MODEL_UPGRADE_THRESHOLD=20000
USE_4O_FOR_SCHEDULES=false
ENABLE_AI_CACHE=false
AI_CACHE_TTL_HOURS=24
ENABLE_TABLE_EXTRACTION=true  # Changed: helps reduce output size

# Model Configuration - GPT-5 SERIES (Responses API)
DEFAULT_MODEL=gpt-5-mini
LARGE_DOC_MODEL=gpt-5
SCHEDULE_MODEL=gpt-5
TINY_MODEL=gpt-5-nano
TINY_MODEL_THRESHOLD=3000

# Model Size Thresholds (character counts)
NANO_CHAR_THRESHOLD=3000           # <3K => nano
MINI_CHAR_THRESHOLD=15000          # 3K–15K => mini; >15K => full

# Token Limits
DEFAULT_MODEL_TEMP=0.1
DEFAULT_MODEL_MAX_TOKENS=12000     # Reduced from 16000
LARGE_MODEL_TEMP=0.1
LARGE_MODEL_MAX_TOKENS=12000       # Reduced from 16000
TINY_MODEL_TEMP=0.0
TINY_MODEL_MAX_TOKENS=8000
ACTUAL_MODEL_MAX_COMPLETION_TOKENS=12000  # Reduced from 16000

# Fallback chain - now includes gpt-4o as backup
MODEL_FALLBACK_CHAIN=gpt-5-mini,gpt-4o-mini

# Responses API timeout
RESPONSES_TIMEOUT_SECONDS=240

# Circuit breaker settings
GPT5_FAILURE_THRESHOLD=3           # Increased from 2
GPT5_DISABLE_ON_EMPTY_OUTPUT=true

# PDF Connection Pooling (Optional)
ENABLE_PDF_POOLING=false
PDF_POOL_SIZE=10

# ============== OCR CONFIGURATION ==============
# Simplified OCR - Full page extraction when needed
OCR_ENABLED=true
OCR_THRESHOLD=1500                 # Chars per page trigger (not total)
OCR_MAX_PAGES=2                    # Reduced from 10
OCR_MODEL=gpt-4o-mini             # Changed from gpt-5
OCR_GRID_SIZE=1                   # No tiling! Was 3x3 = 90 calls
OCR_DPI=300                       # Reduced from 600
OCR_TOKENS_PER_TILE=3000         # Increased for full page
```

## Expected Outcomes

### Performance Improvements
- **OCR API calls**: 90 → 2 per drawing (98% reduction)
- **OCR cost**: ~$0.50 → ~$0.01 per drawing
- **Processing time**: 90+ seconds → 5-10 seconds for OCR
- **Timeout rate**: Should drop to near zero

### Cost Savings
- **Before**: 90 calls × $0.005 = $0.45/drawing for OCR alone
- **After**: 2 calls × $0.001 = $0.002/drawing
- **Monthly savings**: At 1000 drawings/month = $448 saved

### Quality Maintenance
- OCR accuracy remains high (GPT-4o-mini is sufficient for text extraction)
- 300 DPI captures all readable text from construction drawings
- Full-page extraction ensures no content is missed

## Testing Plan

1. **Unit Test OCR Changes:**
   ```bash
   python -c "import os; print(f'OCR Model: {os.getenv(\"OCR_MODEL\", \"gpt-4o-mini\")}'); print(f'Grid: {os.getenv(\"OCR_GRID_SIZE\", \"1\")}'); print(f'Pages: {os.getenv(\"OCR_MAX_PAGES\", \"2\")}')"
   ```

2. **Test Single File:**
   - Pick a previously failing large file
   - Run with new configuration
   - Verify: No timeouts, OCR uses 2 calls max, fallback chain works

3. **Batch Test:**
   - Run full job folder
   - Monitor for "gpt5_circuit_open" messages
   - Check that fallback to gpt-4o-mini occurs

## Rollback Plan
If issues occur, revert by:
1. Change OCR_MODEL back to "gpt-5"
2. Change OCR_GRID_SIZE back to "3"
3. Increase ACTUAL_MODEL_MAX_COMPLETION_TOKENS back to 16000

## Success Metrics
- Zero timeout errors in a full batch run
- Average OCR calls per drawing < 3
- Circuit breaker triggers and recovers appropriately
- Processing time < 30 seconds per drawing average

---

**Instructions for Cursor:** 
Please implement all changes specified above in the exact files and locations indicated. The changes are designed to work together as a system - implement all of them, not just some. Pay special attention to the circuit breaker fix in `ai_service.py` as it's critical for preventing cascade failures.