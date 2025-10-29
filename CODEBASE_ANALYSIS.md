# Ohmni Oracle v3 - Per-Panel Processing Implementation Analysis

**Date:** 2025-10-29  
**Branch:** claude/process-construction-drawings-011CUWmeewF3gJPypcWzVGcj  
**Analysis Focus:** Understanding current architecture for per-panel processing implementation

---

## EXECUTIVE SUMMARY

The current Ohmni Oracle v3 architecture processes **entire PDF documents as single monolithic units**. The system extracts all text/tables, sends them to AI in one request, and produces a unified JSON output. Per-panel processing would require significant architectural changes to support:

1. **Panel detection and boundary identification** at extraction time
2. **Content splitting** into discrete panel segments  
3. **Per-panel AI processing** with appropriate context
4. **Result merging** back into cohesive output
5. **Panel metadata tracking** throughout the pipeline

---

## 1. CURRENT AI PROCESSING FLOW

### Overview
**File:** `services/ai_service.py` (729 lines)

The current flow is fundamentally **single-pass, whole-document processing**:

```
PDF Content (extracted) → Raw AI Request → JSON Response → Validation → Repair (optional) → Output
```

### Key Processing Steps

#### 1.1 Model Selection (`optimize_model_parameters()`)
- **Content-size driven**: Tiered model selection based on character count
  - `< NANO_CHAR_THRESHOLD (3000 chars)` → TINY_MODEL (if available)
  - `< MINI_CHAR_THRESHOLD (15000 chars)` → DEFAULT_MODEL (gpt-5-mini)
  - `>= MINI_CHAR_THRESHOLD` → LARGE_DOC_MODEL (gpt-5)

- **Schedule/Spec detection** (`_is_schedule_or_spec()`):
  - Checks drawing_type and filename for "panel", "schedule", "spec"
  - Uses SCHEDULE_MODEL if detected (separate from size tiers)
  - Applies SPEC_MAX_TOKENS constraint

- **Token budgeting**:
  - SPEC_MAX_TOKENS: 16384 (default)
  - LARGE_MODEL_MAX_TOKENS: 16000 (default)
  - Output tokens capped for very large docs (>35000 chars → 12000 tokens)

#### 1.2 Extraction-to-Processing Flow
```python
# From process_drawing() in ai_service.py

raw_content = extraction_result.raw_text
# + titleblock_text appended separately for repair
# + tables included in raw_content

# Build system message from registry
system_message = registry.get(drawing_type, subtype)  # Always returns GENERAL prompt

# Make request
content = await call_with_cache(
    client=client,
    messages=[
        {"role": "system", "content": system_message},
        {"role": "user", "content": raw_content},  # ENTIRE DOC
    ],
    model=params["model"],
    temperature=params["temperature"],
    max_tokens=params["max_tokens"],
)

# Parse and repair
parsed = json.loads(content)
parsed["DRAWING_METADATA"] = _fill_critical_metadata_fallback(...)

# Optional repair pass for metadata
if get_enable_metadata_repair():
    repaired_metadata = await repair_metadata(titleblock_text, client, pdf_path)
    parsed["DRAWING_METADATA"].update(repaired_metadata)

return json.dumps(parsed)
```

#### 1.3 JSON Output Structure
```json
{
  "DRAWING_METADATA": {
    "drawing_number": "E5.00",
    "title": "Panel Schedule",
    "date": "2025-01-15",
    "revision": "A",
    "project_name": "Main Building",
    "sheet_number": "E5.00"
  },
  "ELECTRICAL": {
    "PANEL_SCHEDULES": [
      {
        "panel_name": "Panel A",
        "circuits": [
          {"circuit": "1", "trip": "20A", "poles": "1", "load_name": "Lighting - Room 101"}
        ]
      }
    ]
  }
}
```

### 1.4 Chunking/Splitting Logic
**Current Status: NONE**

There is **no existing chunking or splitting logic** in the current codebase:
- No panel boundary detection
- No document segmentation
- No sliding window approach
- Tables are merely appended as-is: `raw_content += f"\nTABLE:\n{table['content']}\n"`

### Truncation Handling
- **Detection only** (lines 579-588 in ai_service.py):
  ```python
  token_usage_percent = (estimated_output_tokens / current_max_tokens) * 100
  if token_usage_percent > 90:
      logger.warning("Possible truncation: {token_usage_percent:.0f}% token usage...")
  elif output_length < input_length * 0.5:
      logger.warning("Suspiciously small output...")
  ```
- No automatic retry with reduced content
- No fallback to chunked processing

---

## 2. EXTRACTION SERVICE STRUCTURE

### Overview
**File:** `services/extraction_service.py` (1062 lines)

#### 2.1 Multi-Page Handling
The extraction service processes **all pages uniformly** into one text blob:

```python
# From PyMuPdfExtractor._extract_content()

raw_text = ""
for i, page in enumerate(doc):
    page_text = f"PAGE {i+1}:\n"
    
    # Block-based extraction
    blocks = page.get_text("blocks")
    for block in blocks:
        if block[6] == 0:  # Text block
            page_text += block[4] + "\n"
    
    raw_text += page_text  # All concatenated
```

**Key observation:** Pages are concatenated with page markers but **no structural boundaries** are identified.

#### 2.2 Discipline-Specific Extractors

**ElectricalExtractor** has the most panel-relevant logic:

```python
class ElectricalExtractor(PyMuPdfExtractor):
    def _enhance_panel_information(self, text: str) -> str:
        """Marks but doesn't split panel schedules"""
        if "panel" in text.lower() or "circuit" in text.lower():
            text = "PANEL INFORMATION DETECTED:\n" + text
        
        if self._is_panel_schedule(text):
            text = (
                "===PANEL SCHEDULE BEGINS===\n" + text + "\n===PANEL SCHEDULE ENDS==="
            )
        return text
    
    def _is_panel_schedule(self, text: str) -> bool:
        """Detection logic only, no splitting"""
        panel_indicators = [
            "CKT" in text,
            "BREAKER" in text and "PANEL" in text,
            "CIRCUIT" in text and "LOAD" in text,
            # ... more checks
        ]
        return sum(panel_indicators) >= 2
    
    def _extract_panel_names(self, text: str) -> List[str]:
        """Extracts panel names but from unified content"""
        panel_patterns = [
            r"Panel:?\s*([A-Za-z0-9\-\.]+)",
            r"([A-Za-z0-9\-\.]+)\s*PANEL SCHEDULE",
        ]
        # Returns list of all panels found
```

**Key limitation:** Panel detection happens **after extraction**, on the combined text. No attempt to separate individual panels.

#### 2.3 Title Block Extraction
```python
def _extract_titleblock_region_text(self, doc: fitz.Document, page_num: int) -> str:
    """
    Extracts from first page only, using regional searches
    - Right strip: x0=0.70, y0=0.00, x1=1.00, y1=1.00
    - Bottom-right: x0=0.60, y0=0.70, x1=1.00, y1=1.00
    - Bottom strip: x0=0.00, y0=0.85, x1=1.00, y1=1.00
    """
    # Progressive expansion if text looks truncated
    for expansion in [0.0, 0.10, 0.20]:
        # Extract and score candidate text
        score = self._score_titleblock_text(text)
        if score >= 0.8 and not self._looks_truncated(text):
            return text
```

This is **page-1 only** and **title-block specific**. No per-panel title block extraction.

#### 2.4 Text Extraction Patterns
Current patterns are generic and document-wide:
- Page markers: `f"PAGE {i+1}:\n"`
- Table markers: `f"\nTABLE:\n{table['content']}\n"`
- Discipline markers: e.g., `"PANEL INFORMATION DETECTED:\n"` (added once)

**No per-panel markers or boundaries.**

---

## 3. FILE PROCESSING PIPELINE

### Overview
**File:** `processing/file_processor.py` (826 lines)

The pipeline is a **linear 7-step workflow** with no panel-aware logic:

#### 3.1 Pipeline Architecture

```python
class FileProcessingPipeline:
    async def process(self) -> ProcessingResult:
        """Main entry point"""
        
        # Step 1: Extract content
        if not await self._step_extract_content():
            return error_result
        
        # Step 2: Determine AI processing type
        await self._step_determine_ai_processing_type()
        
        # Step 3: AI processing and parsing
        if not await self._step_ai_processing_and_parsing():
            return error_result
        
        # Step 4: Validate drawing metadata
        await self._step_validate_drawing_metadata()
        
        # Step 5: Normalize data
        await self._step_normalize_data()
        
        # Step 6: Save output
        if not await self._step_save_output():
            return error_result
        
        # Step 7: Generate room templates (optional)
        await self._step_generate_room_templates()
        
        return success_result
```

#### 3.2 Content Flow in _step_ai_processing_and_parsing()

```python
async def _step_ai_processing_and_parsing(self) -> bool:
    extraction_result = self.processing_state["extraction_result"]
    raw_content = extraction_result.raw_text
    
    # Append all tables to end
    for table in extraction_result.tables:
        raw_content += f"\nTABLE:\n{table['content']}\n"
    
    # Single AI processing call with all content
    structured_json_str = await process_drawing(
        raw_content=raw_content,  # ENTIRE DOCUMENT
        drawing_type=processing_type,
        client=self.client,
        pdf_path=self.pdf_path,
        titleblock_text=extraction_result.titleblock_text,
    )
    
    # Single parse attempt
    parsed_json = parse_json_safely(
        structured_json_str,
        repair=(needs_repair and json_repair_enabled)
    )
```

**Key issue:** There's a retry mechanism for mechanical drawings (`MECH_SECOND_PASS`), but it processes the **entire content again**, not smaller chunks.

#### 3.3 Normalization Step
```python
async def _step_normalize_data(self) -> None:
    parsed_json = self.processing_state["parsed_json_data"]
    
    is_panel_schedule = "panel" in (subtype or "").lower()
    is_mechanical_schedule = "mechanical" in processing_type.lower()
    is_plumbing_schedule = "plumbing" in processing_type.lower()
    
    if is_panel_schedule:
        normalized_json = normalize_panel_fields(parsed_json)
```

**Normalization applies to the entire unified document**, not per-panel.

#### 3.4 Error Handling for Truncation

Current approach:
1. Detect truncation in `ai_service.py` via token usage % or output size checks
2. Log a warning
3. Continue processing (no retry or fallback)

**No built-in mechanism to handle or prevent truncation.**

---

## 4. CONFIGURATION SYSTEM

### Overview
**File:** `config/settings.py` (138 lines)

#### 4.1 Token Limit Settings
```python
# Model-specific parameters
DEFAULT_MODEL_MAX_TOKENS = int(os.getenv("DEFAULT_MODEL_MAX_TOKENS", "16000"))
LARGE_MODEL_MAX_TOKENS = int(os.getenv("LARGE_MODEL_MAX_TOKENS", "16000"))
TINY_MODEL_MAX_TOKENS = int(os.getenv("TINY_MODEL_MAX_TOKENS", "8000"))

# Actual provider limit
ACTUAL_MODEL_MAX_COMPLETION_TOKENS = int(os.getenv("ACTUAL_MODEL_MAX_COMPLETION_TOKENS", "32000"))

# Specification documents get constraints
SPEC_MAX_TOKENS = int(os.getenv("SPEC_MAX_TOKENS", "16384"))
```

#### 4.2 Model Selection Logic
```python
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-5-mini")
LARGE_DOC_MODEL = os.getenv("LARGE_DOC_MODEL", "gpt-5")
SCHEDULE_MODEL = os.getenv("SCHEDULE_MODEL", "gpt-5")
TINY_MODEL = os.getenv("TINY_MODEL", "")  # Optional

# Size thresholds for tiering
NANO_CHAR_THRESHOLD = int(os.getenv("NANO_CHAR_THRESHOLD", "3000"))
MINI_CHAR_THRESHOLD = int(os.getenv("MINI_CHAR_THRESHOLD", "15000"))
```

#### 4.3 Feature Flags
```python
# Metadata repair toggle
ENABLE_METADATA_REPAIR = os.getenv("ENABLE_METADATA_REPAIR", "false").lower() == "true"

# JSON repair toggle
ENABLE_JSON_REPAIR = os.getenv("ENABLE_JSON_REPAIR", "false").lower() == "true"

# Mechanical second pass
MECH_SECOND_PASS = os.getenv("MECH_SECOND_PASS", "true").lower() == "true"

# OCR settings
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_THRESHOLD = int(os.getenv("OCR_THRESHOLD", "1500"))  # chars per page
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "2"))
```

**No configuration for per-panel processing** (as it doesn't exist yet).

---

## 5. RECENT ARCHITECTURAL CHANGES

### From Git Log Analysis

#### Major Transitions
1. **Sep 2024:** Migrated from Responses API → Chat Completions API
   - Allows use of `response_format={"type": "json_object"}`
   - Simpler parameter handling (temperature + max_tokens)

2. **Oct 2024:** Added metadata repair and title block extraction
   - Non-destructive fallback filling
   - Separate focused AI pass for title block metadata
   - Progressive region expansion for truncated title blocks

3. **Oct 2024:** Removed dead prompt system
   - Deleted discipline-specific prompts (electrical, mechanical, plumbing)
   - Now uses single GENERAL prompt at runtime
   - Reduces maintenance burden

4. **Oct 2024:** Enhanced OCR service
   - Per-page character threshold (1500 chars/page default)
   - Memory-safe tiling with 10% overlap
   - Configurable DPI and grid size

#### Design Philosophy
- **Single source of truth:** One GENERAL prompt that works for all types
- **Dynamic model selection:** Size-aware, not type-aware (except schedules)
- **Resilience:** Optional repair passes (metadata, JSON)
- **Feature flags:** Everything is configurable; no hard-coded behaviors

**Pattern observed:** The codebase favors **adding optional post-processing steps** (repair, normalization) over changing the core pipeline. This suggests per-panel processing should follow a similar pattern.

---

## 6. WHERE PER-PANEL PROCESSING WOULD FIT

### Current Weaknesses That Per-Panel Processing Would Address

1. **Token limit hits:** Large multi-panel documents get truncated
2. **Context loss:** Panel-to-panel relationships diluted in single large prompt
3. **JSON complexity:** Single massive JSON output hard to validate and repair
4. **Inconsistent parsing:** AI may lose detail in later panels when content is very long
5. **Cost inefficiency:** Processing entire document even if only 1-2 panels matter

### Optimal Integration Points

#### Option A: Panel Detection at Extraction Time (RECOMMENDED)
**Where:** `services/extraction_service.py` → new `PanelDetector` class

Implement **in ElectricalExtractor**:
```python
class ElectricalExtractor(PyMuPdfExtractor):
    async def extract(self, file_path: str) -> ExtractionResult:
        result = await super().extract(file_path)
        
        # NEW: Detect panel boundaries in raw_text
        panels = self._detect_panels(result.raw_text)
        result.panels = [
            {
                "panel_name": panel["name"],
                "panel_number": panel["num"],
                "raw_text": panel["content"],
                "page_range": panel["pages"],
                "circuit_count": panel["circuit_count"],
            }
            for panel in panels
        ]
        return result
```

**Advantages:**
- Leverage existing text extraction
- Text-based panel detection (more reliable than PDF structure)
- Can detect panel boundaries early
- Clean separation of concerns

#### Option B: Panel Splitting in File Pipeline
**Where:** `processing/file_processor.py` → new step between extract and AI

```python
async def _step_detect_panels(self) -> None:
    """Detect and flag panels for separate processing"""
    extraction_result = self.processing_state["extraction_result"]
    
    # If electrical panel schedule detected
    if extraction_result.metadata.get("contains_panel_schedule"):
        panels = self._split_into_panels(extraction_result.raw_text)
        self.processing_state["panels"] = panels
        self.processing_state["is_multi_panel"] = len(panels) > 1

async def _step_ai_processing_per_panel(self) -> bool:
    """Process each panel separately"""
    if self.processing_state.get("is_multi_panel"):
        # Process each panel
        results = []
        for panel in self.processing_state["panels"]:
            panel_result = await process_drawing(
                raw_content=panel["content"],
                drawing_type=self.processing_state["processing_type_for_ai"],
                client=self.client,
                pdf_path=self.pdf_path,
                panel_name=panel["name"],  # NEW
            )
            results.append(panel_result)
        
        # Merge results
        self.processing_state["parsed_json_data"] = self._merge_panel_results(results)
    else:
        # Original single-pass processing
        return await self._step_ai_processing_and_parsing()
```

**Advantages:**
- Minimal changes to extraction service
- Can be toggled with a feature flag
- Clear pipeline step visibility

#### Option C: Chunked Processing in AI Service (NOT RECOMMENDED)
**Where:** `services/ai_service.py` → wrap `process_drawing()`

**Cons:**
- AI service becomes responsible for document structure (wrong abstraction)
- Harder to test
- Loses panel metadata context

---

## 7. POTENTIAL CONFLICTS AND ISSUES

### 7.1 Title Block Extraction
**Current:** Only extracted from page 1

**With per-panel processing:**
- Each panel might span multiple pages
- Panel-specific title blocks might not exist
- Fallback to document-level title block needed

**Solution:** Keep document-level title block extraction, don't duplicate per-panel.

### 7.2 Metadata Repair
**Current:** Single pass on document metadata

**With per-panel processing:**
- drawing_number, revision should stay document-level
- Panel names should be extracted from panel content
- Risk: Metadata repair pass tries to "fix" panel names

**Solution:**
- Lock document metadata after extraction
- Only repair panel-specific fields (panel name, circuits) per-panel

### 7.3 Normalization
**Current:** Applies `normalize_panel_fields()` to entire JSON

**With per-panel processing:**
- Normalize each panel's circuits independently
- Then reassemble under "PANEL_SCHEDULES" array

**Solution:** Modify `normalize_panel_fields()` to accept `panels` parameter

### 7.4 JSON Output Structure
**Current:**
```json
{
  "DRAWING_METADATA": {...},
  "ELECTRICAL": {
    "PANEL_SCHEDULES": [
      {"panel_name": "A", "circuits": [...]}
    ]
  }
}
```

**With per-panel processing:**
```json
{
  "DRAWING_METADATA": {...},  // Document level
  "ELECTRICAL": {
    "PANEL_SCHEDULES": [
      {
        "panel_name": "A",
        "source": "panel_1",  // NEW: which processing pass
        "processing_model": "gpt-5-mini",  // NEW: tracked
        "circuits": [...]
      }
    ]
  }
}
```

**Solution:** Extend metadata to track processing approach.

### 7.5 Caching
**Current:** Cache key = (prompt, parameters, model)

**With per-panel processing:**
- Panel content might be similar across documents
- Cache should be per-panel, not per-document
- Risk: Cache inflation

**Solution:**
- Add panel boundary markers to prompt to make cache key unique
- Or: Disable caching for per-panel mode

### 7.6 Error Handling
**Current:** Retry entire document processing

**With per-panel processing:**
- One panel fails → can retry just that panel
- Partial success possible (Panel A OK, Panel B failed)
- New status codes needed: `partial_success`

**Solution:**
```python
class ProcessingStatus(str, Enum):
    PROCESSED = "processed"
    PARTIAL_SUCCESS = "partial_success"  # NEW
    PANEL_FAILURE = "panel_failure"  # NEW
    # ...
```

---

## 8. RECOMMENDED INTEGRATION POINTS

### 8.1 Phase 1: Panel Detection (Low Risk)
**Goal:** Add panel detection capability without changing AI processing

**Steps:**
1. Create `utils/panel_detection.py` with regex patterns:
   ```python
   def detect_panel_boundaries(text: str) -> List[Dict[str, Any]]:
       """
       Returns:
       [
           {"name": "PANEL-A", "start_idx": 1234, "end_idx": 5678, "circuit_count": 42},
           {"name": "PANEL-B", "start_idx": 5679, "end_idx": 9999, "circuit_count": 38},
       ]
       """
   
   def extract_panel_content(text: str, panel: Dict) -> str:
       """Extract text segment for single panel"""
   ```

2. Add to `ElectricalExtractor`:
   ```python
   result.panel_metadata = {
       "detected_panels": detect_panel_boundaries(result.raw_text),
       "is_multi_panel_schedule": len(...) > 1,
   }
   ```

3. **No changes to AI processing** — just detection metadata

4. **Tests:** Unit tests for boundary detection patterns

#### Success Criteria
- Accurately identify panel boundaries in test documents
- No false positives
- Performance: < 10ms per document

---

### 8.2 Phase 2: Optional Per-Panel Mode (Medium Risk)
**Goal:** Add feature flag to enable per-panel processing

**Changes:**

1. **Configuration** (`config/settings.py`):
   ```python
   ENABLE_PER_PANEL_PROCESSING = os.getenv("ENABLE_PER_PANEL_PROCESSING", "false").lower() == "true"
   PANEL_MIN_CIRCUITS = int(os.getenv("PANEL_MIN_CIRCUITS", "10"))  # Only split if > 10 circuits
   ```

2. **File Pipeline** (`processing/file_processor.py`):
   ```python
   async def _step_ai_processing_and_parsing(self) -> bool:
       if not os.getenv("ENABLE_PER_PANEL_PROCESSING"):
           # Original code path
           return await self._original_step_ai_processing_and_parsing()
       
       # New per-panel path
       extraction_result = self.processing_state["extraction_result"]
       if extraction_result.panel_metadata.get("is_multi_panel_schedule"):
           return await self._step_ai_processing_per_panel()
       else:
           # Single panel or not panel schedule → use original
           return await self._original_step_ai_processing_and_parsing()
   
   async def _step_ai_processing_per_panel(self) -> bool:
       """New implementation"""
   ```

3. **AI Service** (`services/ai_service.py`):
   ```python
   async def process_drawing_panel(
       raw_content: str,
       drawing_type: str,
       client: AsyncOpenAI,
       panel_name: str,
       panel_index: int,
       total_panels: int,
       pdf_path: str = "",
   ) -> str:
       """Process single panel with context hints"""
       # Slightly modified prompt to include panel-specific context
   ```

4. **Merging** (new function in `file_processor.py`):
   ```python
   def _merge_panel_results(self, panel_results: List[Dict]) -> Dict:
       """Merge list of per-panel JSONs into single output"""
       merged = {
           "DRAWING_METADATA": panel_results[0]["DRAWING_METADATA"],
           "ELECTRICAL": {
               "PANEL_SCHEDULES": []
           }
       }
       for panel_result in panel_results:
           merged["ELECTRICAL"]["PANEL_SCHEDULES"].extend(
               panel_result["ELECTRICAL"]["PANEL_SCHEDULES"]
           )
       return merged
   ```

#### Success Criteria
- Produces identical output to non-per-panel mode for single-panel documents
- Better handling of 3+ panel documents
- No degradation for non-electrical drawings
- Error rate: < 5% increase

---

### 8.3 Phase 3: Optimization (Lower Priority)
**Once per-panel mode is stable:**

1. **Parallel processing:** Process panels concurrently
   ```python
   # Instead of sequential
   for panel in panels:
       result = await process_drawing_panel(...)
   
   # Use concurrent
   results = await asyncio.gather(*[
       process_drawing_panel(..., panel)
       for panel in panels
   ])
   ```

2. **Smart caching:** Cache by panel content hash
3. **Token budgeting:** Allocate tokens per panel based on complexity

---

## 9. IMPLEMENTATION CHECKLIST

### Phase 1: Detection
- [ ] Create `utils/panel_detection.py` with regex patterns
- [ ] Add test documents with 1, 2, 3+ panels
- [ ] Add `panel_metadata` field to `ExtractionResult`
- [ ] Update `ElectricalExtractor` to populate `panel_metadata`
- [ ] Unit tests for boundary detection

### Phase 2: Per-Panel Processing
- [ ] Add `ENABLE_PER_PANEL_PROCESSING` to `config/settings.py`
- [ ] Implement `_step_ai_processing_per_panel()` in `file_processor.py`
- [ ] Implement `process_drawing_panel()` in `ai_service.py`
- [ ] Implement `_merge_panel_results()` in `file_processor.py`
- [ ] Update normalization to work with per-panel output
- [ ] Integration tests with real panel PDFs

### Phase 3: Error Handling
- [ ] Update `ProcessingStatus` enum with partial success states
- [ ] Implement per-panel retry logic
- [ ] Update status file format to include panel-level results

### Phase 4: Documentation
- [ ] Update README with per-panel processing section
- [ ] Document new configuration options
- [ ] Add troubleshooting guide

---

## 10. RISKS AND MITIGATIONS

| Risk | Severity | Mitigation |
|------|----------|-----------|
| **Panel detection false positives** | HIGH | Tight regex patterns, extensive test suite, toggle flag |
| **Cache invalidation** | MEDIUM | Disable caching in per-panel mode or use content hash |
| **Metadata duplication** | MEDIUM | Lock document-level metadata, only vary panel-level |
| **Output structure incompatibility** | MEDIUM | Add version field to JSON, handle both formats downstream |
| **Performance degradation (multiple API calls)** | MEDIUM | Batch panels into groups if needed, caching |
| **Incomplete panels detected** | HIGH | Add minimum circuit threshold, fallback to single-pass |

---

## CONCLUSION

The Ohmni Oracle v3 codebase is **well-structured for adding per-panel processing** as an optional feature. Key takeaways:

1. **No existing chunking:** All content currently processed as single unit
2. **Good extensibility points:** ElectricalExtractor and FileProcessingPipeline support enhancement
3. **Feature flag culture:** System already uses toggles; per-panel mode fits naturally
4. **Normalization framework:** Already handles multiple drawing types; can extend to per-panel

**Recommended approach:**
- **Phase 1:** Panel detection in extraction service (non-breaking)
- **Phase 2:** Optional per-panel processing in file pipeline (feature flag)
- **Phase 3:** Optimization once stable

**Timeline estimate:** 2-3 weeks for Phases 1-2, 1 week for Phase 3

**Priority files to modify:**
1. `services/extraction_service.py` - Add panel detection
2. `processing/file_processor.py` - Add per-panel processing step
3. `services/ai_service.py` - Add `process_drawing_panel()` variant
4. `config/settings.py` - Add `ENABLE_PER_PANEL_PROCESSING` flag

