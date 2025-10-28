#!/usr/bin/env python3
"""
Quick test to verify token metrics implementation works correctly.
Tests the enhanced performance tracker without requiring full job run.
"""
import sys
from utils.performance_utils import PerformanceTracker


def test_token_metrics():
    """Test token metrics tracking and reporting"""
    print("Testing Token Metrics Implementation...")
    print()
    
    tracker = PerformanceTracker()
    
    # Simulate some API calls with token data
    print("Simulating API calls with token data...")
    
    # Call 1: gpt-4.1-nano (fast, small)
    tracker.add_metric_with_context(
        category="api_request",
        duration=2.5,
        file_path="test1.pdf",
        drawing_type="Electrical",
        model="gpt-4.1-nano",
        api_type="chat",
        prompt_tokens=1200,
        completion_tokens=2800,
        total_tokens=4000,
        tokens_per_second=1120.0,
        max_tokens_param=32000,
    )
    
    # Call 2: gpt-4.1-mini (medium)
    tracker.add_metric_with_context(
        category="api_request",
        duration=8.3,
        file_path="test2.pdf",
        drawing_type="Architectural",
        model="gpt-4.1-mini",
        api_type="chat",
        prompt_tokens=3500,
        completion_tokens=6200,
        total_tokens=9700,
        tokens_per_second=747.0,
        max_tokens_param=32000,
    )
    
    # Call 3: gpt-4.1-mini (another one)
    tracker.add_metric_with_context(
        category="api_request",
        duration=5.2,
        file_path="test3.pdf",
        drawing_type="Mechanical",
        model="gpt-4.1-mini",
        api_type="chat",
        prompt_tokens=2800,
        completion_tokens=5100,
        total_tokens=7900,
        tokens_per_second=980.0,
        max_tokens_param=32000,
    )
    
    # Call 4: gpt-4.1 (large, slow)
    tracker.add_metric_with_context(
        category="api_request",
        duration=18.7,
        file_path="test4.pdf",
        drawing_type="Plumbing",
        model="gpt-4.1",
        api_type="chat",
        prompt_tokens=8500,
        completion_tokens=12500,
        total_tokens=21000,
        tokens_per_second=668.0,
        max_tokens_param=32000,
    )
    
    # Call 5: Cache hit (should not affect API stats)
    tracker.add_metric_with_context(
        category="api_cache_hit",
        duration=0.0,
        file_path="test5.pdf",
        drawing_type="Electrical",
        model="gpt-4.1-mini",
        api_type="chat",
        cache_hit=True,
    )
    
    print("✅ Added 4 API calls + 1 cache hit")
    print()
    
    # Generate report
    print("Generating performance report...")
    print()
    tracker.log_report()
    
    # Get report data
    report = tracker.report()
    
    # Validate token statistics
    print()
    print("=" * 80)
    print("VALIDATION CHECKS:")
    print("=" * 80)
    
    checks_passed = 0
    checks_failed = 0
    
    # Check 1: Token statistics exist
    if "api_token_statistics" in report:
        print("✅ Token statistics present in report")
        checks_passed += 1
    else:
        print("❌ Token statistics missing from report")
        checks_failed += 1
    
    # Check 2: Sample count correct (4 API calls, not including cache hit)
    token_stats = report.get("api_token_statistics", {})
    if token_stats.get("samples") == 4:
        print("✅ Sample count correct (4 API calls, cache hit excluded)")
        checks_passed += 1
    else:
        print(f"❌ Sample count incorrect: {token_stats.get('samples')} (expected 4)")
        checks_failed += 1
    
    # Check 3: Percentiles exist
    if "completion_tokens_percentiles" in token_stats:
        print("✅ Completion tokens percentiles calculated")
        checks_passed += 1
    else:
        print("❌ Completion tokens percentiles missing")
        checks_failed += 1
    
    # Check 4: Per-model breakdown exists
    if "per_model" in token_stats and len(token_stats["per_model"]) == 3:
        print("✅ Per-model breakdown present (3 models)")
        checks_passed += 1
    else:
        print(f"❌ Per-model breakdown incorrect: {len(token_stats.get('per_model', {}))} models")
        checks_failed += 1
    
    # Check 5: API statistics exist
    if "api_statistics" in report:
        api_stats = report["api_statistics"]
        if api_stats.get("count") == 4:
            print("✅ API statistics count correct (4 calls)")
            checks_passed += 1
        else:
            print(f"❌ API statistics count incorrect: {api_stats.get('count')}")
            checks_failed += 1
    else:
        print("❌ API statistics missing")
        checks_failed += 1
    
    # Check 6: Cache hits tracked separately
    if "api_cache_hit" in tracker.metrics and len(tracker.metrics["api_cache_hit"]) == 1:
        print("✅ Cache hits tracked separately")
        checks_passed += 1
    else:
        print("❌ Cache hit tracking failed")
        checks_failed += 1
    
    print()
    print("=" * 80)
    print(f"RESULTS: {checks_passed} passed, {checks_failed} failed")
    print("=" * 80)
    print()
    
    if checks_failed == 0:
        print("🎉 All checks passed! Token metrics implementation is working correctly.")
        return 0
    else:
        print("⚠️  Some checks failed. Review implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(test_token_metrics())

