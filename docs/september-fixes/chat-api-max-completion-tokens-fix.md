You're hitting a breaking API change: new Chat Completions models (gpt‑4.1 / gpt‑4o) no longer accept max_tokens and require max_completion_tokens. Your make_openai_request always sends max_tokens, causing the 400 error and retries.

Surgical hotfix (only what Cursor needs)

- File: services/ai_service.py
- Change: Use max_completion_tokens for gpt‑4.1 / gpt‑4o / gpt‑5 models, otherwise use max_tokens.
- No other files need changes for this error.

Edits

1) Add a tiny helper near the top of services/ai_service.py (after imports):

```py
def _uses_max_completion_tokens(model: str) -> bool:
    """
    Newer Chat Completions models (gpt-4.1*, gpt-4o*, gpt-5*) require 'max_completion_tokens'
    instead of 'max_tokens'.
    """
    m = (model or "").lower()
    return any(k in m for k in ["gpt-4.1", "gpt-4o", "gpt-5"])
```

2) Replace the params construction inside make_openai_request with model-aware token param:

Find this block:

```py
params = {
    "model": model,
    "messages": messages,
    "temperature": temperature,
    "max_tokens": max_tokens,
    "response_format": response_format,
}
```

Replace with:

```py
token_param = "max_completion_tokens" if _uses_max_completion_tokens(model) else "max_tokens"
params = {
    "model": model,
    "messages": messages,
    "temperature": temperature,
    token_param: max_tokens,
    "response_format": response_format,
}
```

That's it. This fixes the 400 "Unsupported parameter: 'max_tokens' … use 'max_completion_tokens'" for gpt‑4.1/4o while keeping compatibility with older models (e.g., gpt‑3.5-turbo).

Optional (defensive retry, not required)
If you want belt-and-suspenders: catch that specific error and reattempt once with the alternate param. Not necessary if you add the helper above.

After this change
- Chat Completions calls succeed for gpt‑4.1/4o and your fallback chain.
- Responses API path already uses max_output_tokens and needs no change.

<chatName="Hotfix: switch Chat API from max_tokens to max_completion_tokens where required"/>
