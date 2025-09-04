# Performance Documentation

## Overview

This document provides comprehensive performance information for the Ohmni Oracle Template system, including baselines, troubleshooting guides, and optimization strategies.

## 🚀 Performance Baselines

### Standard Configuration Performance
- **First run (uncached)**: ~3-4 minutes for 9 PDFs
- **Cached runs**: ~11 seconds for 9 PDFs  
- **Extraction**: <1 second per PDF
- **AI Processing**: 2-5 seconds per PDF (cached)

### Performance by Document Type
| Drawing Type | Processing Time | Notes |
|--------------|----------------|-------|
| Electrical | 60-90 seconds | Includes complex panel schedules |
| Mechanical | 50-85 seconds | Equipment schedules can be complex |
| Plumbing | 55-80 seconds | Fixture schedules vary in complexity |
| Architectural | 45-65 seconds | Floor plans and room details |
| Technology | 15-25 seconds | Usually simple, text-heavy |
| Equipment | 12-20 seconds | Simple equipment lists |

## ⚠️ Critical Performance Gotchas

### 1. Table Extraction Slowdown
**Problem**: `ENABLE_TABLE_EXTRACTION=true` causes 27x slowdown in extraction
- **Default**: `false` (fast)
- **Impact**: Extraction goes from <1 second to 13+ seconds per PDF
- **Fix**: Always set `ENABLE_TABLE_EXTRACTION=false` unless you specifically need table detection

### 2. AI Cache Disabled
**Problem**: `ENABLE_AI_CACHE=false` causes 28-38x slowdown in processing
- **Default**: `false` (slow)
- **Impact**: Processing goes from ~11 seconds to 3-4 minutes for 9 PDFs
- **Fix**: Always set `ENABLE_AI_CACHE=true` in production

### 3. Model Selection Impact
**Problem**: `FORCE_MINI_MODEL=true` can reduce accuracy for complex documents
- **Default**: `false` (balanced)
- **Impact**: 29% faster uncached processing, but may reduce quality
- **Trade-off**: Speed vs. accuracy - use for development/testing only

## 🔧 Performance Configuration

### Required Settings (.env)
```bash
# CRITICAL: Prevents 27x extraction slowdown
ENABLE_TABLE_EXTRACTION=false

# CRITICAL: Enables 28-38x performance improvement
ENABLE_AI_CACHE=true
AI_CACHE_TTL_HOURS=24

# CRITICAL: Cache directory (default: .ai_cache)
AI_CACHE_DIR=.ai_cache
```

### Optional Performance Settings
```bash
# Trade accuracy for speed (development only)
FORCE_MINI_MODEL=false

# Optimize for specific document types
USE_4O_FOR_SCHEDULES=true

# Control concurrency
MAX_CONCURRENT_API_CALLS=20
BATCH_SIZE=10
```

## 📊 Performance Monitoring

### Key Metrics to Watch
1. **Extraction Time**: Should be <1 second per PDF
2. **AI Processing Time**: Should be 2-5 seconds per PDF (cached)
3. **Total Processing Time**: Should be <15 seconds for 9 PDFs (cached)
4. **Cache Hit Rate**: Should be >90% after first run

### Performance Degradation Detection
The system automatically detects significant performance slowdowns:
- API response times >2x historical average
- Extraction times >5 seconds per PDF
- Total processing time >2x expected baseline

## 🚨 Troubleshooting Common Issues

### "Why is extraction taking 13+ seconds?"
**Cause**: `ENABLE_TABLE_EXTRACTION=true`
**Solution**: Set to `false` in `.env`
**Impact**: 27x speed improvement

### "Why are cached runs still slow?"
**Causes**:
1. Cache directory doesn't exist
2. Cache TTL expired
3. Cache disabled
4. Different input content

**Solutions**:
1. Check `AI_CACHE_DIR` exists and is writable
2. Verify `AI_CACHE_TTL_HOURS` setting
3. Confirm `ENABLE_AI_CACHE=true`
4. Check if PDF content changed

### "Why can't I reproduce May's performance?"
**Cause**: May tests were using cached responses
**Solution**: 
1. First run will always be slower (3-4 minutes)
2. Subsequent runs with same content will be fast (~11 seconds)
3. Check cache directory and settings

### "Why is AI processing taking 2+ minutes per PDF?"
**Causes**:
1. API rate limiting
2. Large document content
3. Model selection issues
4. Network latency

**Solutions**:
1. Check `MAX_CONCURRENT_API_CALLS` setting
2. Verify `MODEL_UPGRADE_THRESHOLD` (default: 15000 chars)
3. Use `FORCE_MINI_MODEL=true` for development
4. Check network connectivity

## 📈 Performance Optimization Strategies

### 1. Cache Optimization
- **TTL Strategy**: Set `AI_CACHE_TTL_HOURS=24` for daily processing
- **Cache Location**: Use fast storage (SSD) for cache directory
- **Cache Cleanup**: Monitor cache size and clean old files

### 2. Concurrency Tuning
- **API Calls**: Start with `MAX_CONCURRENT_API_CALLS=20`
- **Batch Size**: Use `BATCH_SIZE=10` for most workloads
- **Monitor**: Watch for rate limiting or memory issues

### 3. Model Selection
- **Default**: Use GPT-4o-mini for most documents
- **Upgrade Threshold**: Set `MODEL_UPGRADE_THRESHOLD=15000` characters
- **Schedules**: Use `USE_4O_FOR_SCHEDULES=true` for complex schedules

### 4. Extraction Optimization
- **Table Detection**: Always disable unless specifically needed
- **Text Processing**: Focus on text extraction, not table structure
- **Memory**: Monitor memory usage during large batch processing

## 🔍 Performance Testing

### Test Scenarios
1. **Cold Start**: First run with no cache
2. **Warm Start**: Subsequent runs with cache
3. **Mixed Content**: Different document types and sizes
4. **Stress Test**: Large batch processing

### Benchmark Commands
```bash
# Test single PDF
python main.py /path/to/single/pdf /path/to/output

# Test batch processing
python main.py /path/to/pdf/folder /path/to/output

# Monitor performance metrics
cat /path/to/output/metrics/metrics_*.json
```

### Expected Results
- **Cold Start**: 3-4 minutes for 9 PDFs
- **Warm Start**: 10-15 seconds for 9 PDFs
- **Extraction**: <1 second per PDF
- **AI Processing**: 2-5 seconds per PDF (cached)

## 📚 Historical Performance Data

### May 2025 Test Results
- **Best Performance**: 51.42 seconds average per document
- **Performance Improvement**: 41.2% improvement over initial tests
- **Key Optimization**: Model selection and caching configuration

### Performance Trends
- **Extraction**: Stable at 7.5-8.9 seconds across all tests
- **AI Processing**: Improved from 69s to 43s average
- **API Efficiency**: Reduced from 90% to 83% of total time

## 🎯 Performance Goals

### Short Term (<1 month)
- Maintain <1 second extraction time
- Achieve >90% cache hit rate
- Keep total processing <15 seconds for 9 PDFs (cached)

### Medium Term (1-3 months)
- Reduce cold start time by 20%
- Optimize model selection logic
- Implement adaptive concurrency

### Long Term (3+ months)
- Achieve <10 seconds total processing for 9 PDFs (cached)
- Implement intelligent caching strategies
- Add performance prediction models

## 📞 Getting Help

### Performance Issues
1. Check this document first
2. Review `.env` configuration
3. Check cache directory and settings
4. Monitor performance metrics
5. Contact development team with metrics data

### Performance Questions
- Include performance metrics from output
- Specify configuration settings
- Describe expected vs. actual performance
- Provide document types and sizes

---

**Last Updated**: December 2025  
**Version**: 1.0  
**Maintainer**: Development Team
