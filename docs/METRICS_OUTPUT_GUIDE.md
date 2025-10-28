# Token Metrics Output Guide

## Where Do Token Metrics Go?

### 📊 Metrics JSON File (PRIMARY - Keep this!) — 14KB
**Location:** `output/metrics/metrics_YYYYMMDD_HHMMSS.json`

**Contains:**
- ✅ **Complete token statistics** with all details
- ✅ Percentiles (p50, p95, p99) for completion tokens
- ✅ Percentiles (p50, p95, p99) for tokens/sec  
- ✅ Per-model breakdown with full stats
- ✅ All raw metric data
- ✅ API timing statistics
- ✅ Historical comparison data

**Example structure:**
```json
{
  "api_token_statistics": {
    "samples": 42,
    "total_completion_tokens": 245680,
    "avg_completion_tokens": 5849.5,
    "avg_tokens_per_second": 45.23,
    "completion_tokens_percentiles": {
      "p50": 5200,
      "p95": 12400,
      "p99": 15800
    },
    "tokens_per_second_percentiles": {
      "p50": 42.15,
      "p95": 58.30,
      "p99": 62.10
    },
    "per_model": {
      "gpt-4.1-nano": {
        "samples": 15,
        "avg_completion_tokens": 2850,
        "avg_tokens_per_second": 58.20,
        "total_completion_tokens": 42750
      },
      "gpt-4.1-mini": {
        "samples": 22,
        "avg_completion_tokens": 6200,
        "avg_tokens_per_second": 42.10,
        "total_completion_tokens": 136400
      },
      "gpt-4.1": {
        "samples": 5,
        "avg_completion_tokens": 12500,
        "avg_tokens_per_second": 38.50,
        "total_completion_tokens": 62500
      }
    }
  }
}
```

### 📝 Log File (CONDENSED - Smaller now) — 75KB → ~50KB
**Location:** `output/logs/process_log_YYYYMMDD_HHMMSS.txt`

**Contains (NEW condensed format):**
```
=== API Token Statistics ===
  Samples: 42, Total tokens: 245,680
  Avg: 5850 tokens/call, 45.2 tokens/sec
  💡 Full token details & percentiles → metrics JSON file
```

**If you want full details in logs, set:**
```bash
LOG_LEVEL=DEBUG  # Shows percentiles and per-model breakdown in logs too
```

## Size Comparison

### Before Optimization:
```
Logs:    75 KB (verbose token stats)
Metrics: 14 KB (complete data)
```

### After Optimization (Normal Mode):
```
Logs:    ~50 KB (condensed summary)
Metrics: 14 KB (complete data, unchanged)
```

### Debug Mode (if needed):
```bash
LOG_LEVEL=DEBUG
```
```
Logs:    ~75 KB (full token details in both)
Metrics: 14 KB (complete data, unchanged)
```

## What To Use

### For Analysis & Validation
**Use the Metrics JSON file:**
```bash
# Analyze token performance
python3 validate_token_performance.py output/metrics

# Load in Python
import json
with open("output/metrics/metrics_20251028_123456.json") as f:
    data = json.load(f)
    token_stats = data["api_token_statistics"]
```

### For Quick Checks During Run
**Use the Log file:**
```bash
# Watch progress during run
tail -f output/logs/process_log_*.txt | grep "Token Statistics"

# Check summary after run
grep -A 5 "API Token Statistics" output/logs/process_log_*.txt
```

## Token Metrics Flow

```
┌─────────────────────────────────────┐
│  AI Service API Call                │
│  - Captures tokens from response    │
│  - Calculates tokens/sec            │
└────────────┬────────────────────────┘
             │
             ▼
┌─────────────────────────────────────┐
│  Performance Tracker                │
│  - Stores all token details         │
│  - Calculates percentiles           │
│  - Groups by model                  │
└────────────┬────────────────────────┘
             │
             ├──────────────────────────┐
             ▼                          ▼
┌──────────────────────┐  ┌──────────────────────┐
│  log_report()        │  │  save_metrics_v2()   │
│  → Log File          │  │  → Metrics JSON      │
│  (Condensed)         │  │  (Complete)          │
│  ~3 lines summary    │  │  Full nested data    │
└──────────────────────┘  └──────────────────────┘
```

## Configuration

### Keep Logs Small (DEFAULT):
```bash
LOG_LEVEL=INFO  # Condensed token stats in logs
```

**Log output:**
```
=== API Token Statistics ===
  Samples: 42, Total tokens: 245,680
  Avg: 5850 tokens/call, 45.2 tokens/sec
  💡 Full token details & percentiles → metrics JSON file
```

### Show Everything in Logs (DEBUG):
```bash
LOG_LEVEL=DEBUG  # Full token stats in both logs and JSON
```

**Log output:**
```
=== API Token Statistics ===
  Samples: 42, Total tokens: 245,680
  Avg: 5850 tokens/call, 45.2 tokens/sec
  Completion tokens percentiles - p50: 5200, p95: 12400, p99: 15800
  Tokens/sec percentiles - p50: 42.15, p95: 58.30, p99: 62.10
  Per-model breakdown:
    gpt-4.1-nano: 15 calls, 2850 avg tokens, 58.20 tokens/sec
    gpt-4.1-mini: 22 calls, 6200 avg tokens, 42.10 tokens/sec
    gpt-4.1: 5 calls, 12500 avg tokens, 38.50 tokens/sec
```

## Recommendation

**✅ Use INFO level (default):**
- Keeps log files smaller (~50KB instead of 75KB)
- Shows quick summary during runs
- All details preserved in metrics JSON for analysis
- Best for normal operations

**🔍 Use DEBUG level when troubleshooting:**
- Shows full token details in logs too
- Useful for debugging specific runs
- Can correlate log timestamps with token performance
- Temporary debugging only

## Summary

| Data | Log File (INFO) | Log File (DEBUG) | Metrics JSON |
|------|----------------|------------------|--------------|
| Summary stats | ✅ | ✅ | ✅ |
| Percentiles | ❌ | ✅ | ✅ |
| Per-model breakdown | ❌ | ✅ | ✅ |
| File size | ~50KB | ~75KB | ~14KB |
| Use for | Quick checks | Deep debugging | Analysis & validation |

**Bottom line:** Your token metrics are safely stored in the **metrics JSON file** (which is small and perfect for analysis). Logs now show a condensed summary to keep them smaller.

