"""
AI service for processing drawing content using the Chat Completions API.
"""
import json
import logging
import time
import os
import re
import asyncio
import uuid
from typing import Dict, Any, Optional, TypeVar, Generic, List
from openai import AsyncOpenAI
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from utils.performance_utils import time_operation, time_operation_context, get_tracker
from utils.drawing_utils import detect_drawing_info
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
from utils.exceptions import AIProcessingError, JSONValidationError
from config.settings import get_enable_metadata_repair
from utils.ai_cache import load_cache, save_cache

# Initialize logger at module level
logger = logging.getLogger(__name__)

# Chat Completions configuration

# Additional environment variables for stability
RESPONSES_TIMEOUT_SECONDS = int(os.getenv("RESPONSES_TIMEOUT_SECONDS", "200"))
SCHEDULES_ENABLED = os.getenv("SCHEDULES_ENABLED", "false").lower() == "true"
# Deprecated: do not read at import time; use dynamic getter instead
# ENABLE_METADATA_REPAIR = os.getenv("ENABLE_METADATA_REPAIR", "true").lower() == "true"



def _is_schedule_or_spec(drawing_type: Optional[str], pdf_path: Optional[str]) -> bool:
    dt = (drawing_type or "").lower()
    name = os.path.basename(pdf_path or "").lower()
    return any([
        "panel" in dt or "schedule" in dt,
        "schedule" in name or "panel" in name,
        "spec" in dt or "specification" in dt,
        "spec" in name or "specification" in name,
    ])

# Lean JSON extractor instructions used ONLY as Responses API instructions
JSON_EXTRACTOR_INSTRUCTIONS = """
You are an expert in construction-document extraction. Transform the user's input
(raw text from a single drawing) into ONE valid JSON object ONLY (no markdown,
no code fences, no commentary).

Requirements:
- Capture EVERYTHING. Preserve exact values. Use null where unknown.
- Top-level keys: DRAWING_METADATA + one MAIN_CATEGORY (ARCHITECTURAL | ELECTRICAL | MECHANICAL | PLUMBING | OTHER).
- Schedules → arrays of row objects. Specs/notes → keep hierarchy.
- If ARCHITECTURAL floor plan: include ARCHITECTURAL.ROOMS[] with room_number, room_name, dimensions.
- Return ONLY the JSON.
"""

# Focused instructions for metadata repair - reduces tokens and improves accuracy
METADATA_REPAIR_INSTRUCTIONS = """
Extract drawing metadata from title block text. Return JSON with one key "DRAWING_METADATA" containing:
drawing_number, title, date, revision, project_name, job_number, scale, discipline, drawn_by, checked_by.
Use null for missing fields.
"""



def _strip_json_fences(s: str) -> str:
    """Strip JSON code fences from string to prevent parsing errors."""
    if not s:
        return s
    m = re.match(r"^```(?:json)?\s*(.*)```$", s.strip(), re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else s


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

    # Project name fallback hierarchy
    if not metadata.get("project_name"):
        # Try 1: Use project address street name if available
        if metadata.get("project_address"):
            street_match = re.search(r'\d+\s+([A-Z\s]+)(?:\s+(?:BLVD|DR|ST|AVE|RD|WAY|LN|CT|PL))', 
                                    metadata["project_address"], re.IGNORECASE)
            if street_match:
                street_name = street_match.group(1).strip().title()
                job_no = metadata.get("job_no") or metadata.get("job_number") or ""
                metadata["project_name"] = f"{street_name} {job_no}".strip()
                metadata["project_name_source"] = "derived_from_address"
                logger.info(f"Derived project name from address: {metadata['project_name']}")
        
        # Try 2: Use job number as last resort
        if not metadata.get("project_name"):
            job_no = metadata.get("job_no") or metadata.get("job_number")
            if job_no:
                metadata["project_name"] = f"Project {job_no}"
                metadata["project_name_source"] = "derived_from_job_no"
                logger.info(f"Used job number as project name: {metadata['project_name']}")

    return metadata
# =====================================================


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=3, max=8),
    retry=retry_if_exception_type((AIProcessingError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def make_chat_completion_request(
    client: AsyncOpenAI,
    input_text: str,
    model: str,
    temperature: float,
    max_tokens: int,
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
    instructions: Optional[str] = None,
) -> str:
    """
    Make a Chat Completions API request with standard parameters.
    """
    start_time = time.time()
    
    try:
        # Build messages
        system_message = instructions or JSON_EXTRACTOR_INSTRUCTIONS
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": input_text}
        ]
        
        # Build API parameters (GPT-4.1 supports temperature and max_tokens)
        api_params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        
        # Make the API call
        response = await asyncio.wait_for(
            client.chat.completions.create(**api_params),
            timeout=RESPONSES_TIMEOUT_SECONDS
        )
        
        # Extract content
        content = response.choices[0].message.content
        
        if not content:
            raise AIProcessingError("Empty response from Chat Completions API")
        
        # Log metrics
        request_time = time.time() - start_time
        usage = response.usage
        
        if usage:
            logger.info(
                f"Token usage - Input: {usage.prompt_tokens}, "
                f"Output: {usage.completion_tokens}"
            )
        
        # Track performance
        tracker = get_tracker()
        tracker.add_metric_with_context(
            category="api_request",
            duration=request_time,
            file_path=file_path,
            drawing_type=drawing_type,
            model=model,
            api_type="chat"
        )
        
        logger.info(
            f"Chat Completions request completed in {request_time:.2f}s "
            f"for {os.path.basename(file_path) if file_path else 'unknown'}"
        )
        
        return content
        
    except asyncio.TimeoutError:
        request_time = time.time() - start_time
        logger.error(f"Chat Completions timeout after {request_time:.2f}s")
        raise AIProcessingError(f"Timeout after {RESPONSES_TIMEOUT_SECONDS}s")
        
    except Exception as e:
        request_time = time.time() - start_time
        logger.error(f"Chat Completions error: {str(e)} after {request_time:.2f}s")
        raise AIProcessingError(f"Chat Completions request failed: {str(e)}")


def optimize_model_parameters(
    drawing_type: str, raw_content: str, pdf_path: str
) -> Dict[str, Any]:
    """
    Determine optimal model parameters based on drawing type and content.
    """
    content_length = len(raw_content) if raw_content else 0
    
    # Detect if this is a schedule OR a specification
    is_schedule = _is_schedule_or_spec(drawing_type, pdf_path)
    
    # Get force mini override status
    force_mini = get_force_mini_model()
    
    # PRIORITY 1: Schedules/specs use appropriate model with sufficient tokens
    if is_schedule:
        model = SCHEDULE_MODEL
        temperature = float(os.getenv("LARGE_MODEL_TEMP", str(LARGE_MODEL_TEMP))) if isinstance(LARGE_MODEL_TEMP, (int, float)) else float(os.getenv("LARGE_MODEL_TEMP", "0.2"))
        max_tokens = min(LARGE_MODEL_MAX_TOKENS, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        logger.info(f"Using schedule model for {content_length} char document")
    
    # PRIORITY 2: Force mini override for non-schedules
    elif force_mini:
        model = DEFAULT_MODEL
        temperature = float(os.getenv("DEFAULT_MODEL_TEMP", str(DEFAULT_MODEL_TEMP))) if isinstance(DEFAULT_MODEL_TEMP, (int, float)) else float(os.getenv("DEFAULT_MODEL_TEMP", "0.2"))
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Force-mini override active ({content_length} chars)")
    
    # PRIORITY 3: Size-based selection with optimized model choice
    elif content_length < NANO_CHAR_THRESHOLD:
        # Use nano for simple classification and basic extraction
        model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
        temperature = float(os.getenv("TINY_MODEL_TEMP", str(TINY_MODEL_TEMP))) if isinstance(TINY_MODEL_TEMP, (int, float)) else float(os.getenv("TINY_MODEL_TEMP", "0.2"))
        max_tokens = TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using nano model for simple extraction ({content_length} chars)")
    
    elif content_length < MINI_CHAR_THRESHOLD:
        # Use mini for structured schedules and repetitive tasks
        model = DEFAULT_MODEL
        temperature = float(os.getenv("DEFAULT_MODEL_TEMP", str(DEFAULT_MODEL_TEMP))) if isinstance(DEFAULT_MODEL_TEMP, (int, float)) else float(os.getenv("DEFAULT_MODEL_TEMP", "0.2"))
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using mini model for structured extraction ({content_length} chars)")
    
    else:
        # Use full model only for complex reasoning and multi-step tasks
        model = LARGE_DOC_MODEL
        temperature = float(os.getenv("LARGE_MODEL_TEMP", str(LARGE_MODEL_TEMP))) if isinstance(LARGE_MODEL_TEMP, (int, float)) else float(os.getenv("LARGE_MODEL_TEMP", "0.2"))
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for complex extraction ({content_length} chars)")
    
    # Check if this is a specification document first
    is_specification = (
        "spec" in drawing_type.lower() or 
        "specification" in drawing_type.lower() or
        "spec" in pdf_path.lower() or 
        "specification" in pdf_path.lower()
    )
    
    # Special handling for specification documents
    if is_specification:
        spec_max_tokens = int(os.getenv("SPEC_MAX_TOKENS", "16384"))
        max_tokens = min(max_tokens, spec_max_tokens)
        logger.info(f"Specification document detected - limiting to {max_tokens} tokens")
    
    # Token policy for NON-specification documents: keep large outputs reasonable to avoid timeouts
    elif model in [LARGE_DOC_MODEL, SCHEDULE_MODEL]:
        if content_length > 35000:
            max_tokens = min(12000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
            logger.info(f"Capping max_tokens to {max_tokens} for very large document")
        elif content_length > 25000:
            max_tokens = min(14000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
            logger.info(f"Setting max_tokens to {max_tokens} for large document")
        elif content_length > 15000:
            max_tokens = min(15000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        # else: use default max_tokens (16384)
    
    # Ensure we don't exceed provider limits
    max_tokens = min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
    
    params = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    # Log final selection with size bucket info
    size_bucket = "nano" if content_length < NANO_CHAR_THRESHOLD else \
                  "mini" if content_length < MINI_CHAR_THRESHOLD else "full"
    
    logger.info(
        f"Model: {params['model']}, Max tokens: {params['max_tokens']}, "
        f"Input: {content_length} chars"
    )
    
    return params


async def call_with_cache(
    client: AsyncOpenAI,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
    instructions: Optional[str] = None,
) -> Any:
    """
    Call Chat Completions API with optional caching.
    """
    # Extract prompt from messages
    prompt = messages[-1]["content"]
    system_message = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    
    # Prepare parameters for cache key
    params = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_type": "chat",
        "instructions": (instructions or ""),
    }
    
    # Try to load from cache
    cached_response = load_cache(prompt, params)
    if cached_response:
        return cached_response
    
    # Use Chat Completions API
    final_instructions = instructions or system_message or JSON_EXTRACTOR_INSTRUCTIONS
    
    content = await make_chat_completion_request(
        client=client,
        input_text=prompt,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        file_path=file_path,
        drawing_type=drawing_type,
        instructions=final_instructions,
    )
    
    # Save to cache
    save_cache(prompt, params, content)
    
    return content


T = TypeVar("T")


class AiResponse(Generic[T]):
    """Response from AI processing."""

    def __init__(
        self,
        success: bool = True,
        content: str = "",
        parsed_content: Optional[T] = None,
        error: str = "",
    ):
        self.success = success
        self.content = content
        self.parsed_content = parsed_content
        self.error = error

    def __str__(self):
        if self.success:
            return f"AiResponse: success={self.success}, content_length={len(self.content) if self.content else 0}"
        else:
            return f"AiResponse: success={self.success}, error={self.error}"


@time_operation("ai_processing")
async def process_drawing(
    raw_content: str, drawing_type: str, client: AsyncOpenAI, pdf_path: str = "", titleblock_text: Optional[str] = None
) -> str:
    """
    Process drawing content using AI to convert to structured JSON via the Chat Completions API.
    """
    if not raw_content:
        raise AIProcessingError("Cannot process empty content")

    from templates.prompt_registry import get_registry

    content_length = len(raw_content)
    logger.info(
        f"Processing {drawing_type} drawing with {content_length} chars for file {pdf_path}"
    )

    # Get main type and subtype
    main_type, subtype = detect_drawing_info(pdf_path)

    if not drawing_type or drawing_type == "General":
        drawing_type = main_type

    logger.info(f"Detected drawing info: main_type={main_type}, subtype={subtype}")
    logger.info(f"Using drawing_type={drawing_type} for prompt selection")

    # Get appropriate system message
    registry = get_registry()
    system_message = registry.get(drawing_type, subtype)

    if "json" not in system_message.lower():
        logger.warning(
            f"System message for {drawing_type}/{subtype} doesn't contain the word 'json' - adding it"
        )
        system_message += "\n\nFormat your entire response as a valid JSON object."

    logger.info(f"Prompt key used: {drawing_type}_{subtype if subtype else ''}")
    logger.info(f"API mode: Chat")

    # Get optimized model parameters
    params = optimize_model_parameters(drawing_type, raw_content, pdf_path)

    try:
        # Build Responses instructions by combining the system prompt and lean JSON helper
        responses_instructions = system_message + "\n\n" + JSON_EXTRACTOR_INSTRUCTIONS

        # Use the cache-aware function that routes to correct API
        content = await call_with_cache(
            client=client,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": raw_content},
            ],
            model=params["model"],
            temperature=params["temperature"],
            max_tokens=params["max_tokens"],
            file_path=pdf_path,
            drawing_type=drawing_type,
            instructions=responses_instructions,
        )

        # Validate JSON with timing
        try:
            with time_operation_context("json_parsing", file_path=pdf_path, drawing_type=drawing_type):
                content = _strip_json_fences(content)
                parsed = json.loads(content)
                
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
                
                # Check for potential truncation
                output_length = len(content)
                input_length = len(raw_content)
                
                current_max_tokens = params.get("max_tokens", ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
                estimated_output_tokens = output_length / 4
                token_usage_percent = (estimated_output_tokens / current_max_tokens) * 100 if current_max_tokens > 0 else 0
                
                if token_usage_percent > 90:
                    logger.warning(
                        f"Possible truncation: {token_usage_percent:.0f}% token usage. "
                        f"Input: {input_length} chars, Output: {output_length} chars, "
                        f"Max tokens: {current_max_tokens}"
                    )
                elif output_length < input_length * 0.5:
                    logger.warning(
                        f"Suspiciously small output: Input {input_length} chars → Output {output_length} chars"
                    )
                
                logger.info(
                    "Successfully processed drawing",
                    extra={
                        "drawing_type": drawing_type,
                        "output_length": len(content),
                        "estimated_tokens": int(estimated_output_tokens),
                        "token_usage_percent": f"{token_usage_percent:.0f}%",
                        "file": pdf_path,
                    },
                )
                return content
        except json.JSONDecodeError as e:
            logger.error(
                "JSON validation error",
                extra={"error": str(e), "drawing_type": drawing_type, "file": pdf_path},
            )

            # Attempt repair for mechanical schedules
            if "mechanical" in drawing_type.lower():
                from utils.json_utils import repair_panel_json

                logger.info("Attempting mechanical JSON repair")
                with time_operation_context("json_parsing", file_path=pdf_path, drawing_type=drawing_type):
                    repaired = repair_panel_json(content)
                    try:
                        json.loads(repaired)
                        return repaired
                    except json.JSONDecodeError:
                        pass

            logger.error(f"Invalid JSON snippet: {content[:500]}...")
            raise JSONValidationError(f"Invalid JSON output: {str(e)}")

    except Exception as e:
        logger.error(
            "Error processing drawing",
            extra={"error": str(e), "drawing_type": drawing_type, "file": pdf_path},
        )
        raise AIProcessingError(f"Error processing drawing: {str(e)}")


@time_operation("metadata_repair")
async def repair_metadata(
    titleblock_text: str, 
    client: AsyncOpenAI,
    pdf_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Extract metadata from title block text using focused AI prompt.
    Returns empty dict on failure to maintain pipeline resilience.
    
    Args:
        titleblock_text: Extracted text from title block region
        client: OpenAI client for API calls
        pdf_path: Optional path for logging context
        
    Returns:
        Dictionary of metadata fields or empty dict if repair fails
    """
    from config.settings import get_enable_metadata_repair
    
    # Check if feature is enabled
    if not get_enable_metadata_repair():
        logger.debug("Metadata repair disabled by configuration")
        return {}
    
    # Check if we have title block text to work with
    if not titleblock_text or len(titleblock_text.strip()) < 10:
        logger.debug("No title block text available for metadata repair")
        return {}

    try:
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
        
        # Get the specialized metadata repair prompt from registry
        from templates.prompt_registry import get_registry
        registry = get_registry()
        metadata_repair_prompt = registry._prompts.get("METADATA_REPAIR", METADATA_REPAIR_INSTRUCTIONS)
        
        # Make focused API call for metadata extraction
        content = await call_with_cache(
            client=client,
            messages=[
                {"role": "system", "content": metadata_repair_prompt},
                {"role": "user", "content": f"Extract metadata from:\n{titleblock_text}"},
            ],
            model=repair_model,
            temperature=0.0,  # Deterministic for consistent extraction
            max_tokens=800,   # Tight limit - metadata only needs ~200-300 tokens
            file_path=pdf_path,
            drawing_type="metadata_repair",
            instructions=metadata_repair_prompt,
        )

        # Parse and validate response
        content = _strip_json_fences(content)
        parsed = json.loads(content)
        metadata = parsed.get("DRAWING_METADATA", {})
        
        # Validate we got actual metadata
        if not isinstance(metadata, dict):
            logger.warning("Invalid metadata structure in repair response")
            return {}
        
        # Log success with key fields for monitoring
        if metadata:
            drawing_num = metadata.get('drawing_number', 'N/A')
            project = metadata.get('project_name', 'N/A')
            logger.info(f"✅ Metadata repaired: Drawing {drawing_num}, Project: {project}")
            
            # Track success metrics
            from utils.performance_utils import get_tracker
            tracker = get_tracker()
            tracker.add_metric(
                "metadata_repair_success",
                os.path.basename(pdf_path) if pdf_path else "unknown",
                "metadata_repair",
                1.0
            )
        
        return metadata
        
    except json.JSONDecodeError as e:
        logger.debug(f"JSON parse error in metadata repair: {str(e)}")
        return {}
    except Exception as e:
        logger.debug(f"Metadata repair failed: {str(e)}")
        return {}
