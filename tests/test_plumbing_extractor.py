"""
Test suite for the PlumbingExtractor.
"""
import os
import sys
import pytest
import logging

# Add project root to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from services.extraction_service import PlumbingExtractor, create_extractor

# Set up logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test")

# Skip if test files don't exist
TEST_FILE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "test_data", "plumbing_fixture_schedule.pdf"
)
REQUIRES_TEST_FILE = pytest.mark.skipif(
    not os.path.exists(TEST_FILE_PATH), reason="Test file not available"
)


@pytest.mark.asyncio
async def test_plumbing_extractor_created_by_factory():
    """Test that the factory function creates the correct extractor."""
    # Test with lowercase
    extractor = create_extractor("plumbing", logger)
    assert isinstance(extractor, PlumbingExtractor)

    # Test with mixed case
    extractor = create_extractor("Plumbing", logger)
    assert isinstance(extractor, PlumbingExtractor)

    # Test with longer string containing "plumbing"
    extractor = create_extractor("Test Plumbing Drawing", logger)
    assert isinstance(extractor, PlumbingExtractor)


@pytest.mark.asyncio
async def test_plumbing_extractor_basic_functionality():
    """Test that the PlumbingExtractor works with minimal inputs."""
    extractor = PlumbingExtractor(logger)

    # Create a small test by mocking the parent extract method
    original_extract = extractor.__class__.__bases__[0].extract

    async def mock_extract(*args, **kwargs):
        # Return a basic successful result
        from services.extraction_service import ExtractionResult

        return ExtractionResult(
            raw_text="This is a test with pipe and fixture information.",
            tables=[
                {
                    "page": 1,
                    "table_index": 0,
                    "content": "Fixtures | Type | Size\nWC-1 | Water Closet | 1.6 GPF",
                }
            ],
            success=True,
            has_content=True,
        )

    try:
        # Replace the parent extract method temporarily
        extractor.__class__.__bases__[0].extract = mock_extract

        # Test the extractor
        result = await extractor.extract("test_file.pdf")

        # Check that the text was enhanced
        assert "PLUMBING CONTENT:" in result.raw_text
        assert "FIXTURE INFORMATION DETECTED:" in result.raw_text
        assert "PIPING INFORMATION DETECTED:" in result.raw_text

        # Check that tables were correctly processed
        assert len(result.tables) == 1
        assert "fixture" in result.tables[0]["content"].lower()

    finally:
        # Restore the original method
        extractor.__class__.__bases__[0].extract = original_extract


@pytest.mark.asyncio
@REQUIRES_TEST_FILE
async def test_plumbing_extractor_with_test_file():
    """Test the PlumbingExtractor with an actual test file if available."""
    # Initialize logger
    logger = logging.getLogger("test")

    # Create extractor
    extractor = PlumbingExtractor(logger)

    # Extract content from test file
    result = await extractor.extract(TEST_FILE_PATH)

    # Validate result
    assert result.success
    assert result.has_content

    # If we have fixed test data, we can check for specific keywords
    # Otherwise, just verify that our enhancement is applied
    assert "PLUMBING CONTENT:" in result.raw_text

    # Check for fixture detection if content contains fixture terms
    if (
        "fixture" in result.raw_text.lower()
        or "water closet" in result.raw_text.lower()
    ):
        assert "FIXTURE INFORMATION DETECTED:" in result.raw_text

    # Validate table prioritization if tables exist
    if result.tables and any(
        "fixture" in table.get("content", "").lower() for table in result.tables
    ):
        # The fixture table should be near the top (among the first tables)
        assert any(
            "fixture" in table.get("content", "").lower() for table in result.tables[:3]
        )


@pytest.mark.asyncio
async def test_plumbing_extractor_error_handling():
    """Test that the PlumbingExtractor handles errors gracefully."""
    extractor = PlumbingExtractor(logger)

    # Test with non-existent file
    result = await extractor.extract("non_existent_file.pdf")
    assert not result.success
    assert not result.has_content
    assert result.error is not None

    # Test with successful extraction but enhancement error
    original_enhance = extractor._enhance_plumbing_information

    def mock_enhance_error(text):
        raise ValueError("Test error in enhancement")

    try:
        # Mock the parent extract method
        original_extract = extractor.__class__.__bases__[0].extract

        async def mock_extract(*args, **kwargs):
            # Return a basic successful result
            from services.extraction_service import ExtractionResult

            return ExtractionResult(
                raw_text="Test content", tables=[], success=True, has_content=True
            )

        extractor.__class__.__bases__[0].extract = mock_extract

        # Mock the enhancement to throw an error
        extractor._enhance_plumbing_information = mock_enhance_error

        # Test error handling during enhancement
        result = await extractor.extract("test_file.pdf")

        # Check that it falls back to the base extraction
        assert result.success  # Still successful because base extraction works
        assert result.has_content
        assert "Test content" in result.raw_text

    finally:
        # Restore the original methods
        extractor._enhance_plumbing_information = original_enhance
        extractor.__class__.__bases__[0].extract = original_extract


@pytest.mark.asyncio
async def test_prioritize_plumbing_tables():
    """Test the table prioritization logic."""
    extractor = PlumbingExtractor(logger)

    # Create test tables
    tables = [
        {"page": 1, "table_index": 0, "content": "Generic Table"},
        {"page": 1, "table_index": 1, "content": "Fixture Schedule | Model | Size"},
        {"page": 2, "table_index": 0, "content": "Water Heater Schedule | Model | GPM"},
        {"page": 2, "table_index": 1, "content": "Pipe Schedule | Size | Material"},
        {"page": 3, "table_index": 0, "content": "Another Generic Table"},
    ]

    prioritized = extractor._prioritize_plumbing_tables(tables)

    # Check order - fixture tables should be first
    assert "fixture" in prioritized[0]["content"].lower()
    # Water heaters should be second
    assert "water heater" in prioritized[1]["content"].lower()
    # Pipes should be third
    assert "pipe" in prioritized[2]["content"].lower()
    # Generic tables should be last
    assert "generic" in prioritized[3]["content"].lower()
    assert "generic" in prioritized[4]["content"].lower()


def test_enhance_plumbing_information():
    """Test the text enhancement logic."""
    extractor = PlumbingExtractor(logger)

    # Test with fixture info
    text = "This document contains fixture schedules for water closets and lavatories."
    enhanced = extractor._enhance_plumbing_information(text)
    assert "FIXTURE INFORMATION DETECTED:" in enhanced
    assert "PLUMBING CONTENT:" in enhanced

    # Test with water heater info
    text = "Water heater specifications and domestic water system details."
    enhanced = extractor._enhance_plumbing_information(text)
    assert "WATER HEATER INFORMATION DETECTED:" in enhanced
    assert "PLUMBING CONTENT:" in enhanced

    # Test with piping info
    text = "Piping diagrams and valve schedules are included."
    enhanced = extractor._enhance_plumbing_information(text)
    assert "PIPING INFORMATION DETECTED:" in enhanced
    assert "PLUMBING CONTENT:" in enhanced

    # Test with mixed content
    text = "This drawing includes fixtures, water heaters, and piping specifications."
    enhanced = extractor._enhance_plumbing_information(text)
    assert "FIXTURE INFORMATION DETECTED:" in enhanced
    assert "WATER HEATER INFORMATION DETECTED:" in enhanced
    assert "PIPING INFORMATION DETECTED:" in enhanced
    assert "PLUMBING CONTENT:" in enhanced


if __name__ == "__main__":
    pytest.main()
