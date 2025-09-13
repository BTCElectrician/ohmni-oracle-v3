import asyncio
import logging
import json
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv
from templates.prompts.electrical import lighting_fixture_prompt
from services.ai_service import process_drawing
from config.settings import DEFAULT_MODEL

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


async def test_lighting_prompt():
    """
    Test the lighting fixture prompt to verify metadata extraction is working
    """
    # Load environment variables
    load_dotenv()

    # Get API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    # Create OpenAI client
    client = AsyncOpenAI(api_key=api_key)

    # Create mock lighting drawing content with title block metadata
    mock_content = """
    DRAWING TITLE BLOCK:
    
    Drawing Number: E1.00
    Title: LIGHTING - FLOOR LEVEL
    Revision: 3
    Date: 08/15/2024
    Job Number: 30J7925
    Project Name: ELECTRIC SHUFFLE
    
    LIGHTING FIXTURE SCHEDULE:
    
    Type Mark: CL-US-18
    Count: 13
    Manufacturer: Mullan
    Product Number: MLP323
    Description: Essense Vintage Prismatic Glass Pendant Light
    Finish: Antique Brass
    Lamp Type: E27, 40W, 120V, 2200K
    Mounting: Ceiling
    Dimensions: 15.75" DIA x 13.78" HEIGHT
    Location: Restroom Corridor and Raised Playspace
    Wattage: 40W
    Ballast Type: LED Driver
    Dimmable: Yes
    Remarks: Refer to architectural
    Catalog Series: RA1-24-A-35-F2-M-C
    
    LIGHTING ZONE SCHEDULE:
    
    Zone: Z1
    Area: Dining 103
    Circuit: L1-13
    Fixture Type: LED
    Dimming Control: ELV
    Notes: Shuffleboard Tables 3,4
    Quantities or Linear Footage: 16
    """

    # Get the lighting fixture prompt
    prompt = lighting_fixture_prompt()
    logging.info("Using the lighting fixture prompt template")

    # Process the mock content directly via Responses API service
    logging.info("Processing mock lighting drawing content...")
    try:
        result = await process_drawing(
            raw_content=mock_content,
            drawing_type="Electrical",
            client=client,
            pdf_path="lighting_mock.pdf",
            titleblock_text=None,
        )

        # Print the result
        logging.info("Processing complete!")

        # Parse the result as JSON
        try:
            parsed_result = json.loads(result)
            logging.info("Result successfully parsed as JSON")

            # Check if metadata is present
            if (
                "ELECTRICAL" in parsed_result
                and "metadata" in parsed_result["ELECTRICAL"]
            ):
                metadata = parsed_result["ELECTRICAL"]["metadata"]
                logging.info("Metadata found in the result:")
                logging.info(
                    f"Drawing Number: {metadata.get('drawing_number', 'Not found')}"
                )
                logging.info(f"Title: {metadata.get('title', 'Not found')}")
                logging.info(f"Revision: {metadata.get('revision', 'Not found')}")
                logging.info(f"Date: {metadata.get('date', 'Not found')}")
                logging.info(f"Job Number: {metadata.get('job_number', 'Not found')}")
                logging.info(
                    f"Project Name: {metadata.get('project_name', 'Not found')}"
                )

                # Check if all expected metadata fields are present
                expected_fields = [
                    "drawing_number",
                    "title",
                    "revision",
                    "date",
                    "job_number",
                    "project_name",
                ]

                all_fields_present = all(field in metadata for field in expected_fields)
                if all_fields_present:
                    logging.info("SUCCESS: All metadata fields are present!")
                else:
                    missing_fields = [
                        field for field in expected_fields if field not in metadata
                    ]
                    logging.error(
                        f"Missing metadata fields: {', '.join(missing_fields)}"
                    )
            else:
                logging.error("No metadata found in the result!")
                logging.error(
                    f"Result structure: {json.dumps(parsed_result, indent=2)}"
                )

            # Save the result to a file
            os.makedirs("test_output", exist_ok=True)
            with open("test_output/lighting_test_result.json", "w") as f:
                json.dump(parsed_result, f, indent=2)
            logging.info("Result saved to test_output/lighting_test_result.json")

        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse result as JSON: {e}")
            logging.error(f"Raw result: {result}")

    except Exception as e:
        logging.error(f"Error processing lighting drawing: {e}")


if __name__ == "__main__":
    asyncio.run(test_lighting_prompt())
