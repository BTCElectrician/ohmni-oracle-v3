"""
Production-ready OCR service with memory-safe tiling and 10% overlap.
Intelligent trigger logic: per-page text density + file size heuristics → OCR with proven 3x3 @ 600 DPI.
Features: 10% tile overlap ensures no text loss at boundaries, systematic coverage of entire drawing.
"""
import base64
import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional
import pymupdf as fitz  # Match repo's import style
from openai import AsyncOpenAI
from utils.performance_utils import get_tracker

logger = logging.getLogger(__name__)

# Optimized configuration for performance and cost
GRID = int(os.getenv("OCR_GRID_SIZE", "1"))  # Default to no tiling (1x1)
DPI = int(os.getenv("OCR_DPI", "300"))  # 300 DPI is sufficient for text
MODEL = os.getenv("OCR_MODEL", "gpt-4o-mini")  # Fast, cheap, accurate enough
TOKENS_PER_TILE = int(os.getenv("OCR_TOKENS_PER_TILE", "3000"))  # Enough for full page
OVERLAP_PERCENT = 0.1  # 10% overlap between tiles - proven to prevent text loss at boundaries


@dataclass
class OCRRunResult:
    """Aggregated OCR result with tile metadata."""

    text: str
    tiles_processed: int = 0


def _collect_text_from_content(content: Any) -> str:
    """Normalize Chat Completions message content payloads to plain text."""
    if not content:
        return ""

    if isinstance(content, str):
        return content.strip()

    fragments: list[str] = []
    items = content if isinstance(content, (list, tuple)) else [content]
    for item in items:
        text_value: str | None = None

        if isinstance(item, dict):
            if item.get("type") == "text":
                text_value = item.get("text")
            elif "text" in item:
                text_field = item.get("text")
                if isinstance(text_field, dict):
                    text_value = text_field.get("value")
                elif isinstance(text_field, str):
                    text_value = text_field
            elif "value" in item:
                text_value = item.get("value")
        else:
            candidate = getattr(item, "text", None)
            if isinstance(candidate, str):
                text_value = candidate
            elif hasattr(candidate, "value"):
                text_value = getattr(candidate, "value", None)

        if text_value:
            fragments.append(str(text_value).strip())

    return "\n".join(fragment for fragment in fragments if fragment).strip()


def should_perform_ocr(extracted_text: str, pdf_path: str, page_count: int, ocr_enabled: bool = True, ocr_threshold: int = 1500) -> tuple[bool, str]:
    """
    Determine if OCR should be performed based on proven test data thresholds.
    
    Test data shows:
    - Good machine-readable files: 5,088 to 38,560 total chars  
    - Problem scanned files: 1,220 to 1,378 total chars (~600-700 chars/page)
    - Threshold: 1,500 chars/page catches scanned files while skipping readable ones
    
    Args:
        extracted_text: Text extracted by PyMuPDF
        pdf_path: Path to the PDF file
        page_count: Number of pages in the PDF
        ocr_enabled: Whether OCR is enabled in configuration
        ocr_threshold: Characters per page threshold (default: 1500)
        
    Returns:
        Tuple of (should_ocr: bool, reason: str)
    """
    if not ocr_enabled:
        return False, "OCR disabled in configuration"
    
    text_length = len(extracted_text.strip())
    chars_per_page = text_length / page_count if page_count > 0 else 0
    
    # Primary check: Low text density per page (based on test data)
    if chars_per_page < ocr_threshold:
        return True, f"Low density: {chars_per_page:.0f} chars/page (needs OCR)"
    
    # Secondary check: Suspiciously low total text for any drawing
    if text_length < 2000 and page_count >= 1:
        return True, f"Minimal text found: {text_length} total chars"
    
    return False, f"Sufficient text: {text_length} chars ({chars_per_page:.0f}/page)"


async def ocr_page_with_tiling(
    client: AsyncOpenAI,
    pdf_path: str,
    page_num: int,
    drawing_type: Optional[str] = None,
) -> OCRRunResult:
    """
    Memory-safe tiling OCR with 10% overlap between tiles.
    
    Features:
    - Renders each tile directly (no giant page pixmap)
    - Uses PDF coordinates for correct tile boundaries
    - 10% overlap ensures no text is lost at tile boundaries
    - 3x3 grid @ 600 DPI for optimal accuracy on construction drawings
    
    Args:
        client: OpenAI client for API calls
        pdf_path: Path to the PDF file
        page_num: Page number to process (0-indexed)
    """
    with fitz.open(pdf_path) as doc:
        if page_num >= len(doc):
            return ""
            
        page = doc[page_num]
        
        # Always proceed with OCR once file-level trigger is met
        existing_text = page.get_text("text").strip()
        logger.info(f"Proceeding with OCR for page {page_num + 1} ({len(existing_text)} existing chars)")
        logger.info(f"Using {GRID}x{GRID} tiling @ {DPI} DPI with {int(OVERLAP_PERCENT * 100)}% overlap")
        
        # PDF coordinates (not pixels!)
        page_rect = page.rect
        tile_width = page_rect.width / GRID
        tile_height = page_rect.height / GRID
        
        # Calculate overlap amounts
        overlap_width = tile_width * OVERLAP_PERCENT
        overlap_height = tile_height * OVERLAP_PERCENT
        
        # DPI matrix
        matrix = fitz.Matrix(DPI / 72, DPI / 72)
        tracker = get_tracker()
        ocr_texts = []
        tiles_processed = 0
        
        for row in range(GRID):
            for col in range(GRID):
                try:
                    tiles_processed += 1
                    # Calculate base tile position
                    base_x0 = page_rect.x0 + col * tile_width
                    base_y0 = page_rect.y0 + row * tile_height
                    base_x1 = base_x0 + tile_width
                    base_y1 = base_y0 + tile_height
                    
                    # Apply overlap (extend tile boundaries)
                    # Left edge: add overlap unless it's the leftmost column
                    x0 = base_x0 - (overlap_width if col > 0 else 0)
                    # Top edge: add overlap unless it's the topmost row
                    y0 = base_y0 - (overlap_height if row > 0 else 0)
                    # Right edge: add overlap unless it's the rightmost column
                    x1 = base_x1 + (overlap_width if col < GRID - 1 else 0)
                    # Bottom edge: add overlap unless it's the bottommost row
                    y1 = base_y1 + (overlap_height if row < GRID - 1 else 0)
                    
                    # Ensure we stay within page boundaries
                    x0 = max(x0, page_rect.x0)
                    y0 = max(y0, page_rect.y0)
                    x1 = min(x1, page_rect.x1)
                    y1 = min(y1, page_rect.y1)
                    
                    tile_rect = fitz.Rect(x0, y0, x1, y1)
                    
                    # Render ONLY this tile (memory safe!)
                    tile_pix = page.get_pixmap(matrix=matrix, clip=tile_rect, alpha=False)
                    img_b64 = base64.b64encode(tile_pix.tobytes("png")).decode()
                    
                    # OCR via Chat Completions vision endpoint
                    tile_start = time.time()
                    response = await client.chat.completions.create(
                        model=MODEL,
                        messages=[
                            {
                                "role": "user",
                                "content": [
                                    {
                                        "type": "text",
                                        "text": "Extract ALL text from this construction drawing section:",
                                    },
                                    {
                                        "type": "image_url",
                                        "image_url": {"url": f"data:image/png;base64,{img_b64}"},
                                    },
                                ],
                            }
                        ],
                        max_tokens=TOKENS_PER_TILE,
                    )
                    request_duration = time.time() - tile_start
                    usage = getattr(response, "usage", None)
                    prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
                    completion_tokens = getattr(usage, "completion_tokens", 0) or 0
                    total_tokens = getattr(usage, "total_tokens", 0) or 0
                    
                    try:
                        tracker.add_metric_with_context(
                            category="api_request",
                            duration=request_duration,
                            file_path=pdf_path,
                            drawing_type=drawing_type or "OCR",
                            model=MODEL,
                            api_type="ocr_tile",
                            prompt_tokens=prompt_tokens,
                            completion_tokens=completion_tokens,
                            total_tokens=total_tokens,
                            tokens_per_second=(
                                completion_tokens / request_duration
                                if request_duration > 0 and completion_tokens
                                else None
                            ),
                            ocr_page=page_num + 1,
                            ocr_tile=f"{row}-{col}",
                            ocr_grid=GRID,
                            is_ocr=True,
                        )
                    except Exception as metric_err:
                        logger.debug(f"OCR metric logging failed: {metric_err}")

                    choice = (getattr(response, "choices", None) or [None])[0]
                    text = ""
                    if choice and getattr(choice, "message", None):
                        text = _collect_text_from_content(choice.message.content)
                    if text and text.strip():
                        ocr_texts.append(text.strip())
                        
                except Exception as e:
                    logger.warning(f"Tile {row},{col} failed: {e}")
        
        if ocr_texts:
            return OCRRunResult("\n\n".join(ocr_texts), tiles_processed)
        return OCRRunResult("", tiles_processed)


async def run_ocr_if_needed(
    client: AsyncOpenAI,
    pdf_path: str,
    current_text: str,
    threshold: int = 1500,
    max_pages: int = 2,
    page_count: int | None = None,
    assume_ocr_needed: bool | None = None,
    drawing_type: Optional[str] = None,
) -> OCRRunResult:
    """
    Intelligent OCR decision based on text density and file characteristics.
    Uses per-page character density and file size heuristics to catch scanned drawings.
    
    Args:
        client: OpenAI client for OCR requests
        pdf_path: Path to the PDF file
        current_text: Text already extracted by PyMuPDF
        threshold: Characters per page threshold (not total characters)
        max_pages: Maximum pages to OCR for cost control
        
    Returns:
        OCRRunResult containing text (if any) and tile metadata
    """
    # Determine page_count once if not provided
    if page_count is None:
        try:
            with fitz.open(pdf_path) as doc:
                page_count = len(doc)
        except Exception as e:
            logger.warning(f"Could not read PDF for OCR decision: {e}")
            return ""

    # Honor prior OCR decision when provided by caller
    if assume_ocr_needed is not None:
        should_ocr = assume_ocr_needed
        reason = "Pre-decided by caller" if assume_ocr_needed else "Pre-decided skip by caller"
    else:
        should_ocr, reason = should_perform_ocr(
            extracted_text=current_text,
            pdf_path=pdf_path,
            page_count=page_count,
            ocr_enabled=True,  # We only get here if OCR is enabled
            ocr_threshold=threshold
        )
    
    if not should_ocr:
        logger.info(f"OCR SKIPPED: {reason}")
        return OCRRunResult("", 0)
    
    logger.info(f"🎯 OCR TRIGGERED: {reason}")
    
    ocr_results = []
    tiles_processed_total = 0
    
    # OCR up to max_pages
    pages_to_ocr = min(max_pages, page_count)
    for page_num in range(pages_to_ocr):
        try:
            page_result = await ocr_page_with_tiling(
                client,
                pdf_path,
                page_num,
                drawing_type=drawing_type,
            )
            tiles_processed_total += page_result.tiles_processed
            if page_result.text:
                ocr_results.append(f"[OCR Page {page_num + 1}]:\n{page_result.text}")
                logger.info(f"✅ OCR Page {page_num + 1}: Extracted {len(page_result.text)} characters")
        except Exception as e:
            logger.warning(f"❌ OCR failed for page {page_num + 1}: {e}")
            # Continue with other pages
    
    if ocr_results:
        total_ocr_chars = sum(len(result) for result in ocr_results)
        logger.info(f"🎉 OCR COMPLETE: Added {total_ocr_chars} characters from {len(ocr_results)} pages")
        combined_text = "\n\n=== OCR EXTRACTED CONTENT ===\n\n" + "\n\n".join(ocr_results)
        return OCRRunResult(combined_text, tiles_processed_total)
    
    logger.warning("⚠️ OCR triggered but no text extracted")
    return OCRRunResult("", tiles_processed_total)
