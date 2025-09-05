PRD: Hybrid GPT‑5 Routing + Circuit Breaker + Cache Fix

Objective
- Keep GPT‑5 quality where it matters (large/spec/schedule docs), but avoid slow/empty-response runs.
- Use Chat Completions for everything else.
- Add a circuit breaker to disable GPT‑5 during the run after N failures.
- Pass full prompt as Responses API instructions to reduce empty outputs.
- Prevent cache collisions between Responses vs Chat and different instruction sets.

Files to change
- services/ai_service.py
- utils/ai_cache.py
- config/settings.py (minor: log new envs in get_all_settings)
- .env.example (add new env toggles)

Edits

1) services/ai_service.py

Add new toggles + circuit breaker helpers and shorten default timeout
- Place after GPT5_MODEL_MAP (near other env flags), and replace the existing RESPONSES_TIMEOUT_SECONDS default (120) with 45.

```py
# Add below GPT5_MODEL_MAP and replace existing timeout default

# Additional environment variables for stability
RESPONSES_TIMEOUT_SECONDS = int(os.getenv("RESPONSES_TIMEOUT_SECONDS", "45"))
ENABLE_GPT5_NANO = os.getenv("ENABLE_GPT5_NANO", "false").lower() == "true"
SCHEDULES_ENABLED = os.getenv("SCHEDULES_ENABLED", "false").lower() == "true"

# NEW: Routing and stability toggles
GPT5_FOR_LARGE_ONLY = os.getenv("GPT5_FOR_LARGE_ONLY", "true").lower() == "true"
GPT5_MIN_LENGTH_FOR_RESPONSES = int(os.getenv("GPT5_MIN_LENGTH_FOR_RESPONSES", str(MINI_CHAR_THRESHOLD)))
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
        logger.warning("GPT-5 circuit opened for remainder of run; routing to Chat Completions.")

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
```

Replace make_responses_api_request to track failures and reset on success
- Replace entire function with this version (adds _gpt5_note_failure/_gpt5_reset calls and keeps all existing behavior):

```py
@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=3, max=8),
    retry=retry_if_exception_type((AIProcessingError)),
    before_sleep_log(logger, logging.WARNING),
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
        m = (model or "").lower()
        is_gpt5 = m.startswith("gpt-5")

        params: Dict[str, Any] = {
            "model": model,
            "input": input_text,
            "max_output_tokens": max_tokens,
        }
        if not is_gpt5:
            params["response_format"] = {"type": "json_object"}
        if is_gpt5:
            params["text"] = {"verbosity": "low"}
            if instructions:
                params["instructions"] = instructions
            if model == "gpt-5":
                effort = _validate_reasoning_effort()
                params["reasoning"] = {"effort": effort}
                logger.debug(f"Adding reasoning.effort={effort} for {model}")

        response = await asyncio.wait_for(
            client.responses.create(**params),
            timeout=RESPONSES_TIMEOUT_SECONDS
        )

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
            "Responses API request completed",
            extra={
                "duration": f"{request_time:.2f}s",
                "model": model,
                "reasoning": params.get("reasoning", {}).get("effort", "none"),
                "tokens": max_tokens,
                "response_format": "json_object" if not is_gpt5 else "none",
                "file": os.path.basename(file_path) if file_path else "unknown",
                "type": drawing_type or "unknown",
                "request_id": getattr(response, "id", "unknown"),
            },
        )

        # SUCCESS: reset circuit breaker
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
```

Update call_with_cache to support hybrid routing, include instructions in cache key, and route by size/type/circuit breaker
- Replace entire function with this version:

```py
async def call_with_cache(
    client: AsyncOpenAI,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    response_format: Dict[str, str] = {"type": "json_object"},
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
    instructions: Optional[str] = None,  # NEW
) -> Any:
    # Extract prompt from messages
    prompt = messages[-1]["content"]
    system_message = messages[0]["content"] if messages and messages[0]["role"] == "system" else ""
    content_length = len(prompt or "")
    is_special = _is_schedule_or_spec(drawing_type, file_path)

    # Cache key params (include api_type + instructions for uniqueness)
    params = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "api_type": "responses" if USE_GPT5_API else "chat",
        "instructions": (instructions or ""),
    }

    cached_response = load_cache(prompt, params)
    if cached_response:
        return cached_response

    # Decide routing: Responses API only when enabled, circuit not open, and (large/spec/schedule) if GPT5_FOR_LARGE_ONLY
    use_responses = (
        USE_GPT5_API
        and not _gpt5_circuit_open
        and (not GPT5_FOR_LARGE_ONLY or is_special or content_length >= GPT5_MIN_LENGTH_FOR_RESPONSES)
    )

    if use_responses:
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
            fallback_chain = os.getenv("MODEL_FALLBACK_CHAIN", "gpt-4.1-mini,gpt-4.1")
            content = None
            for fb_model in [m.strip() for m in fallback_chain.split(",") if m.strip()]:
                try:
                    content = await make_openai_request(
                        client=client,
                        messages=messages,
                        model=fb_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        response_format=response_format,
                        file_path=file_path,
                        drawing_type=drawing_type,
                    )
                    logger.info(f"Fallback succeeded with model {fb_model}")
                    break
                except AIProcessingError as inner_e:
                    logger.warning(f"Fallback model {fb_model} failed: {str(inner_e)}")
                    content = None
            if not content:
                raise
    else:
        # Chat Completions path
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

    save_cache(prompt, params, content)
    return content
```

Pass full prompt as Responses instructions from process_drawing
- In process_drawing, just before calling call_with_cache, build instructions and pass them.
- Find the existing call to call_with_cache and replace that invocation block with:

```py
    # Build Responses instructions by combining the system prompt and lean JSON helper
    responses_instructions = system_message + "\n\n" + JSON_EXTRACTOR_INSTRUCTIONS

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
        instructions=responses_instructions,  # NEW
    )
```

2) utils/ai_cache.py

Include api_type and instructions hash in cache key; store api_type
- Replace _generate_cache_key with:

```py
def _generate_cache_key(prompt: str, params: Dict[str, Any]) -> str:
    """
    Generate a unique cache key based on prompt and parameters.
    Includes API type and an instructions hash to avoid cross-API collisions.
    """
    instr = (params.get("instructions") or "").strip()
    instructions_hash = hashlib.sha256(instr.encode()).hexdigest() if instr else ""

    key_data = {
        "prompt": prompt,
        "model": params.get("model", ""),
        "temperature": params.get("temperature", 0.0),
        "max_tokens": params.get("max_tokens", 0),
        "api_type": params.get("api_type", "chat"),
        "instructions_hash": instructions_hash,
    }
    key_str = json.dumps(key_data, sort_keys=True)
    return hashlib.sha256(key_str.encode()).hexdigest()
```

- Replace save_cache with:

```py
def save_cache(prompt: str, params: Dict[str, Any], response: str) -> None:
    if os.getenv("ENABLE_AI_CACHE", "false").lower() != "true":
        return

    cache_key = _generate_cache_key(prompt, params)
    cache_path = _get_cache_path(cache_key)

    try:
        cache_data = {
            "prompt": prompt,
            "params": {
                k: params[k]
                for k in ["model", "temperature", "max_tokens", "api_type"]
                if k in params
            },
            "response": response,
            "timestamp": time.time(),
        }

        with open(cache_path, "w") as f:
            json.dump(cache_data, f, indent=2)

        logger.info(f"Cached response for key {cache_key[:8]}...")
    except IOError as e:
        logger.warning(f"Failed to save cache: {str(e)}")
```

3) config/settings.py

Expose new envs in get_all_settings for visibility (optional but helpful)
- Add the following keys inside the returned dict (do not remove existing keys):

```py
        "USE_GPT5_API": os.getenv("USE_GPT5_API", "false"),
        "GPT5_FOR_LARGE_ONLY": os.getenv("GPT5_FOR_LARGE_ONLY", "true"),
        "GPT5_MIN_LENGTH_FOR_RESPONSES": os.getenv("GPT5_MIN_LENGTH_FOR_RESPONSES", str(MINI_CHAR_THRESHOLD)),
        "RESPONSES_TIMEOUT_SECONDS": os.getenv("RESPONSES_TIMEOUT_SECONDS", "45"),
        "GPT5_FAILURE_THRESHOLD": os.getenv("GPT5_FAILURE_THRESHOLD", "2"),
        "GPT5_DISABLE_ON_EMPTY_OUTPUT": os.getenv("GPT5_DISABLE_ON_EMPTY_OUTPUT", "true"),
```

4) .env.example

Add new toggles block (near model config)

```example
# GPT-5 routing and stability
USE_GPT5_API=false                 # QUICK OFF-SWITCH (true enables Responses API)
GPT5_FOR_LARGE_ONLY=true          # Use GPT-5 only for large/spec/schedule docs
GPT5_MIN_LENGTH_FOR_RESPONSES=12000
GPT5_REASONING_EFFORT=minimal     # minimal recommended for speed/stability
RESPONSES_TIMEOUT_SECONDS=45      # Fast-fail on slow Responses calls
GPT5_FAILURE_THRESHOLD=2          # After N failures, disable GPT-5 for rest of run
GPT5_DISABLE_ON_EMPTY_OUTPUT=true

# Fallback chain if Responses fails
MODEL_FALLBACK_CHAIN=gpt-4.1-mini,gpt-4.1
```

Behavioral acceptance criteria
- When USE_GPT5_API=false, all calls use Chat Completions (current behavior).
- When USE_GPT5_API=true:
  - For non-special and small docs, route to Chat Completions.
  - For schedule/spec or large docs, use Responses API.
  - If Responses returns empty/raises twice, GPT‑5 circuit opens; all subsequent calls use Chat Completions until process exit.
  - Responses timeout respects RESPONSES_TIMEOUT_SECONDS default 45s.
- Cache does not collide between Responses and Chat or between different instruction sets.

Notes
- No changes required to tests to compile; functional tests may assert routing by injecting envs.
- This refactor is limited to routing, timeout, circuit breaker, and cache key. No changes to existing normalization/extraction logic.

<chatName="PRD for GPT‑5 hybrid routing + circuit breaker + cache key fix"/>