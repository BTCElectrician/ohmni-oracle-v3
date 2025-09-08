<artifacts>
<artifact identifier="complete-api-metrics-fix" type="text/markdown" title="Complete Fix for Double-Counting API Metrics">
# Complete Changes to Fix Double-Counting API Metrics

## 1. Fix `services/ai_service.py`

### Find and Replace the `make_openai_request` function (around line 140-195):

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((Exception)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def make_openai_request(
    client: AsyncOpenAI,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    response_format: Dict[str, str] = {"type": "json_object"},
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
) -> Any:
    """
    Make a request to the OpenAI API with timing and retry logic.

    Args:
        client: OpenAI client
        messages: List of message dictionaries
        model: Model name
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        response_format: Response format specification
        file_path: Original PDF file path
        drawing_type: Type of drawing (detected or specified)

    Returns:
        OpenAI API response

    Raises:
        AIProcessingError: If the request fails after retries
    """
    start_time = time.time()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format=response_format,
        )
        request_time = time.time() - start_time

        # Get the global tracker and add metrics
        tracker = get_tracker()
        # Note: add_metric_with_context('api_request') also updates API stats internally.
        # Do not call add_api_metric() here to avoid double-counting.
        tracker.add_metric_with_context(
            category="api_request",
            duration=request_time,
            file_path=file_path,
            drawing_type=drawing_type,
            model=model  # Extra context
        )

        logger.info(
            "OpenAI API request completed",
            extra={
                "duration": f"{request_time:.2f}s",
                "model": model,
                "tokens": max_tokens,
                "file": os.path.basename(file_path) if file_path else "unknown",
                "type": drawing_type or "unknown",
            },
        )
        return response
    except Exception as e:
        request_time = time.time() - start_time
        logger.error(
            "OpenAI API request failed",
            extra={"duration": f"{request_time:.2f}s", "error": str(e), "model": model},
        )
        raise AIProcessingError(f"OpenAI API request failed: {str(e)}")
```

### If you have a `make_responses_api_request` function, replace it with:

```python
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=10),
    retry=retry_if_exception_type((Exception)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)
async def make_responses_api_request(
    client: AsyncOpenAI,
    messages: List[Dict[str, str]],
    model: str,
    temperature: float,
    max_tokens: int,
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
) -> Any:
    """
    Make a request to the OpenAI Responses API with timing and retry logic.

    Args:
        client: OpenAI client
        messages: List of message dictionaries
        model: Model name
        temperature: Temperature parameter
        max_tokens: Maximum tokens
        file_path: Original PDF file path
        drawing_type: Type of drawing (detected or specified)

    Returns:
        OpenAI API response

    Raises:
        AIProcessingError: If the request fails after retries
    """
    start_time = time.time()
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        request_time = time.time() - start_time

        # Get the global tracker and add metrics
        tracker = get_tracker()
        # Note: add_metric_with_context('api_request') also updates API stats internally.
        # Do not call add_api_metric() here to avoid double-counting.
        tracker.add_metric_with_context(
            category="api_request",
            duration=request_time,
            file_path=file_path,
            drawing_type=drawing_type,
            model=model,
            api_type="responses"
        )

        logger.info(
            "OpenAI Responses API request completed",
            extra={
                "duration": f"{request_time:.2f}s",
                "model": model,
                "tokens": max_tokens,
                "file": os.path.basename(file_path) if file_path else "unknown",
                "type": drawing_type or "unknown",
            },
        )
        return response
    except Exception as e:
        request_time = time.time() - start_time
        logger.error(
            "OpenAI Responses API request failed",
            extra={"duration": f"{request_time:.2f}s", "error": str(e), "model": model},
        )
        raise AIProcessingError(f"OpenAI Responses API request failed: {str(e)}")
```

## 2. Update `utils/performance_utils.py`

### Find the `add_metric_with_context` method (around line 80-110) and update its docstring:

```python
def add_metric_with_context(
    self, 
    category: str, 
    duration: float,
    file_path: Optional[str] = None,
    drawing_type: Optional[str] = None,
    **kwargs
):
    """
    Add a metric with explicit context.
    
    Notes:
    - When category == "api_request", this method also updates aggregate API stats
      (min/max/avg/count/total_time) internally by calling add_api_metric().
      Do NOT call add_api_metric() separately for the same event, or API metrics
      will be double-counted.
      
    Args:
        category: Category name for the metric (e.g., 'extraction', 'api_request')
        duration: Duration of the operation in seconds
        file_path: Optional path to the file being processed
        drawing_type: Optional type of drawing being processed
        **kwargs: Additional context fields to store with the metric
    """
    file_name = os.path.basename(file_path) if file_path else "unknown"
    drawing_type = drawing_type or "unknown"
    
    if category not in self.metrics:
        self.metrics[category] = []
        
    self.metrics[category].append({
        "file_name": file_name,
        "drawing_type": drawing_type,
        "duration": duration,
        **kwargs
    })
    
    # Special handling for API metrics
    if category == "api_request":
        self.add_api_metric(duration)
```

## 3. Add Test File: `tests/test_api_metrics_single_count.py`

Create this new test file to verify the fix:

```python
"""
Test to ensure API metrics are not double-counted.
"""
import asyncio
import types
from unittest.mock import Mock, AsyncMock, patch
import pytest

from utils.performance_utils import get_tracker, PerformanceTracker
from services.ai_service import make_openai_request


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)


class FakeUsage:
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 20
        self.total_tokens = 30


class FakeResponse:
    def __init__(self):
        self.choices = [FakeChoice('{"test": "response"}')]
        self.usage = FakeUsage()
        self.id = "test-response-id"
        self.model = "gpt-4o-mini"
        self.system_fingerprint = "test-fingerprint"


@pytest.mark.asyncio
async def test_single_api_metric_count():
    """Test that a single API call results in exactly one count in metrics."""
    # Create a fresh tracker for this test
    test_tracker = PerformanceTracker()
    
    # Mock the get_tracker function to return our test tracker
    with patch('services.ai_service.get_tracker', return_value=test_tracker):
        # Create a mock OpenAI client
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=FakeResponse())
        
        # Make a single API request
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Return JSON."},
            {"role": "user", "content": "Extract data from this drawing."}
        ]
        
        response = await make_openai_request(
            client=mock_client,
            messages=messages,
            model="gpt-4o-mini",
            temperature=0.1,
            max_tokens=100,
            file_path="/test/drawing.pdf",
            drawing_type="Electrical"
        )
        
        # Get the report
        report = test_tracker.report()
        
        # Verify API statistics show exactly 1 call
        assert "api_statistics" in report
        assert report["api_statistics"]["count"] == 1, \
            f"Expected 1 API call, but got {report['api_statistics']['count']}"
        
        # Verify api_request category also shows 1 operation
        assert "api_request" in report
        assert report["api_request"]["total_operations"] == 1, \
            f"Expected 1 api_request operation, but got {report['api_request']['total_operations']}"
        
        # Verify the times match between api_statistics and api_request
        api_stats_total = report["api_statistics"]["total_time"]
        api_request_avg = report["api_request"]["overall_average"]
        
        # Since we have 1 call, average should equal total
        assert abs(api_stats_total - api_request_avg) < 0.01, \
            f"Time mismatch: api_stats total={api_stats_total}, api_request avg={api_request_avg}"


@pytest.mark.asyncio
async def test_multiple_api_calls_correct_count():
    """Test that multiple API calls result in correct count in metrics."""
    # Create a fresh tracker for this test
    test_tracker = PerformanceTracker()
    
    # Mock the get_tracker function to return our test tracker
    with patch('services.ai_service.get_tracker', return_value=test_tracker):
        # Create a mock OpenAI client
        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=FakeResponse())
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Return JSON."},
            {"role": "user", "content": "Extract data from this drawing."}
        ]
        
        # Make 3 API requests
        for i in range(3):
            await make_openai_request(
                client=mock_client,
                messages=messages,
                model="gpt-4o-mini",
                temperature=0.1,
                max_tokens=100,
                file_path=f"/test/drawing_{i}.pdf",
                drawing_type="Electrical"
            )
        
        # Get the report
        report = test_tracker.report()
        
        # Verify API statistics show exactly 3 calls
        assert report["api_statistics"]["count"] == 3, \
            f"Expected 3 API calls, but got {report['api_statistics']['count']}"
        
        # Verify api_request category also shows 3 operations
        assert report["api_request"]["total_operations"] == 3, \
            f"Expected 3 api_request operations, but got {report['api_request']['total_operations']}"


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_single_api_metric_count())
    asyncio.run(test_multiple_api_calls_correct_count())
    print("✅ All API metrics tests passed!")
```

## 4. Quick Verification Commands

After making these changes, run these commands to verify:

```bash
# Run the new test
python -m pytest tests/test_api_metrics_single_count.py -v

# Process a small batch and check metrics
python main.py test_input/ test_output/

# Check the metrics file for correct count
grep -A 5 '"api_statistics"' test_output/metrics/metrics_*.json

# Count actual API calls in logs (should match api_statistics count)
grep -c "OpenAI API request completed" test_output/logs/process_log_*.txt
```

## Summary of Changes

1. **Removed duplicate `tracker.add_api_metric()` calls** in both API request functions
2. **Added clarifying comments** to prevent future double-counting
3. **Updated docstring** in `add_metric_with_context` to document the behavior
4. **Added comprehensive test** to verify single-count behavior

These changes will ensure your API metrics accurately reflect the actual number of API calls being made.
</artifact>
</artifacts>