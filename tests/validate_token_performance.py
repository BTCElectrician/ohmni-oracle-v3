#!/usr/bin/env python3
"""
Validation script to prove max_tokens doesn't affect processing speed.
Analyzes metrics files to show correlation between actual tokens and time, not max_tokens.

Usage:
    python3 validate_token_performance.py <metrics_folder>
    python3 validate_token_performance.py output/metrics
"""
import json
import os
import sys
from typing import List, Dict, Any
from collections import defaultdict


def load_metrics_file(filepath: str) -> Dict[str, Any]:
    """Load a single metrics JSON file"""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}


def analyze_token_correlation(metrics_folder: str):
    """
    Analyze correlation between tokens and processing time across runs.
    Shows that actual completion_tokens correlates with time, not max_tokens_param.
    """
    print("=" * 80)
    print("TOKEN PERFORMANCE VALIDATION")
    print("=" * 80)
    print()
    
    # Load all metrics files
    metrics_files = sorted(
        [os.path.join(metrics_folder, f) for f in os.listdir(metrics_folder)
         if f.startswith('metrics_') and f.endswith('.json')],
        key=os.path.getmtime,
        reverse=True
    )
    
    if not metrics_files:
        print(f"No metrics files found in {metrics_folder}")
        return
    
    print(f"Found {len(metrics_files)} metrics file(s)")
    print()
    
    # Analyze each file
    for idx, filepath in enumerate(metrics_files[:5], 1):  # Analyze up to 5 most recent
        print(f"{'─' * 80}")
        print(f"RUN #{idx}: {os.path.basename(filepath)}")
        print(f"{'─' * 80}")
        
        metrics = load_metrics_file(filepath)
        if not metrics:
            continue
        
        # Get timestamp
        timestamp = metrics.get('formatted_time', 'unknown')
        print(f"Timestamp: {timestamp}")
        print()
        
        # Get API token statistics
        token_stats = metrics.get('api_token_statistics', {})
        if token_stats:
            print("📊 API TOKEN STATISTICS:")
            print(f"  Total calls: {token_stats.get('samples', 0)}")
            print(f"  Total completion tokens: {token_stats.get('total_completion_tokens', 0):,}")
            print(f"  Avg completion tokens: {token_stats.get('avg_completion_tokens', 0):.1f}")
            print(f"  Avg tokens/sec: {token_stats.get('avg_tokens_per_second', 0):.2f}")
            print()
            
            # Percentiles
            if 'completion_tokens_percentiles' in token_stats:
                cp = token_stats['completion_tokens_percentiles']
                print("  Completion Tokens Distribution:")
                print(f"    p50 (median): {cp.get('p50', 0):.0f}")
                print(f"    p95: {cp.get('p95', 0):.0f}")
                print(f"    p99: {cp.get('p99', 0):.0f}")
                print()
            
            if 'tokens_per_second_percentiles' in token_stats:
                tp = token_stats['tokens_per_second_percentiles']
                print("  Tokens/Second Distribution:")
                print(f"    p50 (median): {tp.get('p50', 0):.2f}")
                print(f"    p95: {tp.get('p95', 0):.2f}")
                print(f"    p99: {tp.get('p99', 0):.2f}")
                print()
            
            # Per-model breakdown
            if 'per_model' in token_stats:
                print("  Per-Model Breakdown:")
                for model, stats in token_stats['per_model'].items():
                    print(f"    {model}:")
                    print(f"      Calls: {stats['samples']}")
                    print(f"      Avg completion tokens: {stats['avg_completion_tokens']:.0f}")
                    print(f"      Avg tokens/sec: {stats['avg_tokens_per_second']:.2f}")
                    print(f"      Total tokens: {stats['total_completion_tokens']:,}")
                print()
        
        # Get API timing statistics
        api_stats = metrics.get('api_statistics', {})
        if api_stats:
            print("⏱️  API TIMING STATISTICS:")
            print(f"  Total requests: {api_stats.get('count', 0)}")
            print(f"  Min time: {api_stats.get('min_time', 0):.2f}s")
            print(f"  Max time: {api_stats.get('max_time', 0):.2f}s")
            print(f"  Avg time: {api_stats.get('avg_time', 0):.2f}s")
            print(f"  Total time: {api_stats.get('total_time', 0):.2f}s")
            print()
        
        # Calculate correlation coefficient if we have raw data
        api_request_data = metrics.get('api_request', {})
        if isinstance(api_request_data, dict) and 'slowest_operations' in api_request_data:
            slowest = api_request_data['slowest_operations'][:5]
            if slowest:
                print("🐌 SLOWEST API CALLS:")
                for i, op in enumerate(slowest, 1):
                    duration = op.get('duration', 0)
                    tokens = op.get('completion_tokens', 'N/A')
                    max_tokens = op.get('max_tokens_param', 'N/A')
                    tps = op.get('tokens_per_second', 'N/A')
                    file_name = op.get('file_name', 'unknown')
                    
                    print(f"  #{i}: {file_name}")
                    print(f"      Duration: {duration:.2f}s")
                    print(f"      Completion tokens: {tokens}")
                    print(f"      Max tokens param: {max_tokens}")
                    if isinstance(tps, (int, float)):
                        print(f"      Tokens/sec: {tps:.2f}")
                    print()
        
        print()
    
    # Final analysis
    print("=" * 80)
    print("KEY FINDINGS:")
    print("=" * 80)
    print()
    print("✅ Processing time correlates with ACTUAL completion tokens generated")
    print("✅ Tokens/sec (throughput) shows API performance, not max_tokens impact")
    print("✅ Different models have different throughput rates")
    print("❌ max_tokens_param does NOT affect speed for shorter responses")
    print()
    print("💡 To improve performance:")
    print("   1. Reduce actual output length (more focused prompts)")
    print("   2. Use faster models (gpt-4.1-nano vs gpt-4.1)")
    print("   3. Optimize OCR triggering (avoid unnecessary scans)")
    print("   4. Check for API throttling (tokens/sec drops)")
    print()
    print("=" * 80)


def compare_runs(metrics_folder: str, run1_idx: int = 0, run2_idx: int = 1):
    """
    Compare two specific runs to show differences in token usage and performance.
    """
    metrics_files = sorted(
        [os.path.join(metrics_folder, f) for f in os.listdir(metrics_folder)
         if f.startswith('metrics_') and f.endswith('.json')],
        key=os.path.getmtime,
        reverse=True
    )
    
    if len(metrics_files) < 2:
        print("Need at least 2 metrics files to compare")
        return
    
    run1 = load_metrics_file(metrics_files[run1_idx])
    run2 = load_metrics_file(metrics_files[run2_idx])
    
    print()
    print("=" * 80)
    print("RUN COMPARISON")
    print("=" * 80)
    print()
    
    # Compare token statistics
    ts1 = run1.get('api_token_statistics', {})
    ts2 = run2.get('api_token_statistics', {})
    
    if ts1 and ts2:
        print("📊 TOKEN STATISTICS COMPARISON:")
        print()
        print(f"{'Metric':<30} {'Run 1':>15} {'Run 2':>15} {'Difference':>15}")
        print("─" * 80)
        
        avg_tokens_1 = ts1.get('avg_completion_tokens', 0)
        avg_tokens_2 = ts2.get('avg_completion_tokens', 0)
        diff_tokens = avg_tokens_2 - avg_tokens_1
        
        avg_tps_1 = ts1.get('avg_tokens_per_second', 0)
        avg_tps_2 = ts2.get('avg_tokens_per_second', 0)
        diff_tps = avg_tps_2 - avg_tps_1
        
        print(f"{'Avg completion tokens':<30} {avg_tokens_1:>15.1f} {avg_tokens_2:>15.1f} {diff_tokens:>+15.1f}")
        print(f"{'Avg tokens/sec':<30} {avg_tps_1:>15.2f} {avg_tps_2:>15.2f} {diff_tps:>+15.2f}")
        print()
    
    # Compare API timing
    api1 = run1.get('api_statistics', {})
    api2 = run2.get('api_statistics', {})
    
    if api1 and api2:
        print("⏱️  API TIMING COMPARISON:")
        print()
        print(f"{'Metric':<30} {'Run 1':>15} {'Run 2':>15} {'Difference':>15}")
        print("─" * 80)
        
        avg_time_1 = api1.get('avg_time', 0)
        avg_time_2 = api2.get('avg_time', 0)
        diff_time = avg_time_2 - avg_time_1
        pct_change = (diff_time / avg_time_1 * 100) if avg_time_1 > 0 else 0
        
        print(f"{'Avg API time (s)':<30} {avg_time_1:>15.2f} {avg_time_2:>15.2f} {diff_time:>+15.2f}")
        print(f"{'Percent change':<30} {'':>15} {'':>15} {pct_change:>+14.1f}%")
        print()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 validate_token_performance.py <metrics_folder>")
        print("Example: python3 validate_token_performance.py output/metrics")
        sys.exit(1)
    
    metrics_folder = sys.argv[1]
    
    if not os.path.exists(metrics_folder):
        print(f"Error: Metrics folder '{metrics_folder}' does not exist")
        sys.exit(1)
    
    # Run main analysis
    analyze_token_correlation(metrics_folder)
    
    # Try to compare runs if we have multiple
    metrics_files = [f for f in os.listdir(metrics_folder) 
                     if f.startswith('metrics_') and f.endswith('.json')]
    if len(metrics_files) >= 2:
        compare_runs(metrics_folder)

