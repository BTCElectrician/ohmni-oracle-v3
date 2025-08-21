import os
import sys
import json
import logging
import asyncio

from dotenv import load_dotenv
from processing.file_processor import is_panel_schedule
from services.extraction_service import PyMuPdfExtractor


def setup_logging():
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_azure_panel.py <pdf_file_or_folder>")
        sys.exit(1)

    path_arg = sys.argv[1]
    if not os.path.exists(path_arg):
        print(f"Error: Path '{path_arg}' does not exist.")
        sys.exit(1)

    load_dotenv()

    pdf_files = []
    if os.path.isfile(path_arg) and path_arg.lower().endswith(".pdf"):
        pdf_files.append(path_arg)
    elif os.path.isdir(path_arg):
        for root, _, files in os.walk(path_arg):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))

    output_folder = os.path.join(os.getcwd(), "test_output")
    os.makedirs(output_folder, exist_ok=True)

    extractor = PyMuPdfExtractor(logger=logging.getLogger())

    for pdf_path in pdf_files:
        file_name = os.path.basename(pdf_path)

        if is_panel_schedule(file_name, ""):
            logging.info(f"Detected panel schedule in '{file_name}'.")
            try:
                # Extract with PyMuPDF (async call)
                extraction_result = await extractor.extract(pdf_path)

                if extraction_result.success:
                    # Format the content like the old function did
                    all_content = "TEXT:\n" + extraction_result.raw_text + "\n"
                    for table in extraction_result.tables:
                        all_content += "TABLE:\n"
                        all_content += table["content"] + "\n"

                    result_data = {"extracted_content": all_content, "error": None}
                    logging.info(f"Successfully processed '{file_name}'.")
                else:
                    result_data = {
                        "extracted_content": "",
                        "error": extraction_result.error,
                    }
                    logging.error(f"Extraction failed: {extraction_result.error}")
            except Exception as e:
                logging.exception(f"Error: {e}")
                result_data = {"extracted_content": "", "error": str(e)}

            out_file = os.path.join(
                output_folder, f"{os.path.splitext(file_name)[0]}_test_panel.json"
            )
            with open(out_file, "w") as f:
                json.dump(result_data, f, indent=2)
            logging.info(f"Wrote output to '{out_file}'")

        else:
            logging.info(f"'{file_name}' is NOT flagged as a panel schedule.")


if __name__ == "__main__":
    setup_logging()
    asyncio.run(main())
