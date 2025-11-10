"""
Pipeline orchestrator that wires together all processing steps.

This module coordinates the execution of the pipeline steps with proper
error handling, progress tracking, and timing.
"""
import os
import uuid
from typing import cast
from tqdm.asyncio import tqdm

from utils.performance_utils import time_operation
from utils.storage_utils import derive_drawing_identifiers, slugify_storage_component
from processing.pipeline.types import ProcessingState, ProcessingResult, ProcessingStatus
from processing.pipeline.services import PipelineServices
from processing.pipeline.extraction import step_extract_content
from processing.pipeline.typing_detect import step_determine_ai_processing_type
from processing.pipeline.ai import step_ai_processing_and_parsing, step_validate_drawing_metadata
from processing.pipeline.normalize import step_normalize_data
from processing.pipeline.persist import step_save_output, step_save_metadata, save_pipeline_status
from processing.pipeline.templates import step_generate_room_templates


class PipelineContext:
    """Context object holding all paths and identifiers needed by pipeline steps."""
    
    def __init__(
        self,
        pdf_path: str,
        output_folder: str,
        drawing_type: str,
    ):
        """Initialize pipeline context from inputs."""
        if not os.path.exists(pdf_path):
            raise ValueError(f"PDF file does not exist: {pdf_path}")
        
        self.pdf_path = pdf_path
        self.file_name = os.path.basename(pdf_path)
        self.pipeline_id = str(uuid.uuid4())
        
        # Set up output paths
        self.output_base_folder = output_folder
        self.output_drawing_type_folder = drawing_type if drawing_type else "General"
        self.type_folder = os.path.join(self.output_base_folder, self.output_drawing_type_folder)
        os.makedirs(self.type_folder, exist_ok=True)
        self.storage_discipline = slugify_storage_component(self.output_drawing_type_folder)
        self.drawing_slug, self.version_folder = derive_drawing_identifiers(self.file_name)
        self.drawing_folder = os.path.join(self.type_folder, self.drawing_slug)
        self.structured_folder = os.path.join(self.drawing_folder, "structured")
        self.templates_folder = os.path.join(self.drawing_folder, "templates")
        self.meta_file_path = os.path.join(self.drawing_folder, "meta.json")
        for folder in (self.drawing_folder, self.structured_folder, self.templates_folder):
            os.makedirs(folder, exist_ok=True)

        output_filename_base = os.path.splitext(self.file_name)[0]
        self.structured_output_path = os.path.join(
            self.structured_folder, f"{output_filename_base}_structured.json"
        )
        self.error_output_path = os.path.join(
            self.drawing_folder, f"{output_filename_base}_error.json"
        )
        self.raw_error_output_path = os.path.join(
            self.drawing_folder, f"{output_filename_base}_raw_response_error.txt"
        )


@time_operation("total_processing")
async def process_pipeline(
    pdf_path: str,
    services: PipelineServices,
    output_folder: str,
    drawing_type: str,
    templates_created: dict[str, bool],
) -> ProcessingResult:
    """
    Process the PDF file through the complete pipeline.
    
    This function orchestrates all pipeline steps:
    1. Extract content
    2. Determine AI processing type
    3. AI processing and parsing
    4. Validate drawing metadata (optional)
    5. Normalize data
    6. Save output
    7. Generate room templates (optional)
    8. Persist metadata manifest
    
    Args:
        pdf_path: Path to the PDF file to process
        services: Pipeline services bundle
        output_folder: Base folder for output files
        drawing_type: Type of drawing (e.g., "Architectural", "Electrical")
        templates_created: Dictionary tracking what templates have been created
        
    Returns:
        Dictionary with processing results
    """
    logger = services["logger"]
    context = PipelineContext(pdf_path, output_folder, drawing_type)
    
    # Initialize processing state
    state: ProcessingState = {
        "pdf_path": pdf_path,
        "original_drawing_type": drawing_type,
        "templates_created": dict(templates_created),
        "extraction_result": None,
        "processing_type_for_ai": drawing_type,  # initial value
        "subtype": None,
        "raw_ai_response_str": None,
        "parsed_json_data": None,
        "final_status_dict": None,
        "source_document_info": None,
        "structured_document_info": None,
        "template_files": [],
    }
    
    logger.info(f"PIPELINE_START file={context.file_name} pipeline_id={context.pipeline_id}")
    logger.info(f"🔄 Processing {context.file_name}")
    
    try:
        with tqdm(total=100, desc=f"Processing {context.file_name}", leave=False) as pbar:
            # Step 1: Extract content
            state, success = await step_extract_content(
                state, services, context.file_name,
                context.error_output_path, context.structured_output_path
            )
            if not success:
                pbar.update(100)
                logger.info(f"PIPELINE_END file={context.file_name} pipeline_id={context.pipeline_id}")
                return cast(ProcessingResult, state["final_status_dict"])
            pbar.update(20)

            # Step 2: Determine AI processing type
            state = await step_determine_ai_processing_type(
                state, services, context.pdf_path, context.file_name
            )
            pbar.update(10)

            # Step 3: AI processing and parsing
            state, success = await step_ai_processing_and_parsing(
                state, services, context.pdf_path, context.file_name,
                context.pipeline_id, context.error_output_path
            )
            if not success:
                pbar.update(70)  # remaining progress
                logger.info(f"PIPELINE_END file={context.file_name} pipeline_id={context.pipeline_id}")
                return cast(ProcessingResult, state["final_status_dict"])
            pbar.update(40)  # AI + Parse

            # Step 4: Validate drawing metadata (optional)
            state = await step_validate_drawing_metadata(
                state, services, context.pdf_path
            )
            
            # Step 5: Normalize data
            state = await step_normalize_data(
                state, services, context.pdf_path, context.file_name
            )
            pbar.update(10)  # Normalization

            # Step 6: Save output
            state, success = await step_save_output(
                state, services, context.pdf_path, context.file_name,
                context.pipeline_id, context.structured_output_path,
                context.error_output_path, context.storage_discipline,
                context.drawing_slug
            )
            if not success:
                pbar.update(20)  # remaining progress
                logger.info(f"PIPELINE_END file={context.file_name} pipeline_id={context.pipeline_id}")
                return cast(ProcessingResult, state["final_status_dict"])
            pbar.update(10)  # Save

            # Step 7: Generate room templates (optional)
            state = await step_generate_room_templates(
                state, services, context.pdf_path, context.file_name,
                context.templates_folder, context.pipeline_id,
                context.storage_discipline, context.drawing_slug,
                templates_created
            )
            pbar.update(10)  # Room templates

            # Step 8: Persist metadata manifest for this drawing
            state = await step_save_metadata(
                state, services, context.pdf_path, context.file_name,
                context.pipeline_id, context.structured_output_path,
                context.structured_folder, context.templates_folder,
                context.meta_file_path, context.drawing_slug,
                context.output_drawing_type_folder, context.version_folder,
                context.output_base_folder
            )

            # Return final result
            logger.info(f"PIPELINE_END file={context.file_name} pipeline_id={context.pipeline_id}")
            return cast(ProcessingResult, state["final_status_dict"])
    except Exception as e:
        logger.error(f"Unexpected error in processing pipeline: {str(e)}", exc_info=True)
        logger.info(f"PIPELINE_END file={context.file_name} pipeline_id={context.pipeline_id}")
        return await save_pipeline_status(
            state, services, ProcessingStatus.UNEXPECTED_ERROR,
            f"Unexpected pipeline error: {str(e)}",
            context.error_output_path, True
        )

