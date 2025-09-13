"""
AI service for processing drawing content using the unified Responses API (gpt-5).
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

# Responses API configuration

# Additional environment variables for stability
RESPONSES_TIMEOUT_SECONDS = int(os.getenv("RESPONSES_TIMEOUT_SECONDS", "200"))
ENABLE_GPT5_NANO = os.getenv("ENABLE_GPT5_NANO", "false").lower() == "true"
SCHEDULES_ENABLED = os.getenv("SCHEDULES_ENABLED", "false").lower() == "true"
# Deprecated: do not read at import time; use dynamic getter instead
# ENABLE_METADATA_REPAIR = os.getenv("ENABLE_METADATA_REPAIR", "true").lower() == "true"

# NEW: Stability toggles
GPT5_FAILURE_THRESHOLD = int(os.getenv("GPT5_FAILURE_THRESHOLD", "2"))
GPT5_DISABLE_ON_EMPTY_OUTPUT = os.getenv("GPT5_DISABLE_ON_EMPTY_OUTPUT", "true").lower() == "true"

# Circuit-breaker state (per-process)
_gpt5_failures = 0
_gpt5_circuit_open = False

def _gpt5_note_failure(reason: str = ""):
    global _gpt5_failures, _gpt5_circuit_open
    _gpt5_failures += 1
    logger.warning(f"GPT-5 failure {_gpt5_failures}/{GPT5_FAILURE_THRESHOLD} (reason: {reason})")
    if GPT5_DISABLE_ON_EMPTY_OUTPUT and _gpt5_failures >= GPT5_FAILURE_THRESHOLD:
        _gpt5_circuit_open = True
        logger.warning("GPT-5 circuit opened for remainder of run; suppressing further calls this run.")

def _gpt5_reset():
    global _gpt5_failures, _gpt5_circuit_open
    _gpt5_failures = 0
    _gpt5_circuit_open = False

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

def _validate_reasoning_effort() -> str:
    """Validate and return reasoning effort, default to 'minimal'."""
    raw = os.getenv("GPT5_REASONING_EFFORT", "minimal").strip()
    allowed = {"minimal", "low", "medium", "high"}
    
    # Strip any accidental inline comments
    if "#" in raw:
        raw = raw.split("#", 1)[0].strip()
    
    cleaned = raw.lower()
    if cleaned in allowed:
        return cleaned
    
    logger.warning(f"Invalid GPT5_REASONING_EFFORT='{raw}'. Using 'minimal'.")
    return "minimal"


def _strip_json_fences(s: str) -> str:
    """Strip JSON code fences from string to prevent parsing errors."""
    if not s:
        return s
    m = re.match(r"^```(?:json)?\s*(.*)```$", s.strip(), re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else s
# =====================================================


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

    # Detect if this is a schedule OR a specification (treat specs like schedules)
    is_schedule = _is_schedule_or_spec(drawing_type, pdf_path)

    # Get force mini override status
    force_mini = get_force_mini_model()

    # PRIORITY 1: Schedules/specs ALWAYS use schedule model regardless of size or overrides
    if is_schedule:
        model = SCHEDULE_MODEL
        temperature = 1.0
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using schedule model for schedule/spec document ({content_length} chars)")
    
    # PRIORITY 2: Force mini override for non-schedules (emergency cost control)
    elif force_mini:
        model = DEFAULT_MODEL
        temperature = 1.0
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Force-mini override active; using mini model for non-schedule ({content_length} chars)")
    
    # PRIORITY 3: Size-based bucket selection for normal operation
    elif content_length < NANO_CHAR_THRESHOLD:
        # Small documents < 3K chars: Use nano/tiny
        model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
        temperature = 1.0
        max_tokens = TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using nano/tiny model for small document ({content_length} chars)")
    
    elif content_length < MINI_CHAR_THRESHOLD:
        # Medium documents 3K-15K chars: Use mini
        model = DEFAULT_MODEL
        temperature = 1.0
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using mini model for medium document ({content_length} chars)")
    
    else:
        # Large documents > 15K chars: Use full model
        model = LARGE_DOC_MODEL
        temperature = 1.0
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for large document ({content_length} chars)")

    # Dynamic token allocation for large documents
    if model in [LARGE_DOC_MODEL, SCHEDULE_MODEL]:
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
        "temperature": 1.0,  # gpt-5 requires temperature omitted or set to 1
        "max_tokens": min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS),
    }

    # Log final selection with size bucket info
    size_bucket = "nano" if content_length < NANO_CHAR_THRESHOLD else \
                  "mini" if content_length < MINI_CHAR_THRESHOLD else "full"
    
    logger.info(
        f"Model selection: type={drawing_type}, length={content_length}, "
        f"bucket={size_bucket}, schedule={is_schedule}, force_mini={force_mini}, "
        f"model={params['model']}, temp={params['temperature']}, max_tokens={params['max_tokens']}"
    )
    return params


# ============== Responses API Request Function ==============
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=3, max=8),
    retry=retry_if_exception_type((AIProcessingError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def make_responses_api_request(
    client: AsyncOpenAI,
    input_text: str,
    model: str,
    temperature: float,
    max_tokens: int,
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
    instructions: Optional[str] = None,
) -> Any:
    start_time = time.time()
    try:
        # Ensure 'json' appears in the input payload when using text.format=json_object
        # Some providers require the literal word 'json' in the input messages.
        adjusted_input = input_text or ""
        if "json" not in adjusted_input.lower():
            adjusted_input = adjusted_input + "\n\nNOTE: Return output as JSON."

        params: Dict[str, Any] = {
            "model": model,
            "store": False,
            "input": adjusted_input,
            "max_output_tokens": max_tokens,
        }
        
        # Text formatting parameters - API requires object format for text.format
        is_gpt5 = model == "gpt-5" or model.startswith("gpt-5")
        if is_gpt5:
            params["text"] = {
                "format": {"type": "json_object"},  # Valid types: json_object | text | json_schema
                "verbosity": "low"
            }
        else:
            # Non-GPT5 models can also use the same format
            params["text"] = {
                "format": {"type": "json_object"},  # Valid types: json_object | text | json_schema
                "verbosity": "low"
            }
        
        if instructions:
            params["instructions"] = instructions
        if is_gpt5:
            effort = _validate_reasoning_effort()
            params["reasoning"] = {"effort": effort}
            logger.debug(f"Adding reasoning.effort={effort} for {model}")

        response = await asyncio.wait_for(
            client.responses.create(**params),
            timeout=RESPONSES_TIMEOUT_SECONDS
        )

        # Log token usage
        usage = getattr(response, "usage", None)
        if usage:
            logger.info(f"Token usage - Input: {getattr(usage, 'prompt_tokens', 'N/A')}, Output: {getattr(usage, 'completion_tokens', 'N/A')}")

        output = (getattr(response, "output_text", "") or "").strip()
        if not output:
            try:
                collected: List[str] = []
                output_items = getattr(response, "output", []) or []
                for item in output_items:
                    contents = (item.get("content") if isinstance(item, dict) else getattr(item, "content", None)) or []
                    for c in contents:
                        text_block = None
                        if isinstance(c, dict):
                            if "text" in c:
                                tb = c["text"]
                                if isinstance(tb, dict) and "value" in tb:
                                    text_block = tb.get("value")
                                elif isinstance(tb, str):
                                    text_block = tb
                            elif "value" in c:
                                text_block = c.get("value")
                        else:
                            tb = getattr(c, "text", None)
                            if isinstance(tb, str):
                                text_block = tb
                            elif hasattr(tb, "value"):
                                text_block = getattr(tb, "value", None)
                        if text_block:
                            collected.append(str(text_block))
                output = "\n".join([s for s in collected if s]).strip()
            except Exception:
                pass

        if not output:
            req_id = getattr(response, "id", "unknown")
            _gpt5_note_failure("empty_output")
            raise AIProcessingError(f"Empty output from Responses API (request_id={req_id})")

        request_time = time.time() - start_time

        # Get the global tracker and add metrics
        tracker = get_tracker()
        # Note: add_metric_with_context('api_request') also updates API stats internally.
        # Do not call add_api_metric() here to avoid double-counting.
        tracker.add_metric_with_context(
            category="api_request",
            duration=request_time,
            file_path=file_path,
            drawing_type=drawing_type,
            model=model,
            api_type="responses"
        )

        logger.info(
            "Responses API request completed",
            extra={
                "duration": f"{request_time:.2f}s",
                "model": model,
                "reasoning": params.get("reasoning", {}).get("effort", "none"),
                "tokens": max_tokens,
                "text_format": "json_object",
                "file": os.path.basename(file_path) if file_path else "unknown",
                "type": drawing_type or "unknown",
                "request_id": getattr(response, "id", "unknown"),
            },
        )

        _gpt5_reset()
        return output

    except Exception as e:
        request_time = time.time() - start_time
        _gpt5_note_failure(str(e))
        logger.error(
            "Responses API request failed",
            extra={"duration": f"{request_time:.2f}s", "error": str(e), "model": model},
        )
        raise AIProcessingError(f"Responses API request failed: {str(e)}")
# =================================================================


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
    Call Responses API with optional caching.
    """
    # Extract prompt from messages
    prompt = messages[-1]["content"]
    system_message = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    content_length = len(prompt or "")
    is_special = _is_schedule_or_spec(drawing_type, file_path)

    # Prepare parameters for cache key (include api_type and instructions for uniqueness)
    params = {
        "model": model,
        "temperature": 1.0,
        "max_tokens": max_tokens,
        "api_type": "responses",
        "instructions": (instructions or ""),
    }

    # Try to load from cache
    cached_response = load_cache(prompt, params)
    if cached_response:
        return cached_response

    # Always use Responses API with optional fallback chain across Responses models
    final_instructions = instructions or JSON_EXTRACTOR_INSTRUCTIONS
    try:
        content = await make_responses_api_request(
            client=client,
            input_text=prompt,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            file_path=file_path,
            drawing_type=drawing_type,
            instructions=final_instructions,
        )
    except AIProcessingError as e:
        logger.warning(f"Responses API failed, attempting fallback chain: {str(e)}")
        fallback_chain = os.getenv("MODEL_FALLBACK_CHAIN", "gpt-5-mini,gpt-5")
        content = None
        for fb_model in [m.strip() for m in fallback_chain.split(",") if m.strip()]:
            try:
                content = await make_responses_api_request(
                    client=client,
                    input_text=prompt,
                    model=fb_model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    file_path=file_path,
                    drawing_type=drawing_type,
                    instructions=final_instructions,
                )
                logger.info(f"Fallback succeeded with model {fb_model}")
                break
            except AIProcessingError as inner_e:
                logger.warning(f"Fallback model {fb_model} failed: {str(inner_e)}")
                content = None
        if not content:
            raise

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
    Process drawing content using AI to convert to structured JSON via the Responses API.
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
    logger.info(f"API mode: Responses")

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
                
                # Replace the metadata repair block with:
                if not titleblock_text:
                    logger.info("Metadata repair SKIPPED: no title block text extracted")
                elif get_enable_metadata_repair():
                    try:
                        repaired_metadata = await repair_metadata(titleblock_text, client, pdf_path)
                        if repaired_metadata:
                            # Update metadata in the parsed content
                            if "DRAWING_METADATA" in parsed:
                                parsed["DRAWING_METADATA"].update(repaired_metadata)
                            else:
                                parsed["DRAWING_METADATA"] = repaired_metadata
                            # Convert back to string
                            content = json.dumps(parsed)
                            logger.info("Successfully repaired metadata from title block")
                    except Exception as e:
                        logger.warning(f"Metadata repair failed: {str(e)}")
                else:
                    logger.warning("Metadata repair DISABLED by ENABLE_METADATA_REPAIR=false (skipping)")
                
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
    Repair metadata by extracting it from title block text using AI.
    Also updated to support GPT-5 when enabled.
    """
    # ADD THIS HARD GATE AT THE VERY BEGINNING
    from config.settings import get_enable_metadata_repair
    if not get_enable_metadata_repair():
        logger.warning("Metadata repair DISABLED by ENABLE_METADATA_REPAIR=false")
        return {}
    
    if not titleblock_text:
        logger.warning("No title block text provided for metadata repair")
        return {}

    from templates.prompt_registry import get_registry

    registry = get_registry()
    system_message = registry.get("METADATA_REPAIR")

    try:
        # Determine which model to use for metadata repair
        repair_model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
        
        content = await call_with_cache(
            client=client,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": titleblock_text},
            ],
            model=repair_model,
            temperature=1.0,
            max_tokens=min(1000, TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS),
            file_path=pdf_path,
            drawing_type="metadata_repair",
        )

        try:
            with time_operation_context("json_parsing", file_path=None, drawing_type="metadata_repair"):
                content = _strip_json_fences(content)
                parsed = json.loads(content)
                if "DRAWING_METADATA" not in parsed:
                    logger.warning("No DRAWING_METADATA found in repair response")
                    return {}
                return parsed["DRAWING_METADATA"]
        except json.JSONDecodeError as e:
            logger.error(f"JSON validation error in metadata repair: {str(e)}")
            logger.error(f"Invalid JSON snippet: {content[:500]}...")
            raise JSONValidationError(f"Invalid JSON output: {str(e)}")

    except Exception as e:
        logger.error(f"Error in metadata repair: {str(e)}")
        raise AIProcessingError(f"Error in metadata repair: {str(e)}")
