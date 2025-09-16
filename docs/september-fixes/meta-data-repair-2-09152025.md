# Metadata Repair Fixes - Implementation Instructions

## File 1: config/settings.py

### Change 1: Add PIPELINE_LOG_LEVEL configuration
**Location:** After line with `LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")`

**Add this code:**
```python
# Pipeline-specific log level control
PIPELINE_LOG_LEVEL = os.getenv("PIPELINE_LOG_LEVEL", "").upper()

def _resolve_pipeline_level(default=logging.WARNING):
    """Resolve pipeline logging level from environment or defaults."""
    if PIPELINE_LOG_LEVEL in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
        return getattr(logging, PIPELINE_LOG_LEVEL, default)
    # If DEBUG_MODE is true, default to INFO for pipeline modules
    return logging.INFO if DEBUG_MODE else default
```

### Change 2: Replace the logging configuration section
**Location:** Find and replace the entire section that starts with `# Reduce logging noise from verbose modules`

**Replace with:**
```python
# Apply dynamic levels to pipeline modules
for name in [
    "services.ai_service",
    "utils.ai_cache",
    "services.extraction_service",
    "processing.file_processor",
]:
    logging.getLogger(name).setLevel(_resolve_pipeline_level())

# Keep httpx quiet
logging.getLogger("httpx").setLevel(logging.WARNING)
```

## File 2: services/extraction_service.py

### Change 1: Add title block preview logging
**Location:** In the `_extract_titleblock_region_text` method, after `text = page.get_text("text", clip=titleblock_rect)`

**Replace the line `return text.strip()` with:**
```python
text = text.strip()
if text:
    preview = text.replace("\n", " ")[:200]
    self.logger.info(f"Title block preview: {preview}")
else:
    self.logger.debug("No title block text detected in bottom-right region (40% x 30%)")
return text
```

## File 3: services/ai_service.py

### Change 1: Add helper functions for metadata reconciliation
**Location:** After the `_strip_json_fences` function definition

**Add these functions:**
```python
def _looks_like_sheet_no(s: str) -> bool:
    """Check if string looks like a sheet number (e.g., E5.00)."""
    try:
        return bool(re.match(r"^[A-Z]{1,3}\d{1,3}(?:\.\d{1,2})?$", str(s).strip(), re.I))
    except Exception:
        return False


def _parse_sheet_from_filename(pdf_path: Optional[str]) -> Optional[str]:
    """Extract sheet number from filename."""
    if not pdf_path:
        return None
    base = os.path.basename(pdf_path)
    m = re.match(r"^([A-Za-z]{1,3}\d{1,3}(?:\.\d{1,2})?)", base)
    return m.group(1) if m else None


def _extract_project_name_from_titleblock(titleblock_text: str) -> Optional[str]:
    """Extract project name from title block text."""
    for line in titleblock_text.splitlines():
        line_clean = line.strip()
        m = re.search(r"PROJECT(?:\s+NAME|\s+TITLE)?\s*[:\-]\s*(.+)$", line_clean, re.I)
        if m:
            value = m.group(1).strip().strip(":").strip("-")
            if value:
                return value
    return None


def _extract_revision_from_titleblock(titleblock_text: str) -> Optional[str]:
    """Extract revision from title block text."""
    # Try direct "Rev", "Revision" marks
    m = re.search(r"\bRev(?:ision)?\.?\s*[:\-]?\s*([A-Za-z0-9]+)\b", titleblock_text, re.I)
    if m:
        return m.group(1).strip()
    # Try "3 IFC", "B IFC" format
    m = re.search(r"\b([A-Za-z0-9]+)\s+IFC\b", titleblock_text, re.I)
    if m:
        return m.group(1).strip()
    return None


def _fill_critical_metadata_fallback(
    metadata: Dict[str, Any],
    pdf_path: Optional[str],
    titleblock_text: Optional[str],
) -> Dict[str, Any]:
    """Non-destructive fixes for common misplacements/missing fields."""
    metadata = metadata or {}
    sheet_number = metadata.get("sheet_number")
    drawing_number = metadata.get("drawing_number")
    revision = metadata.get("revision")
    project_name = metadata.get("project_name")

    # 1) Ensure sheet_number at least from filename
    if not sheet_number:
        candidate = _parse_sheet_from_filename(pdf_path)
        if candidate:
            sheet_number = candidate
            metadata["sheet_number"] = candidate
            logger.info(f"Filled sheet_number from filename: {candidate}")

    # 2) Fill drawing_number if missing using sheet_number or filename
    if not drawing_number:
        if sheet_number:
            metadata["drawing_number"] = sheet_number
            logger.info("Filled drawing_number from sheet_number")
        else:
            candidate = _parse_sheet_from_filename(pdf_path)
            if candidate:
                metadata["drawing_number"] = candidate
                logger.info(f"Filled drawing_number from filename: {candidate}")

    # 3) If revision looks like a sheet number, clear it (it's wrong)
    if revision and (_looks_like_sheet_no(revision) or (sheet_number and revision == sheet_number)):
        logger.info(f"Clearing incorrect revision value that matches sheet: {revision}")
        metadata["revision"] = None

    # 4) If revision still missing, try pulling from title block
    if (not metadata.get("revision")) and titleblock_text:
        rev = _extract_revision_from_titleblock(titleblock_text)
        if rev:
            metadata["revision"] = rev
            logger.info(f"Revision extracted from title block: {rev}")

    # 5) If project_name missing, try to extract from title block
    if not project_name and titleblock_text:
        pname = _extract_project_name_from_titleblock(titleblock_text)
        if pname:
            metadata["project_name"] = pname
            logger.info(f"Project name extracted from title block: {pname}")

    return metadata
```

### Change 2: Update process_drawing function
**Location:** In the `process_drawing` function, find the JSON parsing section with `parsed = json.loads(content)`

**Replace the entire metadata repair block (from `if not titleblock_text:` to the end of metadata repair) with:**
```python
# Apply fallback reconciliation first (fixes common misplacements)
tb_len = len(titleblock_text.strip()) if titleblock_text else 0
parsed["DRAWING_METADATA"] = _fill_critical_metadata_fallback(
    parsed.get("DRAWING_METADATA") or {},
    pdf_path,
    titleblock_text
)

# Metadata repair (LLM) with clearer logging
if not titleblock_text:
    logger.warning(f"NO TITLE BLOCK for {pdf_path} - skipping metadata repair")
elif get_enable_metadata_repair():
    logger.info(f"Running metadata repair (title block chars={tb_len})")
    try:
        repaired_metadata = await repair_metadata(titleblock_text, client, pdf_path)
        if repaired_metadata:
            if "DRAWING_METADATA" in parsed and isinstance(parsed["DRAWING_METADATA"], dict):
                parsed["DRAWING_METADATA"].update(repaired_metadata)
            else:
                parsed["DRAWING_METADATA"] = repaired_metadata
            logger.info("Successfully repaired metadata from title block")
        else:
            logger.info("Metadata repair returned empty dict (no changes)")
    except Exception as e:
        logger.warning(f"Metadata repair failed: {str(e)}")
else:
    logger.warning("Metadata repair DISABLED by ENABLE_METADATA_REPAIR=false (skipping)")

# Run fallback reconciliation again after repair to enforce consistency
parsed["DRAWING_METADATA"] = _fill_critical_metadata_fallback(
    parsed.get("DRAWING_METADATA") or {},
    pdf_path,
    titleblock_text
)

# Re-serialize content after possible metadata updates
content = json.dumps(parsed)
```

### Change 3: Update repair_metadata function
**Location:** In the `repair_metadata` function, right after the line `from templates.prompt_registry import get_registry`

**Add:**
```python
# Track attempt for visibility in performance report
from utils.performance_utils import get_tracker
tracker = get_tracker()
tracker.add_metric(
    "metadata_repair_attempt",
    os.path.basename(pdf_path) if pdf_path else "unknown",
    "metadata_repair",
    1.0
)

# Log repair attempt
repair_model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
logger.info(f"Attempting metadata repair with {repair_model}")
```

**Also add after successful repair (find where it returns `parsed["DRAWING_METADATA"]`):**
```python
# Track success
tracker.add_metric(
    "metadata_repair_success",
    os.path.basename(pdf_path) if pdf_path else "unknown",
    "metadata_repair",
    1.0
)
```

## File 4: .env file

### Add these environment variables:
```
ENABLE_METADATA_REPAIR=true
PIPELINE_LOG_LEVEL=INFO
```

## Testing Instructions

After applying these changes:

1. Run your test set with the new environment variables
2. Look for these new log messages:
   - "Title block preview: ..." 
   - "Running metadata repair (title block chars=X)"
   - "Filled drawing_number from..."
   - "Revision extracted from title block: ..."
   
3. Check the output JSONs for:
   - `drawing_number` should be populated (e.g., "E5.00")
   - `revision` should be corrected (e.g., "3" instead of "E5.00")
   - `project_name` should be populated if found in title block

4. Check metrics for new entries:
   - `metadata_repair_attempt`
   - `metadata_repair_success`