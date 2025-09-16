Here are the instructions to give Cursor to switch from GPT-5 to GPT-4.1 models:

## Instructions for Cursor: Switch to GPT-4.1 Models

### 1. Update `.env` file
Replace these lines:
```bash
# Find these lines:
DEFAULT_MODEL=gpt-5-mini
LARGE_DOC_MODEL=gpt-5
SCHEDULE_MODEL=gpt-5
TINY_MODEL=gpt-5-nano

# Replace with:
DEFAULT_MODEL=gpt-4.1-mini
LARGE_DOC_MODEL=gpt-4.1
SCHEDULE_MODEL=gpt-4.1
TINY_MODEL=gpt-4.1-nano

# Also update:
USE_GPT5_API=false
MODEL_FALLBACK_CHAIN=gpt-4.1-mini,gpt-4.1-nano

# Update temperatures (GPT-4.1 supports temperature control):
DEFAULT_MODEL_TEMP=0.2
LARGE_MODEL_TEMP=0.2
TINY_MODEL_TEMP=0.2
```

### 2. Update `services/ai_service.py`

In the `make_chat_completion_request` function, change the params back to standard:
```python
params = {
    "model": model,
    "messages": messages,
    "temperature": temperature,  # GPT-4.1 supports temperature
    "max_tokens": max_tokens,     # Use max_tokens, NOT max_completion_tokens
    "response_format": {"type": "json_object"},
}
```

### 3. Update `optimize_model_parameters` function
Ensure temperatures are set to 0.2 (or use from env):
```python
# In optimize_model_parameters function, ensure all temperature assignments use:
temperature = 0.2  # Or float(os.getenv("DEFAULT_MODEL_TEMP", "0.2"))
```

### 4. Remove GPT-5 specific code
Remove or comment out any GPT-5 specific checks like:
- Circuit breaker logic for GPT-5 failures
- Special reasoning_effort parameters
- Any "gpt-5" model name checks

### Summary
You're switching from GPT-5 (slow, experimental) to GPT-4.1 (stable, fast) models which:
- Support standard parameters (temperature, max_tokens)
- Have 1M token context windows
- Cost less and respond faster
- Don't require special parameter handling

This should fix your timeout issues and make processing much faster.