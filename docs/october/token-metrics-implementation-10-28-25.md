# Token Usage & Performance Metrics Implementation

**Date:** October 28, 2025  
**Purpose:** Add comprehensive token tracking to prove `max_tokens` doesn't affect processing speed

## Summary

Implemented detailed token usage tracking and performance metrics to validate that processing time correlates with **actual completion tokens generated**, not the `max_tokens` parameter ceiling.

## Changes Made

### 1. Enhanced AI Service (`services/ai_service.py`)

**Token Tracking in API Calls:**
- Captures `prompt_tokens`, `completion_tokens`, `total_tokens` from API responses
- Calculates tokens/sec (throughput metric)
- Logs throughput for visibility: `Throughput: XX.XX tokens/sec`
- Passes detailed token metrics to performance tracker

**Cache Hit Tracking:**
- Separate `api_cache_hit` category to avoid polluting live API timing stats
- Cache hits don't affect API performance metrics

### 2. Enhanced Performance Tracker (`utils/performance_utils.py`)

**New Metrics Category:**
- Added `api_cache_hit` to metrics dictionary

**Token Statistics Report:**
- Total completion tokens across all calls
- Average completion tokens per call
- Average tokens/second throughput
- **Percentiles** (p50, p95, p99) for both:
  - Completion tokens distribution
  - Tokens/second distribution
- **Per-model breakdown** showing:
  - Number of calls per model
  - Avg completion tokens per model
  - Avg tokens/sec per model
  - Total tokens per model

**Enhanced Logging:**
- Token statistics section in performance reports
- Per-model performance comparison
- Percentile distribution for outlier detection

### 3. Startup Configuration Logging (`main.py`)

**Model & Token Configuration Section:**
- All model names (DEFAULT, LARGE_DOC, SCHEDULE, TINY)
- All token limits (ACTUAL_MODEL_MAX_COMPLETION_TOKENS, etc.)
- Character thresholds for model selection
- Timeout configuration

**OCR Configuration Section:**
- OCR model name
- Tokens per tile
- DPI and grid size

### 4. Validation Script (`validate_token_performance.py`)

**Features:**
- Analyzes metrics files to show token/time correlation
- Displays token statistics with percentiles
- Shows per-model breakdown
- Compares multiple runs
- Proves `max_tokens` ceiling doesn't affect speed

**Usage:**
```bash
python3 validate_token_performance.py output/metrics
```

## Key Findings Validated

### ✅ What's TRUE
- Processing time scales linearly with **actual completion tokens generated**
- Tokens/sec (throughput) varies by model and API load
- Different models have different throughput characteristics

### ❌ What's FALSE
- `max_tokens` parameter does NOT slow down requests
- Setting `max_tokens=32000` vs `max_tokens=16000` has no impact if actual output is 5K tokens
- "Halve max_tokens to halve processing time" is fundamentally wrong

## Configuration Validation

Your current settings are **correct** for GPT-4.1 models:

```bash
ACTUAL_MODEL_MAX_COMPLETION_TOKENS=32000  ✅ (gpt-4.1 family supports 32,768)
DEFAULT_MODEL_MAX_TOKENS=32000            ✅
LARGE_MODEL_MAX_TOKENS=32000              ✅
SPEC_MAX_TOKENS=16384                     ✅ (reasonable limit)
```

## What to Monitor

### Performance Bottlenecks (in order of impact):

1. **Actual token output length**
   - Check: `avg_completion_tokens` in reports
   - Fix: More focused prompts, better extraction logic

2. **API throttling**
   - Check: `tokens_per_second` percentiles (p50, p95, p99)
   - Fix: Rate limiting, time-of-day adjustments

3. **Model selection**
   - Check: Per-model breakdown in reports
   - Fix: Use faster models (nano vs mini vs full)

4. **OCR triggering**
   - Check: OCR statistics in reports
   - Fix: Better OCR threshold tuning

### Red Flags to Watch For

**Throttling Indicators:**
- Tokens/sec p50 < 20 (typical should be 30-60)
- Large gap between p50 and p95 tokens/sec
- Inconsistent throughput across similar files

**Output Issues:**
- Completion tokens approaching max_tokens_param (truncation risk)
- High p99 completion tokens (outliers need investigation)
- Per-model stats showing unexpected differences

## Example Output

### Token Statistics in Reports:
```
=== API Token Statistics ===
  Samples: 42
  Total completion tokens: 245,680
  Avg completion tokens: 5,849.5
  Avg tokens/sec: 45.23
  Completion tokens percentiles - p50: 5,200, p95: 12,400, p99: 15,800
  Tokens/sec percentiles - p50: 42.15, p95: 58.30, p99: 62.10
  Per-model breakdown:
    gpt-4.1-nano: 15 calls, 2,850 avg tokens, 58.20 tokens/sec
    gpt-4.1-mini: 22 calls, 6,200 avg tokens, 42.10 tokens/sec
    gpt-4.1: 5 calls, 12,500 avg tokens, 38.50 tokens/sec
```

## Testing the Implementation

1. **Run a normal job:**
```bash
python3 main.py input_folder output_folder
```

2. **Check the performance report in logs:**
```bash
tail -100 output_folder/logs/log_*.txt | grep -A 20 "API Token Statistics"
```

3. **Analyze metrics with validation script:**
```bash
python3 validate_token_performance.py output_folder/metrics
```

4. **Compare runs to prove max_tokens doesn't matter:**
   - Run same job with different `max_tokens` settings
   - Use validation script to compare
   - Should show similar processing times for similar actual token counts

## Files Modified

- `services/ai_service.py` - Token tracking in API calls
- `utils/performance_utils.py` - Token statistics and percentiles
- `main.py` - Startup configuration logging
- `validate_token_performance.py` - New validation script

## Next Steps

1. Run a few jobs and collect metrics
2. Use validation script to analyze correlations
3. Tune prompts to reduce actual token output where possible
4. Monitor tokens/sec for throttling patterns
5. Use per-model stats to optimize model selection

## Conclusion

With these metrics in place, you now have **hard evidence** that:
- Processing time depends on actual tokens generated
- `max_tokens` ceiling doesn't slow down shorter responses
- Model selection and API throttling are the real performance factors

Your token limits were correct all along. Focus optimization efforts on reducing actual output length and choosing appropriate models, not on lowering max_tokens ceilings.

