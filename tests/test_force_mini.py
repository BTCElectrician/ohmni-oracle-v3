"""
Simple script to test the force_mini_model implementation.
This shows the model selection with and without the force_mini_model setting.
"""
import os
import logging
from dotenv import load_dotenv
from services.ai_service import optimize_model_parameters

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)


def main():
    """
    Test the force_mini_model implementation.
    """
    # Clear out the existing environment variable if it exists
    if "FORCE_MINI_MODEL" in os.environ:
        del os.environ["FORCE_MINI_MODEL"]

    # Create test inputs that would normally trigger the larger model
    drawing_type = "Specifications"
    file_name = "SPECIFICATION_DOCUMENT.pdf"
    raw_content = "A" * 100000  # 100K characters

    # Test 1: First with FORCE_MINI_MODEL not set (should use larger model)
    logging.info("Test 1: FORCE_MINI_MODEL not set or false")
    # Write to .env file directly
    with open(".env", "r") as f:
        env_content = f.read()

    # Remove or set FORCE_MINI_MODEL=false
    if "FORCE_MINI_MODEL" in env_content:
        env_content = "\n".join(
            [
                line
                for line in env_content.splitlines()
                if not line.startswith("FORCE_MINI_MODEL")
            ]
        )
    env_content += "\nFORCE_MINI_MODEL=false"

    with open(".env", "w") as f:
        f.write(env_content)

    # Reload dotenv
    load_dotenv(override=True)

    # Now test
    params = optimize_model_parameters(drawing_type, raw_content, file_name)
    logging.info(f"Selected model: {params['model_type'].value}")
    logging.info(f"Temperature: {params['temperature']}")
    logging.info(f"Max tokens: {params['max_tokens']}")

    # Test 2: Then with FORCE_MINI_MODEL=true (should force mini model)
    logging.info("\nTest 2: FORCE_MINI_MODEL=true")
    # Write to .env file directly
    with open(".env", "r") as f:
        env_content = f.read()

    # Update FORCE_MINI_MODEL to true
    if "FORCE_MINI_MODEL" in env_content:
        env_content = "\n".join(
            [
                line
                for line in env_content.splitlines()
                if not line.startswith("FORCE_MINI_MODEL")
            ]
        )
    env_content += "\nFORCE_MINI_MODEL=true"

    with open(".env", "w") as f:
        f.write(env_content)

    # Reload dotenv
    load_dotenv(override=True)

    # Now test
    params = optimize_model_parameters(drawing_type, raw_content, file_name)
    logging.info(f"Selected model: {params['model_type'].value}")
    logging.info(f"Temperature: {params['temperature']}")
    logging.info(f"Max tokens: {params['max_tokens']}")


if __name__ == "__main__":
    main()
