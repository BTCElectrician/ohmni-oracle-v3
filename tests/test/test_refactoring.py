"""
Simple test script to validate refactoring changes.
"""
import os
import sys
import logging
import asyncio
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from openai import AsyncOpenAI
from config.settings import OPENAI_API_KEY
from utils.logging_utils import setup_logging
from processing.file_processor import process_pdf_async
from services.extraction_service import create_extractor


async def test_extraction():
    """Test PDF extraction."""
    logging.info("Testing extraction...")

    # Check if a test PDF exists
    sample_pdfs = []
    for root, _, files in os.walk("test_data"):
        for file in files:
            if file.lower().endswith(".pdf"):
                sample_pdfs.append(os.path.join(root, file))

    if not sample_pdfs:
        logging.error("No sample PDFs found in test_data directory.")
        return False

    sample_pdf = sample_pdfs[0]

    # Create extractor
    extractor = create_extractor("General")

    # Extract content
    result = await extractor.extract(sample_pdf)

    # Log result
    logging.info(f"Extraction success: {result.success}")
    logging.info(f"Has content: {result.has_content}")

    return result.success


async def test_process_pdf():
    """Test PDF processing."""
    logging.info("Testing PDF processing...")

    # Check if a test PDF exists
    sample_pdfs = []
    for root, _, files in os.walk("test_data"):
        for file in files:
            if file.lower().endswith(".pdf"):
                sample_pdfs.append(os.path.join(root, file))

    if not sample_pdfs:
        logging.error("No sample PDFs found in test_data directory.")
        return False

    sample_pdf = sample_pdfs[0]

    # Create output folder
    output_folder = "test_output"
    os.makedirs(output_folder, exist_ok=True)

    # Create OpenAI client
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)

    # Process PDF
    result = await process_pdf_async(
        pdf_path=sample_pdf,
        client=client,
        output_folder=output_folder,
        drawing_type="General",
        templates_created={"floor_plan": False},
    )

    # Log result
    logging.info(f"Processing success: {result['success']}")

    return result["success"]


async def test_ai_cache():
    """Test AI caching functionality."""
    logging.info("Testing AI cache...")

    # Set environment variables for testing
    os.environ["ENABLE_AI_CACHE"] = "true"
    os.environ["AI_CACHE_DIR"] = ".test_ai_cache"
    os.makedirs(os.environ["AI_CACHE_DIR"], exist_ok=True)

    from utils.ai_cache import load_cache, save_cache

    # Test caching
    test_prompt = "This is a test prompt"
    test_params = {"model": "gpt-4o-mini", "temperature": 0.2, "max_tokens": 1000}
    test_response = "This is a test response"

    # Save to cache
    save_cache(test_prompt, test_params, test_response)

    # Load from cache
    cached_response = load_cache(test_prompt, test_params)

    # Check if cache worked
    cache_success = cached_response == test_response
    logging.info(f"Cache test success: {cache_success}")

    # Reset environment variables
    os.environ["ENABLE_AI_CACHE"] = "false"

    return cache_success


async def main():
    """Main test function."""
    # Set up logging
    os.makedirs("test_output", exist_ok=True)
    setup_logging("test_output")

    # Run tests
    test_results = {}

    # Test extraction
    try:
        test_results["extraction"] = await test_extraction()
    except Exception as e:
        logging.error(f"Extraction test error: {str(e)}")
        test_results["extraction"] = False

    # Test AI cache
    try:
        test_results["ai_cache"] = await test_ai_cache()
    except Exception as e:
        logging.error(f"AI cache test error: {str(e)}")
        test_results["ai_cache"] = False

    # Print summary
    print("\nTest Results:")
    for test_name, result in test_results.items():
        status = "PASSED" if result else "FAILED"
        print(f"  {test_name}: {status}")

    # Overall success
    success = all(test_results.values())
    print(f"\nOverall: {'PASSED' if success else 'FAILED'}")

    return success


if __name__ == "__main__":
    asyncio.run(main())
