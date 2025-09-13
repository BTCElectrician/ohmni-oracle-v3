"""
Test to ensure API metrics are not double-counted.
"""
import asyncio
import types
from unittest.mock import Mock, AsyncMock, patch
import pytest

from utils.performance_utils import get_tracker, PerformanceTracker
from services.ai_service import make_responses_api_request


class FakeUsage:
    def __init__(self):
        self.prompt_tokens = 10
        self.completion_tokens = 20
        self.total_tokens = 30


class FakeResponse:
    def __init__(self):
        self.output_text = '{"test": "response"}'
        self.output = None
        self.usage = FakeUsage()
        self.id = "test-response-id"
        self.model = "gpt-5-mini"


@pytest.mark.asyncio
async def test_single_api_metric_count():
    """Test that a single API call results in exactly one count in metrics."""
    # Create a fresh tracker for this test
    test_tracker = PerformanceTracker()
    
    # Mock the get_tracker function to return our test tracker
    with patch('services.ai_service.get_tracker', return_value=test_tracker):
        # Create a mock OpenAI client
        mock_client = AsyncMock()
        mock_client.responses.create = AsyncMock(return_value=FakeResponse())
        
        # Make a single API request
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Return JSON."},
            {"role": "user", "content": "Extract data from this drawing."}
        ]
        
        response = await make_responses_api_request(
            client=mock_client,
            input_text=messages[-1]["content"],
            model="gpt-5-mini",
            temperature=1.0,
            max_tokens=100,
            file_path="/test/drawing.pdf",
            drawing_type="Electrical",
            instructions="Return JSON only."
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
        mock_client.responses.create = AsyncMock(return_value=FakeResponse())
        
        messages = [
            {"role": "system", "content": "You are a helpful assistant. Return JSON."},
            {"role": "user", "content": "Extract data from this drawing."}
        ]
        
        # Make 3 API requests
        for i in range(3):
            await make_responses_api_request(
                client=mock_client,
                input_text=messages[-1]["content"],
                model="gpt-5-mini",
                temperature=1.0,
                max_tokens=100,
                file_path=f"/test/drawing_{i}.pdf",
                drawing_type="Electrical",
                instructions="Return JSON only."
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
