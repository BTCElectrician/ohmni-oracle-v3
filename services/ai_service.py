"""
AI service for processing drawing content using the Chat Completions API (gpt-5).
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



def _strip_json_fences(s: str) -> str:
    """Strip JSON code fences from string to prevent parsing errors."""
    if not s:
        return s
    m = re.match(r"^```(?:json)?\s*(.*)```$", s.strip(), re.DOTALL | re.IGNORECASE)
    return m.group(1).strip() if m else s
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
    Make a Chat Completions API request with GPT-5 models.
    Simplified version without reasoning chains or complex verbosity settings.
    """
    start_time = time.time()
    
    try:
        # Build messages
        system_message = instructions or JSON_EXTRACTOR_INSTRUCTIONS
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": input_text}
        ]
        
        # Determine reasoning effort based on model and task complexity
        reasoning_effort = "minimal"
        if model == "gpt-5":
            reasoning_effort = "low"  # Use low for full model to balance speed/accuracy
        elif model == "gpt-5-mini":
            reasoning_effort = "minimal"  # Fast processing for mini
        elif model == "gpt-5-nano":
            reasoning_effort = "minimal"  # Fastest for nano
        
        # Build API parameters
        api_params = {
            "model": model,
            "messages": messages,
            "temperature": 0.0,  # Always 0.0 for structured extraction
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        
        # Add GPT-5 specific parameters if available
        if model.startswith("gpt-5"):
            api_params["reasoning_effort"] = reasoning_effort
            api_params["verbosity"] = "low"  # Concise output for faster processing
        
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
            api_type="chat"  # Changed from "responses"
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
    Simplified version without Responses API specific parameters.
    """
    content_length = len(raw_content) if raw_content else 0
    
    # Detect if this is a schedule OR a specification
    is_schedule = _is_schedule_or_spec(drawing_type, pdf_path)
    
    # Get force mini override status
    force_mini = get_force_mini_model()
    
    # PRIORITY 1: Schedules/specs use appropriate model with sufficient tokens
    if is_schedule:
        model = SCHEDULE_MODEL
        temperature = 0.0  # Always 0.0 for extraction
        # Use larger token limit since GPT-5 supports 400K context and 128K output
        max_tokens = min(128000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        logger.info(f"Using schedule model for {content_length} char document")
    
    # PRIORITY 2: Force mini override for non-schedules
    elif force_mini:
        model = DEFAULT_MODEL
        temperature = 0.0
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Force-mini override active ({content_length} chars)")
    
    # PRIORITY 3: Size-based selection with optimized model choice
    elif content_length < NANO_CHAR_THRESHOLD:
        # Use nano for simple classification and basic extraction
        model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
        temperature = 0.0
        max_tokens = TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using nano model for simple extraction ({content_length} chars)")
    
    elif content_length < MINI_CHAR_THRESHOLD:
        # Use mini for structured schedules and repetitive tasks
        model = DEFAULT_MODEL
        temperature = 0.0
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using mini model for structured extraction ({content_length} chars)")
    
    else:
        # Use full model only for complex reasoning and multi-step tasks
        model = LARGE_DOC_MODEL
        temperature = 0.0
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model for complex extraction ({content_length} chars)")
    
    # Token policy: keep large outputs reasonable to avoid timeouts
    if model in [LARGE_DOC_MODEL, SCHEDULE_MODEL]:
        if content_length > 35000:
            max_tokens = min(6000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
            logger.info(f"Capping max_tokens to {max_tokens} for very large document")
        elif content_length > 25000:
            max_tokens = min(8000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
            logger.info(f"Setting max_tokens to {max_tokens} for large document")
        elif content_length > 15000:
            max_tokens = min(10000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        # else: use default max_tokens
    
    # Ensure we don't exceed provider limits
    max_tokens = min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
    
    params = {
        "model": model,
        "temperature": 0.0,  # Always 0.0 for structured extraction
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
        "temperature": 0.0,  # Always 0.0 for extraction
        "max_tokens": max_tokens,
        "api_type": "chat",  # Changed from "responses"
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
        temperature=0.0,  # Override to 0.0
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
