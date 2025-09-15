# PRD: Switch from Responses API to Chat Completions API

## Problem Statement
- Panel schedules are timing out using the Responses API (240s timeout)
- Mechanical drawings take 475s (3.6x slower than before) 
- The Responses API adds unnecessary reasoning overhead for simple data extraction tasks

## Solution
Switch from Responses API to Chat Completions API while keeping GPT-5 models for their 128K token capacity.

## Implementation Requirements

### 1. Replace the Responses API Function

**File:** `services/ai_service.py`

**Remove:** The entire `make_responses_api_request` function

**Add:** New simplified Chat Completions function:

```python
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
        
        # Make the API call
        response = await asyncio.wait_for(
            client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.0,  # Always 0.0 for structured extraction
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                # Note: verbosity parameter may not be available yet in all deployments
                # verbosity="low"  # Uncomment if available
            ),
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
```

### 2. Update the call_with_cache Function

**File:** `services/ai_service.py`

**Replace:** The call to `make_responses_api_request` in `call_with_cache`

**With:**
```python
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
```

### 3. Clean Up Unused Code

**Remove these variables/functions from `services/ai_service.py`:**
- `_gpt5_failures`
- `_gpt5_circuit_open`
- `_gpt5_note_failure()`
- `_gpt5_reset()`
- `_validate_reasoning_effort()`
- `_strip_json_fences()` (unless used elsewhere)
- All Responses API specific configuration

### 4. Update Environment Variables

**File:** `.env`

**Ensure these are set:**
```bash
# Token limits (already updated)
DEFAULT_MODEL_MAX_TOKENS=64000
LARGE_MODEL_MAX_TOKENS=128000
ACTUAL_MODEL_MAX_COMPLETION_TOKENS=128000

# Timeout (increase for safety)
RESPONSES_TIMEOUT_SECONDS=600  # Works for both APIs

# Models (keep as-is)
DEFAULT_MODEL=gpt-5-mini
LARGE_DOC_MODEL=gpt-5
SCHEDULE_MODEL=gpt-5
TINY_MODEL=gpt-5-nano
```

### 5. Simplify Model Parameter Optimization

**File:** `services/ai_service.py`

**Update `optimize_model_parameters` to remove reasoning/verbosity logic:**

```python
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
        max_tokens = min(128000, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
        logger.info(f"Using schedule model for {content_length} char document")
    
    # PRIORITY 2: Force mini override for non-schedules
    elif force_mini:
        model = DEFAULT_MODEL
        temperature = 0.0
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Force-mini override active ({content_length} chars)")
    
    # PRIORITY 3: Size-based selection
    elif content_length < NANO_CHAR_THRESHOLD:
        model = TINY_MODEL if TINY_MODEL else DEFAULT_MODEL
        temperature = 0.0
        max_tokens = TINY_MODEL_MAX_TOKENS if TINY_MODEL else DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using nano/tiny model ({content_length} chars)")
    
    elif content_length < MINI_CHAR_THRESHOLD:
        model = DEFAULT_MODEL
        temperature = 0.0
        max_tokens = DEFAULT_MODEL_MAX_TOKENS
        logger.info(f"Using mini model ({content_length} chars)")
    
    else:
        model = LARGE_DOC_MODEL
        temperature = 0.0
        max_tokens = LARGE_MODEL_MAX_TOKENS
        logger.info(f"Using full model ({content_length} chars)")
    
    # Ensure we don't exceed provider limits
    max_tokens = min(max_tokens, ACTUAL_MODEL_MAX_COMPLETION_TOKENS)
    
    params = {
        "model": model,
        "temperature": 0.0,  # Always 0.0 for structured extraction
        "max_tokens": max_tokens,
    }
    
    logger.info(
        f"Model: {params['model']}, Max tokens: {params['max_tokens']}, "
        f"Input: {content_length} chars"
    )
    
    return params
```

## Testing Plan

1. **Immediate Test:**
   ```bash
   python main.py /path/to/E5.00-PANEL-SCHEDULES.pdf
   ```
   - Should complete without timeout
   - Should not truncate output

2. **Performance Test:**
   ```bash
   python main.py /path/to/M6.01-MECHANICAL-SCHEDULES.pdf
   ```
   - Should complete in ~130-200s (not 475s)

3. **Verify all document types still work:**
   ```bash
   python main.py /path/to/test_folder/
   ```

## Success Criteria

- [ ] Panel schedules complete without timeout
- [ ] No truncation errors
- [ ] Processing time returns to ~130s for mechanical drawings (not 475s)
- [ ] All existing tests pass
- [ ] API costs remain reasonable (monitor token usage)

## What We're NOT Doing

- ❌ Creating new utility files (panel_utils.py)
- ❌ Adding complexity detection
- ❌ Dynamic token scaling beyond basic size buckets
- ❌ Circuit counting or panel analysis
- ❌ Enhanced logging beyond basic metrics

## Risk Mitigation

- Keep the retry logic in place
- Maintain the 600s timeout as a safety net
- Monitor the first few runs closely for any issues
- Keep the cache system to avoid redundant API calls

## Rollback Plan

If issues arise, the changes are isolated to:
1. One function replacement in `ai_service.py`
2. Can revert to Responses API by uncommenting old code

## Notes for Implementation

- This is a SIMPLIFICATION, not an enhancement
- Remove more code than you add
- Test with the problem files first (E5.00-PANEL-SCHEDULES.pdf)
- Monitor API response times in logs