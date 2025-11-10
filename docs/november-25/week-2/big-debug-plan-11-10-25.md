# 🔍 Ohmni Oracle v3 - Critical Issues Investigation & Fix Request

**Date:** November 10, 2025, 7:52 AM Run  
**Context:** Production ETL pipeline processing 9 construction drawings  
**Status:** Processing completed (9/9 files), but with **3 critical issues** requiring immediate attention

---

## 📋 Executive Summary

The processing run completed successfully but revealed three distinct categories of issues:

1. **🔥 CRITICAL - Priority 1:** OCR service completely broken (36 failures)
2. **⚠️ HIGH - Priority 2:** Resource leaks from unclosed async client sessions
3. **📊 MEDIUM - Priority 3:** Data quality issues causing room template skipping

**Performance Impact:** 19.5% slower than baseline (103 sec/drawing vs. 86 sec expected)

---

## 🔥 PRIORITY 1: OCR Service Broken (BLOCKING)

### Problem Statement
The OCR service is completely non-functional due to an incorrect API call to the OpenAI client.

### Error Details
```
WARNING - Tile 0,0 failed: 'AsyncOpenAI' object has no attribute 'responses'
WARNING - Tile 0,1 failed: 'AsyncOpenAI' object has no attribute 'responses'
... (36 total failures across 4 drawings)
```

### Affected Files
- **Primary Suspect:** `services/ocr_service.py`
- Specifically: The tile processing function that calls the OpenAI API

### Root Cause Analysis
The code is trying to call:
```python
response = await client.responses.create(...)  # ❌ WRONG
```

But should be calling:
```python
response = await client.chat.completions.create(...)  # ✅ CORRECT
```

### Impact
- 4 drawings attempted OCR, all failed
- 9 tiles per drawing × 4 drawings = 36 failed API calls
- Each failure wasted ~0.5-0.7 seconds
- Downstream effects: Poor text extraction → increased metadata repair time
- Equipment file metadata repair ballooned to 41 seconds (normally ~1-2 sec)

### Required Fix
**TASK FOR CODEX:**
1. Locate all instances of `client.responses` in `services/ocr_service.py`
2. Replace with `client.chat.completions` 
3. Verify the method signature matches the OpenAI SDK's `chat.completions.create()` API
4. Test that OCR extraction returns valid text

### Success Criteria
- ✅ No more "has no attribute 'responses'" errors
- ✅ OCR successfully extracts text from panel schedules
- ✅ Metadata repair times return to <2 seconds
- ✅ JSON parsing times return to <1 second

---

## ⚠️ PRIORITY 2: Unclosed Client Sessions (Resource Leak)

### Problem Statement
Async HTTP client sessions (`aiohttp.ClientSession`) are not being properly closed, causing resource leaks and potential memory/connection pool exhaustion.

### Error Details
```
asyncio - ERROR - Unclosed client session
asyncio - ERROR - Unclosed connector
client_session: <aiohttp.client.ClientSession object at 0x...>
connector: <aiohttp.connector.TCPConnector object at 0x...>
```

### Affected Modules
Based on log proximity, these modules are likely culprits:
- `processing.file_processor`
- `services.ai_service` 
- `templates.room_templates`
- Any module that makes HTTP requests (OpenAI API, Azure Blob Storage, Azure AI Search)

### Root Cause Analysis
Sessions are being created but not properly closed due to:
1. Missing `async with` context managers
2. Missing explicit `await session.close()` calls
3. Exception handling paths that skip cleanup

### Current Pattern (Likely Broken)
```python
# ❌ BAD - Session never closed
session = aiohttp.ClientSession()
response = await session.get(url)
# ... processing ...
# Oops, forgot to close!
```

### Required Pattern (Correct)
```python
# ✅ GOOD - Context manager ensures cleanup
async with aiohttp.ClientSession() as session:
    response = await session.get(url)
    # ... processing ...
# Session automatically closed here
```

### Required Fix
**TASK FOR CODEX:**
1. Search codebase for all instances of `aiohttp.ClientSession()` initialization
2. Identify sessions NOT wrapped in `async with` context managers
3. Refactor to use `async with aiohttp.ClientSession() as session:` pattern
4. For long-lived sessions (if any), ensure explicit `await session.close()` in:
   - Success paths
   - Exception handlers (`try/finally` blocks)
   - Cleanup methods

### Files to Investigate
```bash
# Search command to find potential issues:
grep -rn "ClientSession()" --include="*.py" services/
grep -rn "ClientSession()" --include="*.py" processing/
grep -rn "ClientSession()" --include="*.py" templates/
```

### Success Criteria
- ✅ No more "Unclosed client session" errors in logs
- ✅ All sessions wrapped in `async with` or explicitly closed
- ✅ Memory usage stable across multiple runs

---

## 📊 PRIORITY 3: Missing Room Numbers in Template Generation

### Problem Statement
The room template generation process is skipping rooms because the `room_number` field is parsing as `None`, even though the `room_name` is successfully extracted.

### Error Details
```
templates.room_templates - WARNING - Skipping room missing number: {'room_name': 'MAINTENANCE', 'room_number': None, ...}
templates.room_templates - WARNING - Skipping room missing number: {'room_name': 'PS 1', 'room_number': None, ...}
templates.room_templates - WARNING - Skipping room missing number: {'room_name': 'CORRIDOR', 'room_number': None, ...}
```

### Affected File
- `A2.2-DIMENSION-FLOOR-PLAN-Rev.3.pdf` (Architectural drawing)

### Root Cause Analysis
This is a **data quality issue** in the upstream extraction process:
1. PDF text extraction is capturing room names correctly
2. BUT the JSON parsing/validation is failing to extract room numbers
3. The room template module then correctly skips these incomplete records

### Potential Causes
1. **Room numbering convention mismatch:** Rooms like "PS 1" or "MAINTENANCE" may not have traditional numeric IDs
2. **Regex pattern too strict:** The room number extraction regex might only match pure numbers (e.g., "118") and fail on alphanumeric IDs (e.g., "PS1", "MAINT-01")
3. **JSON schema mismatch:** The extraction prompt may not be asking GPT to parse these non-standard room identifiers

### Data Pipeline to Trace
```
PDF → Text Extraction → AI Processing (GPT) → JSON Parsing → Room Template Generation
                                             ↑
                                    Problem is likely here
```

### Required Fix
**TASK FOR CODEX:**

1. **Review the extraction prompt** (likely in `services/ai_service.py` or prompt templates):
   - Does it instruct GPT to extract room numbers for non-standard rooms?
   - Does it handle rooms that use alphanumeric IDs (e.g., "PS 1", "MECH-01")?

2. **Review the JSON validation logic** (likely in `processing/file_processor.py`):
   - What regex/validation rules are applied to `room_number`?
   - Is it rejecting valid but non-numeric room identifiers?

3. **Review the room template module** (`templates/room_templates.py`):
   - Should it be more lenient and accept `room_name` as a fallback identifier?
   - Could we use `room_name` as the `room_id` when `room_number` is None?

### Example Room Data
```json
// ✅ Works fine
{"room_name": "KITCHEN", "room_number": "118"}

// ❌ Currently fails
{"room_name": "MAINTENANCE", "room_number": null}
{"room_name": "PS 1", "room_number": null}
{"room_name": "CORRIDOR", "room_number": null}
```

### Suggested Solutions

**Option A: Expand room_number extraction logic**
```python
# Allow alphanumeric room identifiers
# Match: "118", "PS 1", "MECH-01", "M-103"
room_number_pattern = r'[A-Z0-9\-\s]+'
```

**Option B: Use room_name as fallback**
```python
# In room template generation
room_id = room_data.get('room_number') or room_data.get('room_name')
if not room_id:
    logger.warning(f"Skipping room with no identifier: {room_data}")
    continue
```

**Option C: Prompt engineering fix**
Update the GPT extraction prompt to explicitly handle utility spaces:
```
"For each room, extract:
- room_name: The room description (e.g., 'KITCHEN', 'MAINTENANCE', 'PS 1')
- room_number: The room identifier. This may be:
  * A numeric ID (e.g., '118')
  * An alphanumeric code (e.g., 'PS 1', 'MECH-01')  
  * If no explicit number exists, use the room_name as the identifier"
```

### Success Criteria
- ✅ No more "Skipping room missing number" warnings
- ✅ All rooms in architectural drawings generate templates
- ✅ Room identifiers correctly handle alphanumeric formats

---

## ℹ️ NON-CRITICAL: Azure Container Already Exists (409)

### Problem Statement
Frequent `409 - ContainerAlreadyExists` errors when uploading to Azure Blob Storage.

### Error Details
```
Response status: 409
x-ms-error-code: 'ContainerAlreadyExists'
```

### Analysis
This is **EXPECTED BEHAVIOR** and not a bug. The code is:
1. Attempting to create a container (PUT request)
2. Azure returns 409 if it already exists
3. Code handles this gracefully and proceeds with upload (201 Created)

### Required Action
**TASK FOR CODEX (Low Priority):**
1. **Check for existence before creation:**
   ```python
   # Instead of try/create/catch, check first
   if not await container_client.exists():
       await container_client.create()
   ```

2. **OR downgrade log level:**
   ```python
   # Change from INFO to DEBUG
   logger.debug("Container already exists (expected)")
   ```

This optimizes API calls and reduces log noise, but is **not blocking** since the current behavior is functionally correct.

---

## 📊 Performance Baseline Context

**Expected Performance (Baseline):**
- Average per drawing: 85-105 seconds
- API wait time: ~87% of total processing
- JSON parsing: <1 second
- Metadata repair: <2 seconds

**This Run's Performance:**
- Average per drawing: **103.51 seconds** ✅ (within range, but skewed by issues)
- API wait time: **89.5%** of total processing
- JSON parsing: **6.15 seconds** ❌ (553% slower - OCR failures downstream)
- Metadata repair: **6.92 seconds** ❌ (553% slower - poor extraction quality)
- Equipment file repair: **41 seconds** 🔥 (1,818% slower - severe issue)

### Token Throughput (External Factor)
The OpenAI API was also slower this morning:
- gpt-4.1-nano: 40 tok/sec (normally 70-80)
- gpt-4.1-mini: 61 tok/sec (normally 70-80)
- Morning traffic (7:52 AM PST = peak usage)

This contributed ~15-20% slowdown but is not in our control.

---

## 🎯 Implementation Checklist

**For Codex to execute:**

### Phase 1: OCR Fix (Critical)
- [ ] Fix `client.responses` → `client.chat.completions` in OCR service
- [ ] Verify OCR extraction works on test file
- [ ] Run full test suite to confirm <1sec JSON parsing

### Phase 2: Resource Cleanup (High Priority)  
- [ ] Audit all `ClientSession` instantiations
- [ ] Refactor to `async with` pattern
- [ ] Add explicit `session.close()` in exception paths if needed
- [ ] Run leak detection test (multiple consecutive runs)

### Phase 3: Room Number Extraction (Medium Priority)
- [ ] Review extraction prompts for room data
- [ ] Update regex/validation for alphanumeric room IDs
- [ ] Implement fallback logic (room_name as identifier)
- [ ] Test on A2.2 architectural drawing

### Phase 4: Optional Optimization
- [ ] Check Azure container existence before creation
- [ ] Downgrade 409 logs to DEBUG level

---

## 📁 Files Requiring Investigation

**High Priority:**
- `services/ocr_service.py` (OCR fix)
- `services/ai_service.py` (session cleanup, extraction prompts)
- `processing/file_processor.py` (session cleanup, JSON validation)
- `templates/room_templates.py` (room number handling)

**Medium Priority:**
- `storage/azure_client.py` or equivalent (session cleanup, container creation)
- Any module with HTTP requests (Azure SDK, OpenAI SDK calls)

**Configuration:**
- Extraction prompt templates (wherever GPT prompts are stored)
- Room number validation regex patterns

---

## 🧪 Testing & Validation

**After fixes, verify:**
1. Run the same 9-file test set
2. Confirm metrics:
   - ✅ Total time: 13-15 minutes (not >15.5 minutes)
   - ✅ JSON parsing: <1 sec average
   - ✅ Metadata repair: <2 sec average
   - ✅ No OCR failures in logs
   - ✅ No unclosed session warnings
   - ✅ No skipped rooms (or acceptable # documented)

3. Log quality:
   - ✅ Clean error logs (no asyncio warnings)
   - ✅ All rooms processed or explicitly documented why skipped

---

## 💡 Additional Context for Codex

**System Architecture:**
- ETL pipeline: Extract (PDF) → Transform (GPT) → Load (Azure AI Search)
- Async processing with ThreadPoolExecutor (9 workers)
- OpenAI models: gpt-4.1-nano, gpt-4.1-mini, gpt-4.1
- Storage: Azure Blob Storage
- Search: Azure AI Search

**Processing Flow:**
```
PDF Files (9) 
  → Queue by drawing type
  → Parallel workers (9)
  → Text Extraction (PyMuPDF)
  → OCR (if needed) ← BROKEN
  → AI Processing (OpenAI GPT)
  → JSON Parsing
  → Metadata Repair (if needed)
  → Template Generation
  → Azure Upload
  → Performance Metrics
```

**Code Quality Standards:**
- PEP 8 style guidelines
- Type hints required
- Comprehensive logging
- Error handling with fallbacks
- Performance instrumentation

---

## 🚀 Expected Outcome

After Codex implements these fixes:
1. **OCR works reliably** - No more API attribute errors
2. **No resource leaks** - Clean async session management
3. **Complete room data** - All rooms templated or explicitly handled
4. **Performance restored** - Back to 85-105 sec/drawing baseline
5. **Clean logs** - No warnings/errors unless actionable

---

**Ready for Codex to begin investigation and fixes.**