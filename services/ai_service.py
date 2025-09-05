"""
AI service for processing drawing content.
Enhanced with GPT-5 Responses API support (minimal changes).
"""
import json
import logging
import time
import os
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
from utils.ai_cache import load_cache, save_cache

# Initialize logger at module level
logger = logging.getLogger(__name__)

# ============== NEW GPT-5 CONFIGURATION ==============
USE_GPT5_API = os.getenv("USE_GPT5_API", "false").lower() == "true"
GPT5_REASONING_EFFORT = os.getenv("GPT5_REASONING_EFFORT", "minimal")
GPT5_TEXT_VERBOSITY = os.getenv("GPT5_TEXT_VERBOSITY", "low")

# Model mapping for GPT-5 (when USE_GPT5_API=true)
GPT5_MODEL_MAP = {
    "gpt-4o-mini": "gpt-5-mini",
    "gpt-4o": "gpt-5",
    "gpt-4.1-mini": "gpt-5-mini",
    "gpt-4.1": "gpt-5",
    "gpt-3.5-turbo": "gpt-5-nano",
    # Add any custom mappings
}
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

    # Detect if this is a schedule (schedules need maximum accuracy)
    is_schedule = (
        "panel" in drawing_type.lower()
        or "schedule" in drawing_type.lower()
        or ("mechanical" in drawing_type.lower() and "schedule" in pdf_path.lower())
        or ("plumbing" in drawing_type.lower() and "schedule" in pdf_path.lower())
        or ("electrical" in drawing_type.lower() and "schedule" in pdf_path.lower())
        or ("electrical" in drawing_type.lower() and "panel" in pdf_path.lower())
        or ("architectural" in drawing_type.lower() and "schedule" in pdf_path.lower())
        or ("firealarm" in drawing_type.lower() and "schedule" in pdf_path.lower())
    )

    # Get force mini override status
    force_mini = get_force_mini_model()

    # PRIORITY 1: Schedules ALWAYS use full model regardless of size or overrides
    if is_schedule:
        model = SCHEDULE_MODEL  # Will map to gpt-5 when USE_GPT5_API=true
        temperature = LARGE_MODEL_TEMP
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for schedule document ({content_length} chars)")
    
    # PRIORITY 2: Force mini override for non-schedules (emergency cost control)
    elif force_mini:
        model = DEFAULT_MODEL  # Will map to gpt-5-mini when USE_GPT5_API=true
        temperature = DEFAULT_MODEL_TEMP
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Force-mini override active; using mini model for non-schedule ({content_length} chars)")
    
    # PRIORITY 3: Size-based bucket selection for normal operation
    elif content_length < NANO_CHAR_THRESHOLD:
        # Small documents < 3K chars: Use nano/tiny
        model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL  # Will map to gpt-5-nano when USE_GPT5_API=true
        temperature = TINY_MODEL_TEMP if TINY_MODEL else DEFAULT_MODEL_TEMP
        max_tokens = TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using nano/tiny model for small document ({content_length} chars)")
    
    elif content_length < MINI_CHAR_THRESHOLD:
        # Medium documents 3K-15K chars: Use mini
        model = DEFAULT_MODEL  # Will map to gpt-5-mini when USE_GPT5_API=true
        temperature = DEFAULT_MODEL_TEMP
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using mini model for medium document ({content_length} chars)")
    
    else:
        # Large documents > 15K chars: Use full model
        model = LARGE_DOC_MODEL  # Will map to gpt-5 when USE_GPT5_API=true
        temperature = LARGE_MODEL_TEMP
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for large document ({content_length} chars)")

    # Map to GPT-5 models if enabled (existing logic)
    if USE_GPT5_API:
        original_model = model
        model = GPT5_MODEL_MAP.get(model, model)
        if model != original_model:
            logger.info(f"Mapped {original_model} -> {model} (GPT-5 mode)")

    # Dynamic token allocation for large documents (existing logic)
    if model in [LARGE_DOC_MODEL, SCHEDULE_MODEL] or (USE_GPT5_API and model == "gpt-5"):
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
        "temperature": temperature,
        "max_tokens": min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS),
    }

    # Special handling for panel schedules - always use 0 temperature (existing logic)
    if "panel" in drawing_type.lower() or "schedule" in drawing_type.lower():
        params["temperature"] = 0.0

    # Log final selection with size bucket info
    size_bucket = "nano" if content_length < NANO_CHAR_THRESHOLD else \
                  "mini" if content_length < MINI_CHAR_THRESHOLD else "full"
    
    logger.info(
        f"Model selection: type={drawing_type}, length={content_length}, "
        f"bucket={size_bucket}, schedule={is_schedule}, force_mini={force_mini}, "
        f"model={params['model']}, temp={params['temperature']}, max_tokens={params['max_tokens']}"
    )
    return params


# ============== NEW: Responses API Request Function ==============
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((Exception)),
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
) -> Any:
    """
    Make a request to the GPT-5 Responses API with timing and retry logic.
    
    FIXED 2025-09-04: reasoning.effort parameter only works with main "gpt-5" model,
    not with gpt-5-mini or gpt-5-nano variants.
    
    Args:
        client: OpenAI client
        input_text: The input text to process
        model: Model name (gpt-5, gpt-5-mini, gpt-5-nano)
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        file_path: Original PDF file path
        drawing_type: Type of drawing (detected or specified)
        
    Returns:
        Response object from the API
        
    Raises:
        AIProcessingError: If the request fails after retries
    """
    start_time = time.time()
    try:
        # Build base parameters
        params = {
            "model": model,
            "input": input_text,
            "max_output_tokens": max_tokens,
        }
        
        # CRITICAL FIX: Only add reasoning.effort for EXACT "gpt-5" model
        # NOT for gpt-5-mini or gpt-5-nano which reject this parameter
        if model == "gpt-5":  # EXACT match only!
            reasoning_effort = os.getenv("GPT5_REASONING_EFFORT", "medium")
            if reasoning_effort:
                params["reasoning"] = {"effort": reasoning_effort}
                logger.debug(f"Added reasoning.effort={reasoning_effort} for {model}")
        
        # Verbosity parameter MAY work for all gpt-5 variants (test carefully)
        if model.startswith("gpt-5"):
            verbosity_level = os.getenv("GPT5_TEXT_VERBOSITY")
            if verbosity_level:
                params["text"] = {"verbosity": verbosity_level}
                logger.debug(f"Added verbosity={verbosity_level} for {model}")
        
        # Make the API call with properly filtered parameters
        response = await client.responses.create(**params)
        
        request_time = time.time() - start_time
        
        # Track metrics
        tracker = get_tracker()
        tracker.add_api_metric(request_time)
        tracker.add_metric_with_context(
            category="api_request",
            duration=request_time,
            file_path=file_path,
            drawing_type=drawing_type,
            model=model,
            api_type="responses"
        )
        
        logger.info(
            "GPT-5 Responses API request completed",
            extra={
                "duration": f"{request_time:.2f}s",
                "model": model,
                "reasoning": params.get("reasoning", {}).get("effort", "none"),
                "verbosity": params.get("text", {}).get("verbosity", "none"),
                "tokens": max_tokens,
                "file": os.path.basename(file_path) if file_path else "unknown",
                "type": drawing_type or "unknown",
            },
        )
        
        # Return the output text directly
        return response.output_text
        
    except Exception as e:
        request_time = time.time() - start_time
        logger.error(
            "GPT-5 Responses API request failed",
            extra={"duration": f"{request_time:.2f}s", "error": str(e), "model": model},
        )
        raise AIProcessingError(f"GPT-5 API request failed: {str(e)}")
# =================================================================


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((Exception)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def make_openai_request(
    client: AsyncOpenAI,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    response_format: Dict[str, str] = {"type": "json_object"},
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
) -> Any:
    """
    Make a request to the OpenAI API with timing and retry logic.
    
    FIXED 2025-09-04: reasoning.effort parameter only works with main "gpt-5" model,
    not with gpt-5-mini or gpt-5-nano variants.
    """
    start_time = time.time()
    try:
        # Build base parameters - these work for ALL models
        params = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": response_format,
        }
        
        # CRITICAL FIX: Only add reasoning.effort for EXACT "gpt-5" model
        # NOT for gpt-5-mini or gpt-5-nano which reject this parameter
        if model == "gpt-5":  # EXACT match, not startswith!
            reasoning_effort = os.getenv("GPT5_REASONING_EFFORT", "medium")
            if reasoning_effort:
                params["reasoning"] = {"effort": reasoning_effort}
                logger.debug(f"Added reasoning.effort={reasoning_effort} for {model}")
        
        # Verbosity parameter MAY work for all gpt-5 variants (test carefully)
        if model.startswith("gpt-5"):
            verbosity_level = os.getenv("GPT5_TEXT_VERBOSITY")
            if verbosity_level:
                params["text"] = {"verbosity": verbosity_level}
                logger.debug(f"Added verbosity={verbosity_level} for {model}")
        
        # Make the API call with properly filtered parameters
        response = await client.chat.completions.create(**params)
        request_time = time.time() - start_time

        tracker = get_tracker()
        tracker.add_api_metric(request_time)
        tracker.add_metric_with_context(
            category="api_request",
            duration=request_time,
            file_path=file_path,
            drawing_type=drawing_type,
            model=model,
            api_type="chat_completions"
        )

        logger.info(
            "OpenAI Chat API request completed",
            extra={
                "duration": f"{request_time:.2f}s",
                "model": model,
                "tokens": max_tokens,
                "file": os.path.basename(file_path) if file_path else "unknown",
                "type": drawing_type or "unknown",
            },
        )
        return response.choices[0].message.content
    except Exception as e:
        request_time = time.time() - start_time
        logger.error(
            "OpenAI Chat API request failed",
            extra={"duration": f"{request_time:.2f}s", "error": str(e), "model": model},
        )
        raise AIProcessingError(f"OpenAI API request failed: {str(e)}")


async def call_with_cache(
    client: AsyncOpenAI,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    response_format: Dict[str, str] = {"type": "json_object"},
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
) -> Any:
    """
    Call OpenAI API with optional caching.
    Routes between Responses API (GPT-5) and Chat Completions based on configuration.
    """
    # Extract prompt from messages
    prompt = messages[-1]["content"]
    system_message = messages[0]["content"] if messages[0]["role"] == "system" else ""
    
    # Prepare parameters for cache key
    params = {
        "model": model, 
        "temperature": temperature, 
        "max_tokens": max_tokens,
        "api_type": "responses" if USE_GPT5_API else "chat"
    }
    
    # Try to load from cache
    cached_response = load_cache(prompt, params)
    if cached_response:
        return cached_response
    
    # ============== NEW: Route to appropriate API ==============
    if USE_GPT5_API:
        # Combine system message and user prompt for Responses API
        combined_input = f"{system_message}\n\n{prompt}" if system_message else prompt
        
        content = await make_responses_api_request(
            client=client,
            input_text=combined_input,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            file_path=file_path,
            drawing_type=drawing_type,
        )
    else:
        # Use legacy Chat Completions API
        content = await make_openai_request(
            client=client,
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
            file_path=file_path,
            drawing_type=drawing_type,
        )
    # ===========================================================
    
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
    Process drawing content using AI to convert to structured JSON.
    Now supports both Chat Completions and Responses API via configuration.
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
    logger.info(f"API mode: {'GPT-5 Responses' if USE_GPT5_API else 'Chat Completions'}")

    # Get optimized model parameters
    params = optimize_model_parameters(drawing_type, raw_content, pdf_path)

    try:
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
        )

        # Validate JSON with timing
        try:
            with time_operation_context("json_parsing", file_path=pdf_path, drawing_type=drawing_type):
                parsed = json.loads(content)
                
                # If we have title block text, try to repair metadata
                if titleblock_text:
                    try:
                        repaired_metadata = await repair_metadata(titleblock_text, client, pdf_path)
                        if repaired_metadata:
                            if "DRAWING_METADATA" in parsed:
                                parsed["DRAWING_METADATA"].update(repaired_metadata)
                            else:
                                parsed["DRAWING_METADATA"] = repaired_metadata
                            content = json.dumps(parsed)
                            logger.info("Successfully repaired metadata from title block")
                    except Exception as e:
                        logger.warning(f"Metadata repair failed: {str(e)}")
                
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
    if not titleblock_text:
        logger.warning("No title block text provided for metadata repair")
        return {}

    from templates.prompt_registry import get_registry

    registry = get_registry()
    system_message = registry.get("METADATA_REPAIR")

    try:
        # Determine which model to use for metadata repair
        repair_model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
        if USE_GPT5_API:
            repair_model = GPT5_MODEL_MAP.get(repair_model, "gpt-5-nano")
        
        content = await call_with_cache(
            client=client,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": titleblock_text},
            ],
            model=repair_model,
            temperature=TINY_MODEL_TEMP if TINY_MODEL else DEFAULT_MODEL_TEMP,
            max_tokens=min(1000, TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS),
            file_path=pdf_path,
            drawing_type="metadata_repair",
        )

        try:
            with time_operation_context("json_parsing", file_path=None, drawing_type="metadata_repair"):
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