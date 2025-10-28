## 🎉 **TEST 7 RESULTS: NEW RECORD!**

Okay, THIS is excellent news. Let me show you what you just "accidentally" discovered:

---

## 📊 The Complete Picture (All Tests)

| Test | Overall Avg | E0.01-SPEC | Status |
|------|-------------|------------|--------|
| Test 3 | 72.0s | 155s | ✅ Baseline |
| Test 4 | 129.0s | 388s | ❌ Anomaly |
| Test 5 | 70.0s | 152s | ✅ Normal |
| Test 6 | 63.5s | 113s | 🏆 Great |
| **Test 7** | **59.8s** | **100.8s** | 🏆🏆 **BEST EVER** |

---

## 🔥 What Test 7 Tells Us

### 1. **Your System Is STABLE and OPTIMAL**

You just ran **4 consecutive good tests** (Tests 3, 5, 6, 7) with results in the **60-72s range**.

The variance is purely **API throughput**:

| Test | API Tokens/sec | E0.01-SPEC Time |
|------|---------------|-----------------|
| Test 5 | ~80 | 152s |
| Test 6 | 110 | 113s |
| **Test 7** | **125** | **100.8s** ✅ |

**Test 7 got the fastest API server response** - 125 tokens/second is **excellent** for gpt-4.1.

### 2. **The E0.01-SPEC Output Is Consistent**

Look at the completion tokens:
- Test 6: 12,187 tokens
- Test 7: 12,327 tokens

**Difference: 140 tokens (1%)** - basically identical!

Your prompt is producing **consistent, structured output** regardless of API speed.

### 3. **Your Configuration Is LOCKED IN** ✅

```bash
SPEC_MAX_TOKENS=16384
DEFAULT_MODEL=gpt-4.1-mini
LARGE_DOC_MODEL=gpt-4.1
```

This is **perfect**. The spec file naturally produces ~12K tokens, well within the 16K limit.

---

## 📈 The Natural Performance Range

Based on 4 good tests, here's your **true baseline**:

### Overall Average Per File
- **Best case:** 59.8s (Test 7) ← optimal API
- **Typical case:** 63-72s (Tests 3, 5, 6) ← normal API
- **Warning threshold:** >90s ← investigate

### E0.01-SPEC (Your Canary File)
- **Best case:** 100-113s (Tests 6, 7) ← fast API
- **Typical case:** 150-155s (Tests 3, 5) ← normal API
- **Warning threshold:** >200s ← regression

### E5.00-PANEL
- **Expected:** 95-105s
- **Warning threshold:** >130s

### M6.01-MECH
- **Expected:** 100-115s
- **Warning threshold:** >140s

---

## 🎯 **CRITICAL INSIGHT: API Variance Is Random**

Look at this:

```
Test 5 → Test 6: 152s → 113s (39s improvement!)
Test 6 → Test 7: 113s → 101s (12s improvement!)
```

**You didn't change ANYTHING** between these tests. Same code, same config, same files.

**The difference is 100% OpenAI API server mood:**
- Low server load → Fast (125 tokens/sec)
- Medium load → Normal (110 tokens/sec)
- High load → Slower (80 tokens/sec)

You have **ZERO control** over this. It's like measuring your commute time - some days traffic is light, some days it's heavy.

---

## ✅ What This Means For You

### You're Done Testing! 🎉

You have **enough data** to establish your baseline:

**Expected Performance:**
- Overall: **60-75 seconds per file**
- Specs: **100-160 seconds**
- Panels: **95-110 seconds**
- Mechanicals: **100-115 seconds**

**Regression Threshold (trigger investigation):**
- Overall: **>90 seconds per file**
- Specs: **>200 seconds**
- Panels: **>130 seconds**
- Mechanicals: **>140 seconds**

---

## 🚀 UPDATED CURSOR AGENT PROMPT

Here's your **final, ready-to-use prompt** with Test 7 data included:

```
You are updating the performance baseline documentation and adding automated regression detection to the ohmni-oracle-v3 project.

## TASK 1: Create docs/PERFORMANCE.md

Create the file `docs/PERFORMANCE.md` with this content:

```markdown
# Performance Baseline

## Test Environment
- **Baseline Established:** October 28, 2025
- **Test Suite:** 9 PDF files (Architectural, Electrical, Mechanical, Plumbing, Technology, Equipment)
- **Configuration:** Commit 47822d5 (optimal prompt structure)
- **Model Configuration:**
  - DEFAULT_MODEL: gpt-4.1-mini
  - LARGE_DOC_MODEL: gpt-4.1
  - SCHEDULE_MODEL: gpt-4.1-mini
  - TINY_MODEL: gpt-4.1-nano

## Expected Processing Times

### Overall Performance
- **Best Case:** 60 seconds per file (optimal API conditions)
- **Typical Case:** 63-75 seconds per file (normal API variance)
- **Regression Threshold:** >90 seconds per file (investigate immediately)

### Individual File Expectations

| File Type | Best Case | Typical Case | Regression Threshold |
|-----------|-----------|--------------|---------------------|
| **E0.01-SPECIFICATIONS** | 100-113s | 150-160s | >200s |
| **E5.00-PANEL-SCHEDULES** | 95-98s | 100-105s | >130s |
| **M6.01-MECHANICAL-SCHEDULES** | 105-111s | 110-115s | >140s |
| **P6.01-PLUMBING-SCHEDULES** | 61-66s | 66-70s | >90s |
| **E1.00-LIGHTING-FLOOR** | 52-60s | 55-65s | >80s |
| **A2.2-FLOOR-PLAN** | 37-66s | 60-70s | >90s |

## Performance Test History

### Test 3 (Oct 28, 11:46am) - Pre-Refactor Baseline
- Overall average: 72s
- E0.01-SPEC: 155s
- Status: ✅ Normal performance

### Test 4 (Oct 28, 2:45pm) - Deployment Anomaly
- Overall average: 129s
- E0.01-SPEC: 388s
- Status: ❌ Regression (mid-deploy, prompt registry incomplete)
- **Root Cause:** Code deployed during refactor with incomplete registry

### Test 5 (Oct 28, 3:53pm) - Post-Refactor Validation
- Overall average: 70s
- E0.01-SPEC: 152s
- API throughput: ~80 tokens/sec
- Status: ✅ Normal performance with new prompt

### Test 6 (Oct 28, 4:29pm) - Fast API Response
- Overall average: 63.5s
- E0.01-SPEC: 113s
- API throughput: 110 tokens/sec
- Status: ✅ Great performance

### Test 7 (Oct 28, 5:13pm) - Optimal API Response
- Overall average: **59.8s** ← **BEST EVER**
- E0.01-SPEC: **100.8s** ← **BEST EVER**
- API throughput: 125 tokens/sec
- Status: ✅ Optimal performance (fast API servers)

## Understanding API Variance

Performance naturally varies by 15-25% due to:
- **OpenAI Server Load:** Low load = 125 tokens/sec, High load = 80 tokens/sec
- **Network Latency:** Internet routing and connection quality
- **Token Generation Speed:** API internal processing variance

**This variance is NORMAL and UNCONTROLLABLE.**

### Example: E0.01-SPEC Variance
- Test 7 (optimal API): 100.8s @ 125 tokens/sec
- Test 6 (good API): 113.4s @ 110 tokens/sec  
- Test 5 (normal API): 152.0s @ 80 tokens/sec
- **Same code, same config, same file** - different API throughput

### When to Investigate
- ✅ **60-75s average:** Normal variance - no action needed
- ⚠️ **75-90s average:** Mild slowdown - monitor next run
- ❌ **>90s average:** Regression - investigate immediately

## Configuration (Locked - DO NOT CHANGE)

These settings produce optimal performance:

```bash
# Model Selection
DEFAULT_MODEL=gpt-4.1-mini          # Schedules, structured data
LARGE_DOC_MODEL=gpt-4.1              # Specifications, complex docs
SCHEDULE_MODEL=gpt-4.1-mini          # Panel/equipment schedules
TINY_MODEL=gpt-4.1-nano              # Simple extractions (<3K chars)

# Token Limits
SPEC_MAX_TOKENS=16384                # Specs naturally output ~12K
DEFAULT_MODEL_MAX_TOKENS=32000       # Schedules use 10-11K
LARGE_MODEL_MAX_TOKENS=32000         # Full model ceiling
ACTUAL_MODEL_MAX_COMPLETION_TOKENS=32000

# Character-Based Model Selection
NANO_CHAR_THRESHOLD=3000             # <3K chars → use nano
MINI_CHAR_THRESHOLD=15000            # 3K-15K → use mini, >15K → full

# Timeouts & Safety
RESPONSES_TIMEOUT_SECONDS=600        # 10-minute max per file
GPT5_FAILURE_THRESHOLD=3             # Retry attempts
```

## Token Output Consistency

The structured prompt produces **consistent output sizes**:

| File | Typical Output | Range |
|------|----------------|-------|
| E0.01-SPEC | 12,200 tokens | 12,100-12,400 |
| E5.00-PANEL | 10,900 tokens | 10,400-10,900 |
| M6.01-MECH | 10,800 tokens | 10,700-10,900 |

**Variance: <5%** - confirms prompt is working correctly.

## When to Run Performance Tests

### DO Test When:
- ✅ Changing prompt templates (GENERAL or specialized prompts)
- ✅ Modifying model selection logic (`optimize_model_parameters`)
- ✅ Adjusting token limits (SPEC_MAX_TOKENS, etc.)
- ✅ Updating PDF extraction logic (PyMuPDF settings)
- ✅ Before production deployment (final validation)
- ✅ After detecting regression (diagnose root cause)

### DON'T Test For:
- ❌ Confirming good results (variance is random)
- ❌ Hunting for "perfect" sub-60s runs (API-dependent)
- ❌ Daily performance checks (adds no value)
- ❌ After minor code changes (unrelated to extraction/AI)

## Troubleshooting Performance Issues

### Symptom: Overall average >90s
**Possible Causes:**
1. API slowdown (check OpenAI status page)
2. Prompt regression (check recent commits)
3. Network connectivity issues
4. Model configuration changes

**Action:** Review recent commits, check API status, run test again

### Symptom: Single file >2x baseline
**Possible Causes:**
1. File-specific prompt issue
2. Unexpected file format/content
3. OCR triggered unnecessarily

**Action:** Check file's extracted text, review prompt for that type

### Symptom: All files consistently slow (>90s avg for 3+ runs)
**Possible Causes:**
1. Code regression (bad deploy)
2. Prompt changes causing verbosity
3. Model selection logic broken

**Action:** Git bisect to find breaking commit, compare token outputs

## Success Metrics

Your system is performing optimally when:
- ✅ Overall average: 60-75 seconds per file
- ✅ E0.01-SPEC: 100-160 seconds
- ✅ Token outputs stable (~12K for specs, ~11K for schedules)
- ✅ No timeouts or errors
- ✅ JSON parsing success rate: 100%
```

## TASK 2: Add Regression Detection to utils/performance_utils.py

Add this code at the end of `utils/performance_utils.py` (before any main block):

```python
# =============================================================================
# PERFORMANCE BASELINE & REGRESSION DETECTION
# =============================================================================

# Performance baseline thresholds (in seconds)
# Based on 4 stable test runs (Tests 3, 5, 6, 7) from Oct 28, 2025
PERFORMANCE_BASELINE = {
    "overall_average": 75,  # Warning if avg exceeds this
    "overall_regression": 90,  # Critical if avg exceeds this
    
    # Individual file thresholds (warning level)
    "E0.01-SPECIFICATIONS-Rev.3.pdf": 200,
    "E5.00-PANEL-SCHEDULES-Rev.3 copy.pdf": 130,
    "M6.01-MECHANICAL---SCHEDULES-Rev.3.pdf": 140,
    "P6.01-PLUMBING---SCHEDULES-Rev.2.pdf": 90,
    "E1.00-LIGHTING---FLOOR-LEVEL-Rev.3.pdf": 80,
    "A2.2-DIMENSION-FLOOR-PLAN-Rev.3.pdf": 90,
}


def check_performance_regression(metrics: Dict[str, Any], run_id: str) -> bool:
    """
    Check if current run shows performance regression compared to baseline.
    
    Analyzes both overall average and individual file performance to detect:
    - API slowdowns (temporary, all files affected)
    - Code regressions (permanent, all files affected)
    - File-specific issues (single file affected)
    
    Args:
        metrics: Performance metrics dictionary from get_metrics()
        run_id: Run identifier for logging
        
    Returns:
        True if regression detected, False otherwise
        
    Example:
        >>> tracker = get_tracker()
        >>> has_regression = check_performance_regression(
        ...     tracker.get_metrics(), 
        ...     "20251028_171343"
        ... )
        >>> if has_regression:
        ...     logging.warning("Performance regression detected!")
    """
    logger = logging.getLogger(__name__)
    
    # Extract metrics
    total_processing = metrics.get("total_processing", {})
    overall_avg = total_processing.get("overall_average", 0)
    
    # Check overall performance
    baseline_avg = PERFORMANCE_BASELINE["overall_average"]
    regression_threshold = PERFORMANCE_BASELINE["overall_regression"]
    
    if overall_avg > regression_threshold:
        # CRITICAL regression
        logger.error(f"⛔ CRITICAL PERFORMANCE REGRESSION in run {run_id}")
        logger.error(f"   Overall average: {overall_avg:.1f}s")
        logger.error(f"   Baseline: {baseline_avg}s | Threshold: {regression_threshold}s")
        logger.error(f"   Exceeded baseline by {((overall_avg / baseline_avg - 1) * 100):.1f}%")
        
        _log_problem_files(total_processing, logger)
        _log_regression_causes(logger, critical=True)
        
        return True
        
    elif overall_avg > baseline_avg:
        # WARNING - mild slowdown
        logger.warning(f"⚠️  PERFORMANCE WARNING in run {run_id}")
        logger.warning(f"   Overall average: {overall_avg:.1f}s (baseline: {baseline_avg}s)")
        logger.warning(f"   {((overall_avg / baseline_avg - 1) * 100):.1f}% over baseline (still acceptable)")
        
        # Check if specific files are problematic
        problem_files = _check_individual_files(total_processing)
        if problem_files:
            logger.warning(f"   Problem files detected: {len(problem_files)}")
            for file_info in problem_files:
                logger.warning(
                    f"     ❌ {file_info['name']}: {file_info['duration']:.1f}s "
                    f"(expected <{file_info['threshold']}s)"
                )
        else:
            logger.warning("   All individual files within thresholds - likely API slowdown")
        
        return False  # Don't flag as regression, just a warning
        
    else:
        # GOOD performance
        logger.info(f"✅ Performance within baseline for run {run_id}")
        logger.info(f"   Overall average: {overall_avg:.1f}s (baseline: {baseline_avg}s)")
        
        # Show top 3 slowest for context
        slowest_ops = total_processing.get("slowest_operations", [])
        if slowest_ops:
            logger.info("   Top 3 slowest files:")
            for i, op in enumerate(slowest_ops[:3], 1):
                file_name = op.get("file_name", "unknown")
                duration = op.get("duration", 0)
                
                # Check if this file is within its individual threshold
                threshold = PERFORMANCE_BASELINE.get(file_name)
                status = "✅" if threshold and duration < threshold else "⚠️"
                
                logger.info(f"     {i}. {status} {file_name}: {duration:.1f}s")
        
        return False


def _check_individual_files(total_processing: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Check if individual files exceed their thresholds."""
    problem_files = []
    slowest_ops = total_processing.get("slowest_operations", [])
    
    for op in slowest_ops:
        file_name = op.get("file_name", "")
        duration = op.get("duration", 0)
        
        if file_name in PERFORMANCE_BASELINE:
            threshold = PERFORMANCE_BASELINE[file_name]
            if duration > threshold:
                problem_files.append({
                    "name": file_name,
                    "duration": duration,
                    "threshold": threshold,
                    "percent_over": ((duration / threshold - 1) * 100)
                })
    
    return problem_files


def _log_problem_files(total_processing: Dict[str, Any], logger) -> None:
    """Log detailed information about problem files."""
    logger.error("")
    logger.error("   📋 Problem Files:")
    
    problem_files = _check_individual_files(total_processing)
    if problem_files:
        for file_info in problem_files:
            logger.error(
                f"     ❌ {file_info['name']}: {file_info['duration']:.1f}s "
                f"(expected <{file_info['threshold']}s, "
                f"+{file_info['percent_over']:.0f}% over)"
            )
    else:
        logger.error("     ⚠️  All files proportionally slow - likely API slowdown")


def _log_regression_causes(logger, critical: bool = False) -> None:
    """Log possible causes of regression."""
    logger.error("") if critical else logger.warning("")
    
    if critical:
        logger.error("   🔍 Possible Causes (Critical Regression):")
        logger.error("     1. Code regression from recent deploy")
        logger.error("     2. Prompt changes causing verbose output")
        logger.error("     3. Model selection logic broken")
        logger.error("     4. Severe API issues (check status.openai.com)")
        logger.error("")
        logger.error("   🔧 Recommended Actions:")
        logger.error("     1. Review commits since last good run")
        logger.error("     2. Compare token outputs (should be ~12K for specs)")
        logger.error("     3. Check recent prompt changes")
        logger.error("     4. Run test again to rule out API fluke")
    else:
        logger.warning("   🔍 Possible Causes (Mild Slowdown):")
        logger.warning("     - API server load (most likely)")
        logger.warning("     - Network latency")
        logger.warning("     - Temporary OpenAI throttling")
        logger.warning("")
        logger.warning("   💡 This is likely normal variance - monitor next run")
```

## TASK 3: Update main.py to Call Regression Check

Find this section in `main.py` (around line 50-60 in the `main_async` function):

```python
# Save metrics to file for historical comparison
metrics_file = tracker.save_metrics_v2(output_folder, run_id)
if not metrics_file:
    logging.warning(
        "Failed to save performance metrics - check permissions and disk space"
    )
```

Add this immediately after:

```python
# Check for performance regressions
from utils.performance_utils import check_performance_regression
has_regression = check_performance_regression(tracker.get_metrics(), run_id)
if has_regression:
    logging.error("")
    logging.error("="*70)
    logging.error("⛔ PERFORMANCE REGRESSION DETECTED - Review warnings above")
    logging.error("="*70)
```

## TASK 4: Update README.md

Find the appropriate section in README.md (after installation or usage instructions) and add:

```markdown
## Performance

This system processes construction drawings with optimized performance:

### Expected Processing Times
- **Overall average:** 60-75 seconds per file (typical)
- **Specification files:** 100-160 seconds
- **Panel schedules:** 95-110 seconds
- **Mechanical schedules:** 100-115 seconds

### Performance Monitoring
The system includes automated regression detection that alerts when processing times exceed baseline thresholds. Performance naturally varies by 15-25% due to OpenAI API server load - this is normal and expected.

For detailed performance metrics, test history, and troubleshooting guidance, see [docs/PERFORMANCE.md](docs/PERFORMANCE.md).

### When Performance Degrades
If you see processing times >90s per file consistently:
1. Check recent code changes (prompt or model selection)
2. Review API status at status.openai.com
3. Compare token outputs (should be ~12K for specs, ~11K for schedules)
4. See [docs/PERFORMANCE.md](docs/PERFORMANCE.md) for troubleshooting steps
```

## Important Implementation Notes:

1. **The regression detection is conservative** - it only flags critical issues (>90s avg), and gives warnings for mild slowdowns (>75s avg)

2. **The thresholds are based on your actual test data** - they account for natural API variance

3. **The logging is actionable** - it tells you what to check and when to worry

4. **Individual file thresholds** prevent false alarms when one file is slow but others are normal

5. **The code includes helpful docstrings** for future maintainability
```

---

## 🎯 Your Action Plan

### Right Now:
1. ✅ **Copy the cursor prompt above**
2. ✅ **Paste it into Cursor**
3. ✅ **Let it make all the updates**
4. ✅ **Commit with message:** `Add performance baseline docs and regression detection`

### Going Forward:
- **Don't test again unless you change code**
- Your baseline is **60-75s average** (natural variance)
- **Only investigate if** you get 3+ consecutive runs >90s average
- The regression detection will **automatically alert** you if something breaks

---

## 🏆 Final Scorecard

| Metric | Your Status |
|--------|-------------|
| Configuration | ✅ Optimal (commit 47822d5) |
| Prompt | ✅ Structured & specific |
| Token limits | ✅ Correct (16K/32K) |
| Performance baseline | ✅ 60-75s (4 test validation) |
| Best ever | ✅ 59.8s (Test 7) |
| Regression detection | ⏳ About to add |
| Documentation | ⏳ About to add |

**You're ready to ship!** 🚀

Run that cursor prompt and you'll have enterprise-grade performance monitoring in place!

