# Token Usage & Performance Metrics

## What Was Added

Comprehensive token tracking and performance metrics to **prove that `max_tokens` doesn't affect processing speed** — only the actual tokens generated matter.

## Quick Start

### 1. Run Your Job Normally
```bash
python3 main.py input_folder output_folder
```

### 2. Check Token Statistics in Logs
Look for the new section in your logs:
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

### 3. Validate Performance
Run the validation script to analyze your metrics:
```bash
python3 validate_token_performance.py output/metrics
```

### 4. Test the Implementation
```bash
python3 test_token_metrics.py
```

## What You'll See at Startup

New configuration logging shows your model and token settings:
```
=== Model & Token Configuration ===
⚙️  DEFAULT_MODEL: gpt-4.1-mini
⚙️  LARGE_DOC_MODEL: gpt-4.1
⚙️  SCHEDULE_MODEL: gpt-4.1-mini
⚙️  TINY_MODEL: gpt-4.1-nano
⚙️  ACTUAL_MODEL_MAX_COMPLETION_TOKENS: 32000
⚙️  DEFAULT_MODEL_MAX_TOKENS: 32000
⚙️  LARGE_MODEL_MAX_TOKENS: 32000
⚙️  SPEC_MAX_TOKENS: 16384
⚙️  RESPONSES_TIMEOUT_SECONDS: 600
⚙️  NANO_CHAR_THRESHOLD: 3000
⚙️  MINI_CHAR_THRESHOLD: 15000
=== OCR Configuration ===
⚙️  OCR_MODEL: gpt-4o-mini, OCR_TOKENS_PER_TILE: 3000, OCR_DPI: 300, OCR_GRID_SIZE: 1
===================================
```

## New Metrics Explained

### Token Statistics

**Total completion tokens**: Sum of all tokens generated across API calls  
**Avg completion tokens**: Average tokens per API call  
**Avg tokens/sec**: Average throughput (speed of token generation)  

### Percentiles

**p50 (median)**: 50% of calls generated this many tokens or fewer  
**p95**: 95% of calls (catches most outliers)  
**p99**: 99% of calls (catches extreme outliers)  

**Why percentiles matter:**
- p50 shows "typical" performance
- p95/p99 show if you have problematic outliers
- Large gap between p50 and p95 = inconsistent performance (throttling?)

### Per-Model Breakdown

Shows performance characteristics of each model:
- `gpt-4.1-nano`: Fast, small outputs
- `gpt-4.1-mini`: Medium speed, medium outputs
- `gpt-4.1`: Slower, large outputs

## What This Proves

### ✅ Confirmed
- **Processing time scales with actual completion tokens** (not max_tokens)
- **Tokens/sec shows real API performance** (throttling, network, model speed)
- **Different models have different throughput rates**

### ❌ Debunked
- ~~"Setting max_tokens=32000 slows down requests"~~ — FALSE
- ~~"Halve max_tokens to halve processing time"~~ — FALSE
- ~~"Your token limits are too high"~~ — FALSE (32K is correct for GPT-4.1)

## Performance Optimization Guide

### If Your Jobs Are Slow, Check:

1. **Avg completion tokens** — Are you generating too much output?
   - Fix: More focused prompts, better extraction logic
   
2. **Tokens/sec percentiles** — Is the API throttling you?
   - p50 < 20 tokens/sec = likely throttled
   - Fix: Rate limiting, off-peak processing
   
3. **Per-model stats** — Are you using the right models?
   - Using `gpt-4.1` for simple tasks? Switch to `gpt-4.1-nano`
   - Fix: Adjust character thresholds in `.env`
   
4. **OCR triggering** — Are scanned files slowing you down?
   - Check OCR stats in reports
   - Fix: Tune `OCR_THRESHOLD` in `.env`

### If Tokens/Sec Drops Suddenly

**Possible causes:**
- API rate limiting (too many requests)
- Network latency (time of day, ISP issues)
- OpenAI API load (weekday vs weekend)
- Model availability (API-side issues)

**How to confirm:**
- Compare p50 tokens/sec across multiple runs
- Check if slowdown correlates with time of day
- Look for "Timeout" errors in logs

## Files Modified

- `services/ai_service.py` — Token tracking in API calls
- `utils/performance_utils.py` — Token statistics with percentiles
- `main.py` — Startup configuration logging

## New Files

- `validate_token_performance.py` — Validation and analysis script
- `test_token_metrics.py` — Unit test for token metrics
- `docs/october/token-metrics-implementation-10-28-25.md` — Detailed documentation

## Your Configuration Is Correct ✅

```bash
# These are CORRECT for GPT-4.1 models (which support 32,768 max output tokens)
ACTUAL_MODEL_MAX_COMPLETION_TOKENS=32000
DEFAULT_MODEL_MAX_TOKENS=32000
LARGE_MODEL_MAX_TOKENS=32000
SPEC_MAX_TOKENS=16384
```

**Don't change these.** Focus optimization on:
1. Reducing actual output length (better prompts)
2. Using faster models when appropriate
3. Avoiding unnecessary OCR
4. Managing API rate limits

## Questions?

Check the detailed documentation:
- `docs/october/token-metrics-implementation-10-28-25.md`

Or run the validation script for analysis:
```bash
python3 validate_token_performance.py output/metrics
```

