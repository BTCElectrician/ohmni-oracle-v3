"""
Test dual compatibility of Responses API for GPT-4.x and GPT-5 models.
"""
import pytest
import os
from unittest.mock import Mock, AsyncMock, patch
from services.ai_service import make_responses_api_request


@pytest.mark.asyncio
async def test_gpt4_includes_response_format():
    """Test that GPT-4.x models include response_format parameter."""
    client = Mock()
    client.responses = Mock()
    client.responses.create = AsyncMock()
    
    # Mock response
    mock_response = Mock()
    mock_response.output_text = '{"test": "data"}'
    client.responses.create.return_value = mock_response
    
    # Test with GPT-4.1-mini
    await make_responses_api_request(
        client=client,
        input_text="test input",
        model="gpt-4.1-mini",
        temperature=0.5,
        max_tokens=100
    )
    
    # Verify response_format was included
    call_args = client.responses.create.call_args[1]
    assert "response_format" in call_args
    assert call_args["response_format"] == {"type": "json_object"}


@pytest.mark.asyncio
async def test_gpt5_excludes_response_format():
    """Test that GPT-5 models exclude response_format parameter."""
    client = Mock()
    client.responses = Mock()
    client.responses.create = AsyncMock()
    
    # Mock response
    mock_response = Mock()
    mock_response.output_text = '{"test": "data"}'
    client.responses.create.return_value = mock_response
    
    # Test with GPT-5-mini
    await make_responses_api_request(
        client=client,
        input_text="test input",
        model="gpt-5-mini",
        temperature=0.5,
        max_tokens=100
    )
    
    # Verify response_format was NOT included
    call_args = client.responses.create.call_args[1]
    assert "response_format" not in call_args


@pytest.mark.asyncio
async def test_gpt5_includes_text_verbosity():
    """Test that GPT-5 models include text.verbosity when env var is set."""
    with patch.dict(os.environ, {"GPT5_TEXT_VERBOSITY": "low"}):
        client = Mock()
        client.responses = Mock()
        client.responses.create = AsyncMock()
        
        # Mock response
        mock_response = Mock()
        mock_response.output_text = '{"test": "data"}'
        client.responses.create.return_value = mock_response
        
        # Test with GPT-5-mini
        await make_responses_api_request(
            client=client,
            input_text="test input",
            model="gpt-5-mini",
            temperature=0.5,
            max_tokens=100
        )
        
        # Verify text.verbosity was included
        call_args = client.responses.create.call_args[1]
        assert "text" in call_args
        assert call_args["text"]["verbosity"] == "low"


@pytest.mark.asyncio
async def test_gpt5_full_includes_reasoning_effort():
    """Test that only full GPT-5 model includes reasoning.effort."""
    with patch.dict(os.environ, {"GPT5_REASONING_EFFORT": "minimal"}):
        client = Mock()
        client.responses = Mock()
        client.responses.create = AsyncMock()
        
        # Mock response
        mock_response = Mock()
        mock_response.output_text = '{"test": "data"}'
        client.responses.create.return_value = mock_response
        
        # Test with full GPT-5
        await make_responses_api_request(
            client=client,
            input_text="test input",
            model="gpt-5",
            temperature=0.5,
            max_tokens=100
        )
        
        # Verify reasoning.effort was included
        call_args = client.responses.create.call_args[1]
        assert "reasoning" in call_args
        assert call_args["reasoning"]["effort"] == "minimal"


@pytest.mark.asyncio
async def test_gpt5_mini_excludes_reasoning_effort():
    """Test that GPT-5-mini excludes reasoning.effort."""
    with patch.dict(os.environ, {"GPT5_REASONING_EFFORT": "minimal"}):
        client = Mock()
        client.responses = Mock()
        client.responses.create = AsyncMock()
        
        # Mock response
        mock_response = Mock()
        mock_response.output_text = '{"test": "data"}'
        client.responses.create.return_value = mock_response
        
        # Test with GPT-5-mini
        await make_responses_api_request(
            client=client,
            input_text="test input",
            model="gpt-5-mini",
            temperature=0.5,
            max_tokens=100
        )
        
        # Verify reasoning.effort was NOT included
        call_args = client.responses.create.call_args[1]
        assert "reasoning" not in call_args


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
