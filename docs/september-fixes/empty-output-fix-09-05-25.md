📝 PRD: Fix Empty Outputs from GPT-5 Responses API
1. Problem Statement

When using USE_GPT5_API=true with gpt-5-mini, the Responses API frequently returns empty outputs. Logs show AIProcessingError: Empty output from Responses API. This causes retries, long stalls, and delays in the drawing processing pipeline.

Root cause:

response.output_text is sometimes empty for GPT-5 models, especially mini.

Current code concatenates system + user into input, instead of using instructions.

No fallback mechanism when GPT-5 returns empty.

2. Objectives

Eliminate empty-output errors from GPT-5 Responses API.

Ensure every request produces a JSON object (no markdown, no fences).

Add a robust fallback path (Chat Completions) if Responses API fails.

Shorten timeout to reduce long stalls.

Log request IDs for debugging.

3. Technical Changes
A. Update make_responses_api_request

Add instructions: Optional[str] = None to function signature.

If model starts with "gpt-5":

Set params["instructions"] = instructions if provided.

Set params["text"] = {"verbosity": "low"}.

If model == "gpt-5", add params["reasoning"] = {"effort": validated_effort}.

Extraction:

First try response.output_text.

If empty, reconstruct from response.output[*].content[*].text.

If still empty, raise AIProcessingError("Empty output …") including request_id.

Add request_id into logs.

B. Update call_with_cache

When USE_GPT5_API:

Pass input_text=prompt and instructions=system_message (instead of concatenating).

Wrap call in try/except. On AIProcessingError, iterate through MODEL_FALLBACK_CHAIN (e.g., gpt-4.1-mini,gpt-4.1) using make_openai_request.

C. Timeout & Retry

Change RESPONSES_TIMEOUT_SECONDS default from 600 → 120.

In retry decorators:

Restrict retries to AIProcessingError only (not JSON parse errors).

Use stop_after_attempt(2) with exponential backoff (min=3, max=8).

D. Instructions Prompt

Use a lean JSON extraction prompt as instructions:

You are an expert in construction-document extraction. Transform the user's input
(raw text from a single drawing) into ONE valid JSON object ONLY (no markdown,
no code fences, no commentary).

Requirements:
- Capture EVERYTHING. Preserve exact values. Use null where unknown.
- Top-level keys: DRAWING_METADATA + one MAIN_CATEGORY (ARCHITECTURAL | ELECTRICAL | MECHANICAL | PLUMBING | OTHER).
- Schedules → arrays of row objects. Specs/notes → keep hierarchy.
- If ARCHITECTURAL floor plan: include ARCHITECTURAL.ROOMS[] with room_number, room_name, dimensions.
- Return ONLY the JSON.


This becomes the system_message → instructions param.

4. Acceptance Criteria

✅ No more Empty output from Responses API errors under normal loads.

✅ Every GPT-5 call produces JSON text or cleanly falls back to Chat Completions.

✅ Requests never hang longer than 120s.

✅ Logs show request_id, model, and timing for every call.

✅ Cache still works with new parameters.

✅ Outputs validate as JSON (or trigger fallback repair logic).

5. Deployment Notes

Update .env:

RESPONSES_TIMEOUT_SECONDS=120

MODEL_FALLBACK_CHAIN=gpt-4.1-mini,gpt-4.1

Roll out patch → test with small, medium, and schedule drawings.

Verify JSON passes through ingestion into Azure AI Search.

6. Risks & Mitigations

Risk: GPT-5 output remains malformed JSON.
Mitigation: Existing _strip_json_fences + JSONValidationError repair logic remains.

Risk: Fallback models increase cost slightly.
Mitigation: Only triggered when GPT-5 fails (rare).

7. Next Steps for Cursor Agent

Modify make_responses_api_request per Section 3A.

Modify call_with_cache per Section 3B.

Update .env with new timeout and fallback chain.

Replace system prompt with the JSON extractor instructions in Section 3D.

Run regression tests on a known PDF to confirm JSON output.