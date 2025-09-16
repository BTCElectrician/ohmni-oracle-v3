# Fix Instructions for Cursor

## Problem
Your code is trying to pass a `verbosity` parameter to the Chat Completions API, but this parameter only exists in the Responses API. This is causing the error:
```
AsyncCompletions.create() got an unexpected keyword argument 'verbosity'
```

## Solution: Remove the verbosity parameter

### Step 1: Open the file
Open `services/ai_service.py` in your project

### Step 2: Find the problematic code
Search for this code block (around lines 524-526):
```python
# Add verbosity parameter for GPT-5 models
is_gpt5 = model == "gpt-5" or model.startswith("gpt-5")
if is_gpt5:
    params["verbosity"] = "low"
```

### Step 3: Remove or comment out these lines
Either delete these lines entirely or comment them out:
```python
# REMOVED - verbosity doesn't exist in Chat Completions
# is_gpt5 = model == "gpt-5" or model.startswith("gpt-5")
# if is_gpt5:
#     params["verbosity"] = "low"
```

### Step 4: Verify the fix
Make sure your `make_chat_completion_request` function now looks like this (without any verbosity parameter):
```python
params = {
    "model": model,
    "messages": messages,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "response_format": {"type": "json_object"},
}
# NO verbosity parameter here!
```

### Step 5: Save and run
Save the file and run your PDF processing again. It should work now.

## Quick Command for Cursor
If Cursor supports find and replace, you can use:
- **Find:** `params["verbosity"] = "low"`
- **Replace with:** `# params["verbosity"] = "low"  # Removed - not supported in Chat Completions`

## Verification
After making this change, your GPT-5 models (gpt-5-mini, gpt-5, gpt-5-nano) will work correctly with the Chat Completions API.