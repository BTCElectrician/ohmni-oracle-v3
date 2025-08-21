import unittest
import os
import glob
from openai import AsyncOpenAI
from services.extraction_service import PyMuPdfExtractor
import json
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Define the functions that were previously imported
async def extract_text_and_tables_from_pdf(pdf_path: str) -> str:
    """Extract text and tables from a PDF file."""
    extractor = PyMuPdfExtractor()
    result = await extractor.extract(pdf_path)
    return result.raw_text


async def structure_panel_data(client: AsyncOpenAI, raw_content: str) -> dict:
    """Structure panel data using OpenAI."""
    prompt = f"""
    You are an expert in electrical engineering and panel schedules. 
    Please structure the following content from an electrical panel schedule into a valid JSON format. 
    The content includes both text and tables. Extract key information such as panel name, voltage, amperage, circuits, 
    and any other relevant details.
    Pay special attention to the tabular data, which represents circuit information.
    Ensure your entire response is a valid JSON object.
    Raw content:
    {raw_content}
    """
    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful assistant that structures electrical panel data into JSON.",
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=2000,
        response_format={"type": "json_object"},
    )
    return json.loads(response.choices[0].message.content)


class TestPDFProcessing(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        """Async setup method that will be properly awaited by the test runner."""
        # Initialize OpenAI client with API key from .env
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            logger.warning(
                "No OPENAI_API_KEY found in environment variables. OpenAI tests will be skipped."
            )
            self.skip_openai_tests = True
        else:
            self.skip_openai_tests = False
            logger.info("Found OPENAI_API_KEY in environment variables.")

        self.client = AsyncOpenAI(api_key=api_key or "dummy-key-for-init")

        # Find PDF files for testing
        self.test_pdfs = []
        # Look in various locations where test PDFs might be
        search_paths = [
            "samples/*.pdf",
            "test_data/*.pdf",
            "tests/samples/*.pdf",
            "tests/test_data/*.pdf",
            "*.pdf",
            # Add the ElecShuffleTest directory from the user's desktop
            "/Users/collin/Desktop/ElecShuffleTest/**/*.pdf",
            "/Users/collin/Desktop/ElecShuffleTest/*/*.pdf",
        ]

        for path in search_paths:
            found_files = glob.glob(path, recursive=True)
            if found_files:
                self.test_pdfs.extend(found_files)
                logger.info(f"Found {len(found_files)} PDF files in {path}")

        if not self.test_pdfs:
            logger.warning("No test PDF files found. Tests will be skipped.")
        else:
            logger.info(f"Found {len(self.test_pdfs)} total PDF files for testing")

    async def test_panel_schedule_extraction(self):
        # Skip test if no PDF files found
        if not self.test_pdfs:
            self.skipTest("No PDF files available for testing")

        # Use the first available PDF for testing
        test_file = self.test_pdfs[0]
        logger.info(f"Testing with PDF file: {test_file}")

        try:
            # Extract text content
            content = await extract_text_and_tables_from_pdf(test_file)

            # Verify extraction worked
            self.assertTrue(len(content) > 0, "Extracted content should not be empty")

            # Only test structuring if we have content and API key
            if len(content) > 0 and not getattr(self, "skip_openai_tests", False):
                # Structure data with OpenAI
                structured = await structure_panel_data(
                    self.client, content[:2000]
                )  # Limit to first 2000 chars for testing

                # Verify structuring returns a dict with fields
                self.assertIsInstance(structured, dict)
                self.assertTrue(
                    len(structured) > 0, "Structured data should not be empty"
                )
            elif getattr(self, "skip_openai_tests", False):
                logger.info("Skipping OpenAI structuring test due to missing API key")
        except Exception as e:
            logger.error(f"Error during test: {str(e)}")
            raise
