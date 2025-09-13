# Production-Ready OCR Tiling Implementation PRD
## Simple Rule + Production Fixes

### Core Logic
If PyMuPDF extracts < 400 characters → Run 3x3 tiling OCR at 600 DPI

### Critical Production Fixes Required
1. **Use `max_completion_tokens`** (not `max_tokens`) for GPT-4o
2. **Render tiles directly** (not full page then crop) to avoid memory issues
3. **Use PDF coordinates** for tile boundaries (not pixel coordinates)

---

## Implementation Instructions for Claude Code

### Step 1: Add Minimal Config
**File**: `config/settings.py`
**Location**: Add after `MAX_CONCURRENT_API_CALLS`
**Action**: INSERT

```python
# OCR Configuration - Simple with production safety
OCR_ENABLED = os.getenv("OCR_ENABLED", "true").lower() == "true"
OCR_THRESHOLD = int(os.getenv("OCR_THRESHOLD", "400"))
OCR_MAX_PAGES = int(os.getenv("OCR_MAX_PAGES", "2"))
```

### Step 2: Create Production-Safe OCR Service
**File**: `services/ocr_service.py` (NEW FILE)
**Action**: CREATE

```python
"""
Production-ready OCR service with memory-safe tiling.
Simple trigger rule: low text → OCR with proven 3x3 @ 600 DPI.
"""
import base64
import logging
import pymupdf as fitz  # Match repo's import style
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Fixed configuration (proven to work)
GRID = 3  # 3x3 tiling
DPI = 600  # High quality
MODEL = "gpt-4o"  # Best OCR model
TOKENS_PER_TILE = 1000  # Enough for construction text


async def ocr_page_with_tiling(
    client: AsyncOpenAI,
    pdf_path: str,
    page_num: int
) -> str:
    """
    Memory-safe tiling OCR. Renders each tile directly (no giant page pixmap).
    Uses PDF coordinates for correct tile boundaries.
    """
    with fitz.open(pdf_path) as doc:
        if page_num >= len(doc):
            return ""
            
        page = doc[page_num]
        
        # Check if page already has text
        existing_text = page.get_text("text").strip()
        if len(existing_text) > 1000:
            logger.info(f"Page {page_num + 1} has {len(existing_text)} chars, skipping OCR")
            return ""
        
        logger.info(f"Page {page_num + 1} has {len(existing_text)} chars, running 3x3 OCR")
        
        # PDF coordinates (not pixels!)
        page_rect = page.rect
        tile_width = page_rect.width / GRID
        tile_height = page_rect.height / GRID
        
        # DPI matrix
        matrix = fitz.Matrix(DPI / 72, DPI / 72)
        
        ocr_texts = []
        
        for row in range(GRID):
            for col in range(GRID):
                try:
                    # Calculate tile in PDF coordinates
                    x0 = page_rect.x0 + col * tile_width
                    y0 = page_rect.y0 + row * tile_height
                    x1 = min(x0 + tile_width, page_rect.x1)
                    y1 = min(y0 + tile_height, page_rect.y1)
                    tile_rect = fitz.Rect(x0, y0, x1, y1)
                    
                    # Render ONLY this tile (memory safe!)
                    tile_pix = page.get_pixmap(matrix=matrix, clip=tile_rect, alpha=False)
                    img_b64 = base64.b64encode(tile_pix.tobytes("png")).decode()
                    
                    # OCR with correct token parameter
                    response = await client.chat.completions.create(
                        model=MODEL,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "text", "text": "Extract ALL text from this construction drawing section:"},
                                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}}
                            ]
                        }],
                        temperature=0,
                        max_completion_tokens=TOKENS_PER_TILE  # CRITICAL: correct parameter name
                    )
                    
                    text = response.choices[0].message.content
                    if text and text.strip():
                        ocr_texts.append(text.strip())
                        
                except Exception as e:
                    logger.warning(f"Tile {row},{col} failed: {e}")
        
        if ocr_texts:
            return "\n\n".join(ocr_texts)
        return ""


async def run_ocr_if_needed(
    client: AsyncOpenAI,
    pdf_path: str,
    current_text: str,
    threshold: int = 400,
    max_pages: int = 2
) -> str:
    """
    Simple decision: If text below threshold, OCR up to max_pages.
    
    Returns:
        OCR text to append, or empty string
    """
    current_chars = len(current_text.strip())
    
    if current_chars >= threshold:
        logger.info(f"Sufficient text ({current_chars} chars), skipping OCR")
        return ""
    
    logger.info(f"Low text ({current_chars} chars), running OCR")
    
    ocr_results = []
    
    # Simple: just OCR first N pages
    for page_num in range(max_pages):
        try:
            page_text = await ocr_page_with_tiling(client, pdf_path, page_num)
            if page_text:
                ocr_results.append(f"[OCR Page {page_num + 1}]:\n{page_text}")
        except Exception as e:
            logger.warning(f"OCR failed for page {page_num + 1}: {e}")
            # Continue with other pages
    
    if ocr_results:
        return "\n\n=== OCR EXTRACTED CONTENT ===\n\n" + "\n\n".join(ocr_results)
    
    return ""
```

### Step 3: Update File Processor
**File**: `processing/file_processor.py`
**Location**: In `_step_extract_content`, right after `extraction_result` is set
**Action**: ADD this block before the `has_content` check

```python
# OCR augmentation when needed
from config.settings import OCR_ENABLED, OCR_THRESHOLD, OCR_MAX_PAGES

if OCR_ENABLED:
    try:
        from services.ocr_service import run_ocr_if_needed
        
        ocr_text = await run_ocr_if_needed(
            client=self.client,
            pdf_path=self.pdf_path,
            current_text=extraction_result.raw_text,
            threshold=OCR_THRESHOLD,
            max_pages=OCR_MAX_PAGES
        )
        
        if ocr_text:
            extraction_result.raw_text += ocr_text
            extraction_result.has_content = True
            self.logger.info(f"OCR added {len(ocr_text)} characters")
            
    except Exception as e:
        self.logger.warning(f"OCR failed (continuing): {e}")
```

### Step 4: Add to .env.example
**File**: `.env.example`
**Location**: At the end
**Action**: ADD

```bash
# OCR Settings (Simple + Safe)
OCR_ENABLED=true      # Enable/disable OCR
OCR_THRESHOLD=400     # Run OCR if chars below this
OCR_MAX_PAGES=2       # Max pages to OCR (cost control)
```

---

## What This Fixes

### Memory Safety ✅
- **Before**: 24"×36" @ 600 DPI = 1.2GB pixmap = OOM
- **After**: Each tile ~140MB = safe

### API Compatibility ✅
- **Before**: `max_tokens` = 400 error with GPT-4o
- **After**: `max_completion_tokens` = works

### Coordinate Accuracy ✅
- **Before**: Pixel math on PDF = wrong tile boundaries
- **After**: PDF coordinates = correct tiles

### Simplicity ✅
- Only 3 config options (not 8+)
- Fixed proven values for grid/DPI/model
- One simple trigger rule

---

## Testing

```bash
# Test with low-text drawing
python main.py input/ output/

# Should see in logs:
# "Low text (XXX chars), running OCR"
# "Page 1 has XXX chars, running 3x3 OCR"

# To disable:
OCR_ENABLED=false python main.py input/ output/
```

---

## For Claude Code

Tell Claude Code:
1. This fixes critical production issues while keeping it simple
2. The coordinate and memory fixes are REQUIRED
3. Use `max_completion_tokens` not `max_tokens`
4. Keep the import style consistent with the repo (`pymupdf as fitz`)

This implementation is production-ready AND simple. Works for all drawing types, won't crash on large drawings, and uses the correct API parameters.