"""
Smoke test to verify dual API compatibility doesn't break existing functionality.
"""
import os
import json
from services.ai_service import _strip_json_fences, optimize_model_parameters


def test_strip_json_fences():
    """Test the JSON fence stripper works correctly."""
    # Test with fences
    input_with_fences = '```json\n{"test": "data"}\n```'
    assert _strip_json_fences(input_with_fences) == '{"test": "data"}'
    
    # Test without fences
    input_without_fences = '{"test": "data"}'
    assert _strip_json_fences(input_without_fences) == '{"test": "data"}'
    
    # Test empty string
    assert _strip_json_fences('') == ''
    
    # Test None
    assert _strip_json_fences(None) == None


def test_optimize_model_parameters_basic():
    """Test that optimize_model_parameters returns expected structure."""
    # Test with a small document
    params = optimize_model_parameters(
        drawing_type="general",
        raw_content="a" * 1000,  # 1K chars
        pdf_path="test.pdf"
    )
    
    assert isinstance(params, dict)
    assert "model" in params
    assert "temperature" in params
    assert "max_tokens" in params
    
    # Test with a large document
    params_large = optimize_model_parameters(
        drawing_type="general",
        raw_content="a" * 20000,  # 20K chars
        pdf_path="test.pdf"
    )
    
    assert isinstance(params_large, dict)
    assert "model" in params_large
    
    # Test with a schedule (should always use full model)
    params_schedule = optimize_model_parameters(
        drawing_type="panel schedule",
        raw_content="a" * 1000,  # Small content
        pdf_path="test.pdf"
    )
    
    assert isinstance(params_schedule, dict)
    assert params_schedule["temperature"] == 1.0  # gpt-5 requires temperature=1


def test_env_variables():
    """Test that our new environment variables are properly read."""
    # Test default values
    from services.ai_service import RESPONSES_TIMEOUT_SECONDS
    
    assert isinstance(RESPONSES_TIMEOUT_SECONDS, int)
    assert RESPONSES_TIMEOUT_SECONDS > 0


if __name__ == "__main__":
    print("Running smoke tests...")
    
    test_strip_json_fences()
    print("✓ JSON fence stripper works")
    
    test_optimize_model_parameters_basic()
    print("✓ Model parameter optimization works")
    
    test_env_variables()
    print("✓ Environment variables properly configured")
    
    print("\nAll smoke tests passed! ✅")
