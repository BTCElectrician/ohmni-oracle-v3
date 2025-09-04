# Troubleshooting Guide

## Overview

This guide addresses common issues and performance problems encountered when using the Ohmni Oracle Template system. Most issues are related to configuration or performance settings.

## 🚨 Critical Performance Issues

### Issue: Extraction Taking 13+ Seconds Per PDF

**Symptoms**:
- PDF extraction phase is extremely slow
- Processing times are 20-30x slower than expected
- System appears to hang during extraction

**Root Cause**: `ENABLE_TABLE_EXTRACTION=true` in `.env`

**Solution**:
```bash
# In your .env file, set:
ENABLE_TABLE_EXTRACTION=false
```

**Why This Happens**: PyMuPDF table detection is computationally expensive and can slow down extraction by 27x.

**Verification**: Check extraction time - should be <1 second per PDF after fix.

---

### Issue: Cached Runs Still Taking 3+ Minutes

**Symptoms**:
- First run was slow (expected)
- Subsequent runs with same content still slow
- No performance improvement from caching

**Root Causes**:
1. `ENABLE_AI_CACHE=false` in `.env`
2. Cache directory doesn't exist or isn't writable
3. Cache TTL expired
4. Different input content

**Solutions**:
```bash
# 1. Enable caching
ENABLE_AI_CACHE=true

# 2. Set cache TTL (24 hours recommended)
AI_CACHE_TTL_HOURS=24

# 3. Verify cache directory exists
AI_CACHE_DIR=.ai_cache
```

**Verification Steps**:
1. Check if `.ai_cache` directory exists
2. Verify cache files are being created
3. Check cache file timestamps
4. Confirm same PDF content is being processed

---

### Issue: Can't Reproduce May's Performance

**Symptoms**:
- Historical tests showed ~11 seconds for 9 PDFs
- Current tests show 3-4 minutes for same content
- Performance regression investigation needed

**Root Cause**: May tests were using cached responses

**Explanation**:
- **First run (cold start)**: Always 3-4 minutes for 9 PDFs
- **Subsequent runs (cached)**: ~11 seconds for 9 PDFs
- May tests were likely running on previously cached content

**Solution**: 
1. Accept that first run will be slow
2. Ensure caching is properly configured
3. Run multiple times to establish baseline

---

### Issue: AI Processing Taking 2+ Minutes Per PDF

**Symptoms**:
- Individual PDFs taking extremely long to process
- API calls timing out or hanging
- Inconsistent processing times

**Root Causes**:
1. API rate limiting
2. Large document content triggering model upgrade
3. Network latency issues
4. Model selection problems

**Solutions**:
```bash
# 1. Reduce concurrent API calls
MAX_CONCURRENT_API_CALLS=10

# 2. Adjust model upgrade threshold
MODEL_UPGRADE_THRESHOLD=20000

# 3. Force mini model for development
FORCE_MINI_MODEL=true
```

**Verification**: Check API response times in metrics output.

---

### Issue: Memory Usage Too High

**Symptoms**:
- System becomes unresponsive during processing
- Out of memory errors
- Processing fails on large batches

**Root Causes**:
1. Batch size too large
2. Concurrent processing overwhelming system
3. Large PDF files consuming memory

**Solutions**:
```bash
# 1. Reduce batch size
BATCH_SIZE=5

# 2. Reduce concurrent API calls
MAX_CONCURRENT_API_CALLS=10

# 3. Process smaller batches
# Split large folders into smaller subfolders
```

---

### Issue: API Rate Limiting

**Symptoms**:
- API calls failing with rate limit errors
- Inconsistent processing times
- Some PDFs fail while others succeed

**Root Causes**:
1. Too many concurrent API calls
2. OpenAI API quota exceeded
3. Rate limit configuration too aggressive

**Solutions**:
```bash
# 1. Reduce concurrent API calls
MAX_CONCURRENT_API_CALLS=5

# 2. Increase rate limit window
TIME_WINDOW=120

# 3. Check OpenAI API quota
# Visit OpenAI dashboard to verify limits
```

## 🔧 Configuration Issues

### Issue: Environment Variables Not Loading

**Symptoms**:
- Configuration changes not taking effect
- Default values being used instead of custom settings
- Settings appearing to be ignored

**Root Causes**:
1. `.env` file not in correct location
2. Environment variable syntax errors
3. Application not reloading configuration

**Solutions**:
1. Ensure `.env` file is in project root
2. Check syntax (no spaces around `=`)
3. Restart application after changes
4. Verify file permissions

**Example .env syntax**:
```bash
# CORRECT
ENABLE_AI_CACHE=true
AI_CACHE_TTL_HOURS=24

# INCORRECT
ENABLE_AI_CACHE = true
ENABLE_AI_CACHE: true
```

---

### Issue: Cache Directory Problems

**Symptoms**:
- Cache not working despite correct settings
- Permission errors in logs
- Cache files not being created

**Root Causes**:
1. Cache directory doesn't exist
2. Permission issues
3. Disk space problems

**Solutions**:
```bash
# 1. Create cache directory manually
mkdir .ai_cache

# 2. Check permissions
chmod 755 .ai_cache

# 3. Verify disk space
df -h .

# 4. Check if directory is writable
touch .ai_cache/test_file
```

## 📊 Performance Monitoring Issues

### Issue: Performance Metrics Not Generated

**Symptoms**:
- No metrics files in output directory
- Performance data missing from logs
- Can't track system performance

**Root Causes**:
1. Output directory permissions
2. Performance tracking disabled
3. Processing failed before metrics generation

**Solutions**:
1. Check output directory permissions
2. Verify processing completed successfully
3. Check logs for error messages
4. Ensure `DEBUG_MODE=true` for detailed metrics

---

### Issue: Inconsistent Performance Measurements

**Symptoms**:
- Performance varies significantly between runs
- Metrics don't match expected baselines
- Unpredictable processing times

**Root Causes**:
1. Different input content
2. Cache state differences
3. System resource variations
4. Network latency fluctuations

**Solutions**:
1. Use identical input for benchmarking
2. Clear cache between tests if needed
3. Run multiple tests and average results
4. Monitor system resources during processing

## 🐛 Common Error Messages

### "ENABLE_TABLE_EXTRACTION not found in environment"
**Cause**: Environment variable not set
**Solution**: Add `ENABLE_TABLE_EXTRACTION=false` to `.env`

### "Cache directory not writable"
**Cause**: Permission issues with cache directory
**Solution**: Check directory permissions and ownership

### "API rate limit exceeded"
**Cause**: Too many concurrent API calls
**Solution**: Reduce `MAX_CONCURRENT_API_CALLS`

### "Model selection failed"
**Cause**: Invalid model configuration
**Solution**: Check model names and settings in `.env`

## 🔍 Debugging Steps

### 1. Check Configuration
```bash
# Verify .env file exists and has correct settings
cat .env | grep -E "(ENABLE_|AI_CACHE|FORCE_MINI)"

# Check if settings are being loaded
python -c "from config.settings import get_all_settings; print(get_all_settings())"
```

### 2. Monitor Performance
```bash
# Check performance metrics
cat output/metrics/metrics_*.json

# Monitor cache directory
ls -la .ai_cache/

# Check processing logs
tail -f output/logs/process_log_*.txt
```

### 3. Test Individual Components
```bash
# Test single PDF processing
python main.py single_pdf.pdf output/

# Test with minimal configuration
ENABLE_AI_CACHE=false python main.py test_folder/ output/
```

### 4. Verify System Resources
```bash
# Check memory usage
free -h

# Check disk space
df -h

# Check CPU usage
top
```

## 📞 Getting Help

### Before Contacting Support
1. **Check this guide** for your specific issue
2. **Verify configuration** matches recommended settings
3. **Check logs** for error messages
4. **Test with minimal setup** to isolate the problem

### Information to Provide
- **Error messages** from logs
- **Configuration settings** from `.env`
- **Performance metrics** from output
- **System information** (OS, Python version, etc.)
- **Steps to reproduce** the issue

### Support Channels
- **Documentation**: Check this guide and PERFORMANCE.md
- **Issues**: Create detailed issue reports with metrics
- **Team**: Contact development team with complete context

---

**Last Updated**: December 2025  
**Version**: 1.0  
**Maintainer**: Development Team
