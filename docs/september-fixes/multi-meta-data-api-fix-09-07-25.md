# Cursor Instructions: Fix Metadata Repair Double API Call - Final Solution

## Problem Summary
The application is making 18 API calls for 9 PDF files because of two bugs:
1. The config getters are overwriting runtime environment variables with `.env` file values
2. The "disabled" log messages are hidden due to logging level configuration

## Required Fixes

### Fix 1: Remove override=True from Config Getters

**File:** `config/settings.py`

**Find the function `get_force_mini_model()` and replace it with:**
```python
def get_force_mini_model():
    """Get the FORCE_MINI_MODEL setting from environment"""
    # Respect the process environment; do not reload .env here
    return os.getenv("FORCE_MINI_MODEL", "false").lower() == "true"
```

**Find the function `get_enable_metadata_repair()` and replace it with:**
```python
def get_enable_metadata_repair():
    """Get the ENABLE_METADATA_REPAIR setting from environment"""
    # Respect the process environment; do not reload .env here
    return os.getenv("ENABLE_METADATA_REPAIR", "false").lower() == "true"
```

**Important:** Remove the `load_dotenv(override=True)` line from BOTH functions. This is the critical fix.

### Fix 2: Change Log Levels to Make Messages Visible

**File:** `services/ai_service.py`

**Find this code in the `process_drawing` function (around line 700-750):**
```python
elif titleblock_text and not enable_repair:
    logger.info("Metadata repair disabled by ENABLE_METADATA_REPAIR=false (skipping)")
```

**Replace with:**
```python
elif titleblock_text and not enable_repair:
    logger.warning("Metadata repair DISABLED by ENABLE_METADATA_REPAIR=false (skipping)")
```

**Find this code in the `repair_metadata` function (should be near the top):**
```python
if not get_enable_metadata_repair():
    logger.info("Metadata repair disabled by ENABLE_METADATA_REPAIR=false")
    return {}
```

**Replace with:**
```python
if not get_enable_metadata_repair():
    logger.warning("Metadata repair DISABLED by ENABLE_METADATA_REPAIR=false")
    return {}
```

## Verification Steps

### 1. Verify the .env file
Ensure your `.env` file contains:
```
ENABLE_METADATA_REPAIR=false
```

### 2. Run a Test
Run the application with your 9 PDF test files.

### 3. Check the Logs
You should now see one of these messages per file (9 total):
```
Metadata repair DISABLED by ENABLE_METADATA_REPAIR=false
```
or
```
Metadata repair DISABLED by ENABLE_METADATA_REPAIR=false (skipping)
```

### 4. Check the Metrics
In the metrics JSON file, verify:
- `api_statistics.count` should be **9** (not 18)
- Total processing time should drop by approximately 40-50%

## Expected Results

| Metric | Before Fix | After Fix |
|--------|------------|-----------|
| API Calls | 18 | **9** |
| Total Time | ~188s | **~95s** |
| Avg API Time | ~78s | **~40s** |
| E5.00-PANEL | ~159s | **~80s** |
| M6.01-MECH | ~144s | **~72s** |

## Why These Fixes Work

### The override=True Bug
- `load_dotenv(override=True)` was overwriting your runtime environment variables every time the getter was called
- This meant even if you set `ENABLE_METADATA_REPAIR=false` in your environment, it would be overwritten by whatever was in the .env file
- Removing this ensures the runtime environment variable is respected

### The Logging Level Bug  
- Your config sets `logging.getLogger("services.ai_service").setLevel(logging.WARNING)`
- But the "disabled" messages were using `logger.info()`
- This meant the messages were being suppressed even when metadata repair was actually disabled
- Changing to `logger.warning()` makes them visible

## Optional: Emergency Kill Switch

If you need to temporarily disable metadata repair completely while testing, add this as the FIRST line of the `repair_metadata` function:

```python
async def repair_metadata(...):
    return {}  # TEMPORARY: Force disable for testing
    # rest of function...
```

Remove this line after confirming the proper fix works.

## Troubleshooting

If you still see 18 API calls after these fixes:

1. **Check parse_json_safely**: If this function uses an LLM for repair, it could be making extra calls. Temporarily set `repair=False` in all calls to test.

2. **Verify environment**: Run this before your script to ensure the variable is set:
   ```bash
   export ENABLE_METADATA_REPAIR=false
   python main.py ...
   ```

3. **Add debug logging**: Add this at the start of `repair_metadata`:
   ```python
   logger.warning(f"repair_metadata called: ENABLE_METADATA_REPAIR={get_enable_metadata_repair()}")
   ```

## Summary

These two simple changes will fix the double API call issue:
1. Remove `load_dotenv(override=True)` from both getter functions
2. Change the disabled messages from `logger.info` to `logger.warning`

This should immediately cut your API calls from 18 to 9 and reduce processing time by approximately 50%.