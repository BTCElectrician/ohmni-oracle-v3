# Cursor Instructions: Update Title Block Extraction in extraction_service.py

Please modify the file `services/extraction_service.py` according to these instructions:

## Step 1: REPLACE Existing Method

Find the existing method `_extract_titleblock_region_text` in the `PyMuPdfExtractor` class (around lines 40-80) and REPLACE it entirely with this new version:

```python
def _extract_titleblock_region_text(self, doc: fitz.Document, page_num: int) -> str:
    """
    Extract title block with progressive expansion if truncated.
    Handles rotated pages and various title block positions.
    """
    if page_num < 0 or page_num >= len(doc):
        self.logger.warning(f"Page number {page_num} out of range (0-{len(doc)-1})")
        return ""

    page = doc[page_num]
    page_rect = page.rect
    
    # Handle page rotation
    rotation = page.rotation
    is_rotated = rotation in (90, 270)
    
    # Define search regions based on orientation
    # Format: (x0_pct, y0_pct, x1_pct, y1_pct, name)
    if is_rotated:
        regions = [
            (0.00, 0.70, 0.30, 1.00, "left_strip"),     # Left strip for rotated
            (0.70, 0.60, 1.00, 1.00, "bottom_right"),   # Adjusted bottom-right
        ]
    else:
        regions = [
            (0.70, 0.00, 1.00, 1.00, "right_strip"),    # Right vertical strip
            (0.60, 0.70, 1.00, 1.00, "bottom_right"),   # Bottom-right corner
            (0.00, 0.85, 1.00, 1.00, "bottom_strip"),   # Bottom horizontal strip
        ]
    
    best_text = ""
    best_score = 0.0
    best_region_name = ""
    
    for x0_pct, y0_pct, x1_pct, y1_pct, region_name in regions:
        # Try progressively larger regions if we need to expand leftward
        expansions = [0.0]
        if x0_pct > 0.5:  # Only expand regions that start from right side
            expansions.extend([0.10, 0.20])
        
        for expansion in expansions:
            # Apply expansion
            x0_expanded = max(0, x0_pct - expansion)
            
            # Create extraction rectangle
            rect = fitz.Rect(
                page_rect.width * x0_expanded,
                page_rect.height * y0_pct,
                page_rect.width * x1_pct,
                page_rect.height * y1_pct
            )
            
            # Extract text from region
            try:
                text = page.get_text("text", clip=rect).strip()
            except Exception as e:
                self.logger.warning(f"Error extracting from region {region_name}: {e}")
                continue
            
            if not text or len(text) < 50:
                continue
            
            # Score the extracted text
            score = self._score_titleblock_text(text)
            
            # Check if this is our best candidate so far
            if score > best_score:
                best_text = text
                best_score = score
                best_region_name = f"{region_name}_exp{int(expansion*100)}"
            
            # Early exit if we found high-quality, non-truncated text
            if score >= 0.8 and not self._looks_truncated(text):
                self.logger.info(
                    f"High-quality title block found in {region_name} "
                    f"(expansion: {int(expansion*100)}%, "
                    f"chars: {len(text)}, score: {score:.2f})"
                )
                return text
            
            # If text looks truncated and we can expand more, continue
            if self._looks_truncated(text) and expansion < 0.20:
                continue
                
    # Log what we found
    if best_text:
        self.logger.info(
            f"Best title block from {best_region_name}: "
            f"{len(best_text)} chars, score: {best_score:.2f}, "
            f"truncated: {self._looks_truncated(best_text)}"
        )
    else:
        self.logger.warning(f"No title block found on page {page_num}")
    
    return best_text
```

## Step 2: ADD New Helper Methods

Add these three new methods to the same `PyMuPdfExtractor` class (you can add them right after the method you just replaced):

### Method 1: _score_titleblock_text

```python
def _score_titleblock_text(self, text: str) -> float:
    """
    Score text likelihood of being a title block (0.0-1.0).
    Higher scores indicate more confidence it's a title block.
    """
    if not text:
        return 0.0
    
    score = 0.0
    text_upper = text.upper()
    
    # Keywords commonly found in title blocks with their weights
    keywords = {
        'PROJECT': 0.25,
        'SHEET': 0.15,
        'DRAWING': 0.10,
        'DATE': 0.10,
        'DRAWN': 0.10,
        'CHECKED': 0.10,
        'APPROVED': 0.10,
        'SCALE': 0.10,
        'TITLE': 0.15,
        'JOB': 0.10,
        'NO': 0.05,
        'NUMBER': 0.05,
        'REVISION': 0.10,
        'REV': 0.05,
        'CLIENT': 0.10,
        'ARCHITECT': 0.10,
        'ENGINEER': 0.10,
        'CONTRACTOR': 0.10
    }
    
    # Add points for each keyword found
    for keyword, weight in keywords.items():
        if keyword in text_upper:
            score += weight
    
    # Bonus for ideal length range (title blocks are typically 200-2000 chars)
    text_length = len(text)
    if 200 <= text_length <= 500:
        score += 0.25
    elif 500 < text_length <= 1000:
        score += 0.20
    elif 1000 < text_length <= 2000:
        score += 0.15
    elif text_length > 2000:
        score += 0.05
    
    # Check for drawing number patterns (e.g., E5.00, A-101, M601)
    drawing_patterns = [
        r'[A-Z]{1,3}[-.]?\d{1,3}(?:\.\d{1,3})?[A-Z]?',  # E5.00, A-101, M601A
        r'SHEET\s*:?\s*[A-Z0-9]',                         # SHEET: A101
        r'DWG\.?\s*NO\.?\s*:?\s*[A-Z0-9]',              # DWG NO: E5
    ]
    
    for pattern in drawing_patterns:
        if re.search(pattern, text_upper):
            score += 0.15
            break
    
    # Penalty if text appears truncated
    if self._looks_truncated(text):
        score *= 0.7
    
    # Normalize score to 0-1 range
    return min(score, 1.0)
```

### Method 2: _looks_truncated

```python
def _looks_truncated(self, text: str) -> bool:
    """
    Detect if text appears to be truncated.
    Returns True if the text seems to be cut off mid-word or mid-sentence.
    """
    if not text or len(text) < 50:
        return False
    
    text = text.rstrip()
    
    # Clear truncation indicators
    if text.endswith(('-', '/', '\\', '...')):
        return True
    
    # Check if ends with ellipsis pattern
    if re.search(r'\.\s*\.\s*\.$', text):
        return True
    
    # Get the last word
    words = text.split()
    if not words:
        return False
    
    last_word = words[-1].rstrip('.,;:!?')
    
    # Common short words that are valid endings (not truncated)
    valid_short_endings = {
        # Articles, prepositions, conjunctions
        'a', 'an', 'as', 'at', 'by', 'do', 'go', 'he', 'if', 'in', 'is', 'it', 
        'me', 'my', 'no', 'of', 'on', 'or', 'so', 'to', 'up', 'us', 'we',
        'for', 'the', 'and', 'but', 'nor', 'yet', 'all', 'any', 'are', 'can',
        'had', 'has', 'her', 'him', 'his', 'its', 'may', 'not', 'one', 'our',
        'out', 'she', 'too', 'two', 'was', 'who', 'why', 'you',
        # Common abbreviations
        'inc', 'llc', 'ltd', 'co', 'corp', 'st', 'rd', 'ave', 'dr', 'ct', 'ln',
        'blvd', 'pkwy', 'hwy', 'ft', 'sq', 'mi', 'km', 'mm', 'cm', 'm',
        # Common drawing terms
        'no', 'yes', 'ok', 'na', 'tbd', 'typ', 'min', 'max', 'ref', 'rev',
        'dwg', 'sht', 'det', 'elev', 'sect', 'plan', 'schd', 'diag',
        # Months
        'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'
    }
    
    # Check if it's a valid short word
    if last_word.lower() in valid_short_endings:
        return False
    
    # Check for incomplete words (all caps, 1-4 letters)
    if len(last_word) <= 4 and last_word.isalpha() and last_word.isupper():
        # But exclude common abbreviations that are all caps
        common_caps = {'USA', 'LLC', 'INC', 'ASAP', 'HVAC', 'MEP', 'ADA', 'NEC', 'IBC'}
        if last_word not in common_caps:
            return True
    
    # Check for incomplete alphanumeric codes (like "E5-0" instead of "E5-01")
    if re.match(r'^[A-Z]{1,3}\d{0,2}[-.]?$', last_word):
        return True
    
    # Check if the text ends mid-sentence (no proper punctuation)
    last_char = text[-1]
    if last_char.isalnum() and len(text) < 300:
        # Short text ending with alphanumeric might be truncated
        # But only if it's not ending with a common abbreviation
        if not any(text.upper().endswith(abbr.upper()) for abbr in valid_short_endings):
            return True
    
    return False
```

### Method 3: _extract_project_name_from_titleblock (OPTIONAL but recommended)

```python
def _extract_project_name_from_titleblock(self, titleblock_text: str) -> Tuple[Optional[str], str, bool]:
    """
    Extract project name from title block text with source tracking.
    Returns: (project_name, source, is_truncated)
    """
    if not titleblock_text:
        return None, "not_found", False
    
    project_name = None
    source = "not_found"
    
    # Try to find labeled project name
    patterns = [
        (r'PROJECT\s*(?:NAME)?\s*:?\s*([^\n\r]+)', "project_label"),
        (r'TITLE\s*:?\s*([^\n\r]+)', "title_label"),
        (r'JOB\s*(?:NAME)?\s*:?\s*([^\n\r]+)', "job_label"),
        (r'(?:^|\n)([A-Z][A-Z\s\-&]+(?:PROJECT|BUILDING|CENTER|FACILITY|COMPLEX|TOWER|PLAZA))', "inferred"),
    ]
    
    for pattern, pattern_source in patterns:
        match = re.search(pattern, titleblock_text, re.IGNORECASE | re.MULTILINE)
        if match:
            candidate = match.group(1).strip(": -\t")
            # Clean up the project name
            candidate = re.sub(r'\s+', ' ', candidate)  # Normalize whitespace
            candidate = candidate.strip()
            
            if candidate and len(candidate) > 3:
                project_name = candidate
                source = pattern_source
                break
    
    # Check if the found project name appears truncated
    is_truncated = False
    if project_name:
        last_word = project_name.split()[-1] if project_name.split() else ""
        if last_word and len(last_word) <= 4 and last_word.isalpha() and last_word.isupper():
            # Check if it's not a valid abbreviation
            valid_abbrevs = {'LLC', 'INC', 'CORP', 'LTD', 'ASSN', 'INTL', 'NATL', 'BLDG'}
            if last_word not in valid_abbrevs:
                is_truncated = True
    
    return project_name, source, is_truncated
```

## Step 3: Add Required Imports

Make sure these imports are at the top of the file (they should already be there, but verify):

```python
import re
from typing import Optional, Dict, Any, Tuple
```

## IMPORTANT NOTES:
- Do NOT delete or modify any other methods in the file
- Keep all existing classes (ArchitecturalExtractor, ElectricalExtractor, etc.) intact
- The changes only affect the `PyMuPdfExtractor` class
- The file should remain approximately 600+ lines after changes