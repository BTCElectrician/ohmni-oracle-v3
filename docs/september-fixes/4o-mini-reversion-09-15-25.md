# Fix OpenAI Model Performance Issues

## Context
We discovered GPT-4.1 models are 2.7x MORE expensive than GPT-4o AND significantly slower (8+ minute processing times). We need to switch back to GPT-4o models and fix token limit issues.

## Task 1: Update .env File
Update the `.env` file with these exact changes:

```bash
# Change all model references from gpt-4.1 to gpt-4o
DEFAULT_MODEL=gpt-4o-mini
LARGE_DOC_MODEL=gpt-4o
SCHEDULE_MODEL=gpt-4o
TINY_MODEL=gpt-4o-mini

# Keep these token limits as-is (32768 max for GPT-4o)
DEFAULT_MODEL_MAX_TOKENS=32768
LARGE_MODEL_MAX_TOKENS=32768
TINY_MODEL_MAX_TOKENS=8000
ACTUAL_MODEL_MAX_COMPLETION_TOKENS=32768

# Add new setting for specification documents
SPEC_MAX_TOKENS=16000
```

## Task 2: Update services/ai_service.py

In the `optimize_model_parameters` function (around line 90-150), add special handling for specification documents to prevent JSON truncation:

```python
def optimize_model_parameters(
    drawing_type: str, raw_content: str, pdf_path: str
) -> Dict[str, Any]:
    """
    Determine optimal model parameters based on drawing type and content.
    """
    content_length = len(raw_content) if raw_content else 0

    # ... existing code ...

    # ADD THIS SECTION: Special handling for specification documents
    # Specs need reduced tokens to avoid truncation
    is_specification = (
        "spec" in drawing_type.lower() or 
        "specification" in drawing_type.lower() or
        "spec" in pdf_path.lower() or 
        "specification" in pdf_path.lower()
    )
    
    if is_specification:
        spec_max_tokens = int(os.getenv("SPEC_MAX_TOKENS", "16000"))
        max_tokens = min(max_tokens, spec_max_tokens)
        logger.info(f"Specification document detected - limiting to {max_tokens} tokens")

    # ... rest of existing code ...
```

## Task 3: Verify Changes

After making these changes:

1. Check that `.env` has all the GPT-4o models set correctly
2. Verify `SPEC_MAX_TOKENS=16000` is in `.env`
3. Ensure the specification handling code is added to `optimize_model_parameters`
4. Run a test with a specification document to confirm it doesn't truncate

## Expected Results
- Processing time should drop from 8+ minutes to 2-3 minutes total
- Costs will be 63% lower
- Specification documents will process without JSON truncation errors
- All 9 test files should process successfully

## Note
GPT-4o models also have a 32,768 token limit, so the token limits we set earlier are still correct. The main change is switching the model names back to GPT-4o variants and adding special handling for long specification documents.