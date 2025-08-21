"""
AI service for processing drawing content.
Simplified implementation with focused model selection and processing logic.
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
    ACTUAL_MODEL_MAX_COMPLETION_TOKENS
)
from utils.exceptions import AIProcessingError, JSONValidationError
from utils.ai_cache import load_cache, save_cache

# Initialize logger at module level
logger = logging.getLogger(__name__)


def optimize_model_parameters(
    drawing_type: str, raw_content: str, pdf_path: str
) -> Dict[str, Any]:
    """
    Determine optimal model parameters based on drawing type and content.
    Models and their parameters are fully configurable via environment variables.
    """
    content_length = len(raw_content) if raw_content else 0

    # Validate configuration
    if not DEFAULT_MODEL:
        raise ValueError("DEFAULT_MODEL not configured in settings")

    # Start with default model and its parameters
    model = DEFAULT_MODEL
    temperature = DEFAULT_MODEL_TEMP
    max_tokens = DEFAULT_MODEL_MAX_TOKENS
    
    # Check if tiny model should be used for small documents
    if TINY_MODEL and content_length < TINY_MODEL_THRESHOLD:
        model = TINY_MODEL
        temperature = TINY_MODEL_TEMP
        max_tokens = TINY_MODEL_MAX_TOKENS
        logger.info(f"Using tiny model {model} for small document ({content_length} chars)")
    else:
        # Check if this is a schedule
        is_schedule = (
            "panel" in drawing_type.lower()
            or "schedule" in drawing_type.lower()
            or ("mechanical" in drawing_type.lower() and "schedule" in pdf_path.lower())
            or ("plumbing" in drawing_type.lower() and "schedule" in pdf_path.lower())
        )

        # Check if we should upgrade model
        force_mini = get_force_mini_model()
        use_large_model = not force_mini and (
            content_length > MODEL_UPGRADE_THRESHOLD
            or (USE_4O_FOR_SCHEDULES and is_schedule)
        )

        if use_large_model:
            model = SCHEDULE_MODEL if is_schedule else LARGE_DOC_MODEL
            temperature = LARGE_MODEL_TEMP
            max_tokens = LARGE_MODEL_MAX_TOKENS
            reason = "schedule document" if is_schedule else f"large document ({content_length} chars)"
            logger.info(f"Using {model} for {reason}")

    # Dynamic token allocation for large documents
    if model in [LARGE_DOC_MODEL, SCHEDULE_MODEL]:
        # Scale tokens based on input size
        if content_length > 35000:  # Massive specs/drawings
            # Boost max_tokens, but ensure it doesn't exceed the absolute model limit
            max_tokens = min(ACTUAL_MODEL_MAX_COMPLETION_TOKENS, max_tokens * 2)
            logger.info(f"Boosting max_tokens to {max_tokens} for very large document")
        elif content_length > 25000:  # Large complex documents
            # Boost max_tokens, but ensure it doesn't exceed the absolute model limit
            max_tokens = min(ACTUAL_MODEL_MAX_COMPLETION_TOKENS, int(max_tokens * 1.5))
            logger.info(f"Boosting max_tokens to {max_tokens} for large document")
        # Note: else keeps the configured max_tokens value

    # Build parameters
    params = {
        "model": model,
        "temperature": temperature,
        # Ensure max_tokens never exceeds the absolute model limit, regardless of previous logic
        "max_tokens": min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS),
    }

    # Special handling for panel schedules - always use 0 temperature
    if "panel" in drawing_type.lower() or "schedule" in drawing_type.lower():
        params["temperature"] = 0.0

    logger.info(
        f"Model selection: type={drawing_type}, length={content_length}, "
        f"model={params['model']}, temp={params['temperature']}, max_tokens={params['max_tokens']}"
    )
    return params


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

    Args:
        client: OpenAI client
        messages: List of message dictionaries
        model: Model name
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        response_format: Response format specification
        file_path: Original PDF file path
        drawing_type: Type of drawing (detected or specified)

    Returns:
        OpenAI API response

    Raises:
        AIProcessingError: If the request fails after retries
    """
    start_time = time.time()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        request_time = time.time() - start_time

        # Get the global tracker and add metrics
        tracker = get_tracker()
        tracker.add_api_metric(request_time)  # Keep for overall API stats
        
        # Add metric with explicit context
        tracker.add_metric_with_context(
            category="api_request",
            duration=request_time,
            file_path=file_path,
            drawing_type=drawing_type,
            model=model  # Extra context
        )

        logger.info(
            "OpenAI API request completed",
            extra={
                "duration": f"{request_time:.2f}s",
                "model": model,
                "tokens": max_tokens,
                "file": os.path.basename(file_path) if file_path else "unknown",
                "type": drawing_type or "unknown",
            },
        )
        return response
    except Exception as e:
        request_time = time.time() - start_time
        logger.error(
            "OpenAI API request failed",
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

    Args:
        client: OpenAI client
        messages: List of message dictionaries
        model: Model name
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        response_format: Response format specification
        file_path: Original PDF file path
        drawing_type: Type of drawing (detected or specified)

    Returns:
        API response (potentially from cache)
    """
    # Extract prompt from the last message
    prompt = messages[-1]["content"]

    # Prepare parameters for cache key
    params = {"model": model, "temperature": temperature, "max_tokens": max_tokens}

    # Try to load from cache
    cached_response = load_cache(prompt, params)
    if cached_response:
        return cached_response

    # Call API if not in cache
    response = await make_openai_request(
        client=client,
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        response_format=response_format,
        file_path=file_path,
        drawing_type=drawing_type,
    )

    # Extract content from response
    content = response.choices[0].message.content

    # Save to cache
    save_cache(prompt, params, content)

    return content


@time_operation("ai_processing")
async def process_drawing(
    raw_content: str, drawing_type: str, client: AsyncOpenAI, pdf_path: str = "", titleblock_text: Optional[str] = None
) -> str:
    """
    Process drawing content using AI to convert to structured JSON.

    Args:
        raw_content: Raw content extracted from drawing
        drawing_type: Type of drawing (detected or specified)
        client: OpenAI client
        pdf_path: Original PDF file path
        titleblock_text: Optional text extracted from title block region

    Returns:
        Structured JSON as string

    Raises:
        AIProcessingError: If processing fails
        JSONValidationError: If JSON validation fails
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

    # If no drawing_type provided or it's General, use the detected main_type
    if not drawing_type or drawing_type == "General":
        drawing_type = main_type

    # Debug info for prompt selection
    logger.info(f"Detected drawing info: main_type={main_type}, subtype={subtype}")
    logger.info(f"Using drawing_type={drawing_type} for prompt selection")

    # Get appropriate system message
    registry = get_registry()
    system_message = registry.get(drawing_type, subtype)

    # Check if the system message contains the word 'json'
    if "json" not in system_message.lower():
        logger.warning(
            f"System message for {drawing_type}/{subtype} doesn't contain the word 'json' - adding it"
        )
        system_message += "\n\nFormat your entire response as a valid JSON object."

    logger.info(f"Prompt key used: {drawing_type}_{subtype if subtype else ''}")
    logger.info(f"Prompt contains 'json': {'json' in system_message.lower()}")

    # Get optimized model parameters
    params = optimize_model_parameters(drawing_type, raw_content, pdf_path)

    try:
        # Use the cache-aware function instead of direct make_openai_request
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
                        # Continue with original content if repair fails
                
                # Check for potential truncation
                output_length = len(content)
                input_length = len(raw_content)
                
                # Rough token estimation (4 chars per token average)
                # Ensure params["max_tokens"] is available here; it should be if optimize_model_parameters was called
                current_max_tokens = params.get("max_tokens", ACTUAL_MODEL_MAX_COMPLETION_TOKENS) # Fallback if params not yet fully populated in this scope
                estimated_output_tokens = output_length / 4
                token_usage_percent = (estimated_output_tokens / current_max_tokens) * 100 if current_max_tokens > 0 else 0
                
                if token_usage_percent > 90:
                    logger.warning(
                        f"Possible truncation: {token_usage_percent:.0f}% token usage. "
                        f"Input: {input_length} chars, Output: {output_length} chars, "
                        f"Max tokens: {current_max_tokens}"
                    )
                elif output_length < input_length * 0.5:  # Output less than half of input
                    logger.warning(
                        f"Suspiciously small output: Input {input_length} chars → Output {output_length} chars"
                    )
                
                logger.info(
                    "Successfully processed drawing",
                    extra={
                        "drawing_type": drawing_type,
                        "output_length": len(content),
                        "estimated_tokens": int(estimated_output_tokens), # Assuming estimated_output_tokens from STEP 2 is in scope
                        "token_usage_percent": f"{token_usage_percent:.0f}%", # Assuming token_usage_percent from STEP 2 is in scope
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

            # Log snippet of invalid JSON for debugging
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

    Args:
        titleblock_text: Text extracted from the title block region
        client: OpenAI client
        pdf_path: Original PDF file path

    Returns:
        Dictionary containing the repaired metadata

    Raises:
        AIProcessingError: If processing fails
        JSONValidationError: If JSON validation fails
    """
    if not titleblock_text:
        logger.warning("No title block text provided for metadata repair")
        return {}

    from templates.prompt_registry import get_registry

    # Get the metadata repair prompt
    registry = get_registry()
    system_message = registry.get("METADATA_REPAIR")

    try:
        # Use the cache-aware function
        content = await call_with_cache(
            client=client,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": titleblock_text},
            ],
            model=TINY_MODEL if TINY_MODEL else DEFAULT_MODEL,
            temperature=TINY_MODEL_TEMP if TINY_MODEL else DEFAULT_MODEL_TEMP,
            max_tokens=min(1000, TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS),
            file_path=pdf_path,
            drawing_type="metadata_repair",
        )

        # Validate JSON
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
