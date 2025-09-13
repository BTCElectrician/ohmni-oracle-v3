import unittest
import asyncio
import logging
from services.ai_service import process_drawing
from openai import AsyncOpenAI
from dotenv import load_dotenv
import os
import json


class IntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_dotenv()
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        # Initialize OpenAI client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set")
        cls.client = AsyncOpenAI(api_key=api_key)

    def test_mock_drawing_processing(self):
        """
        Test the drawing processing pipeline with mock content.
        This is a smoke test that doesn't make actual API calls.
        """
        # Create a minimal mock drawing content
        mock_content = """
        Drawing: E101 - PANEL SCHEDULE
        Panel: LP-1
        Voltage: 120/208V
        
        Circuit  Description     Poles  Amps
        1        Receptacles     1      20
        3        Lighting        1      15
        5        HVAC            1      20
        """

        # Set up an async test helper
        async def test_helper():
            # Mock the AI client's response to avoid actual API calls
            class MockClient:
                async def process_with_prompt(self, *args, **kwargs):
                    return json.dumps({"test": "success"})

                async def get_example_output(self, *args, **kwargs):
                    return None

                chat = type(
                    "obj",
                    (object,),
                    {
                        "completions": type(
                            "obj",
                            (object,),
                            {"create": lambda *args, **kwargs: asyncio.sleep(0)},
                        )
                    },
                )

            # Test with the mock client
            try:
                from unittest.mock import patch

                # Patch the Responses API call to avoid network I/O
                with patch(
                    "services.ai_service.make_responses_api_request",
                    return_value=json.dumps({"test": "success"}),
                ):
                    result = await process_drawing(
                        raw_content=mock_content,
                        drawing_type="Electrical",
                        client=self.client,
                        pdf_path="test_panel.pdf",
                    )
                    self.assertIsInstance(result, str)
                    # Just verify it's JSON, we're not testing the actual content here
                    try:
                        json.loads(result)
                        self.assertTrue(
                            True
                        )  # If we get here, it parsed successfully
                    except json.JSONDecodeError:
                        self.fail("Result is not valid JSON")
            except Exception as e:
                self.fail(f"Integration test failed: {str(e)}")

        # Run the async test
        loop = asyncio.get_event_loop()
        loop.run_until_complete(test_helper())


if __name__ == "__main__":
    unittest.main()
