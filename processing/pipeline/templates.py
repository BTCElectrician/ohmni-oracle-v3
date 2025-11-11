"""
Template generation step for the processing pipeline.

Handles generation of room templates for architectural drawings.
"""
from processing.pipeline.types import ProcessingState
from processing.pipeline.services import PipelineServices
from processing.pipeline.archive import archive_additional_artifacts


async def step_generate_room_templates(
    state: ProcessingState,
    services: PipelineServices,
    pdf_path: str,
    file_name: str,
    templates_folder: str,
    pipeline_id: str,
    storage_discipline: str,
    drawing_slug: str,
    templates_created: dict[str, bool],
) -> ProcessingState:
    """
    Generate room templates for architectural drawings.
    
    This step:
    1. Checks if the drawing is an architectural floor plan
    2. Generates room templates if applicable
    3. Updates templates_created tracking dictionary
    
    This is an optional post-processing step.
    
    Note: Mutates state and templates_created in place.
    
    Args:
        state: Processing state (mutated in place)
        services: Pipeline services bundle
        pdf_path: Path to the PDF file
        file_name: Name of the PDF file
        templates_folder: Path to templates folder
        pipeline_id: Unique pipeline identifier
        storage_discipline: Storage discipline slug
        drawing_slug: Drawing slug identifier
        templates_created: Dictionary tracking templates (mutated in place)
        
    Returns:
        Updated state
    """
    logger = services["logger"]
    
    # Enhanced floor plan detection: check filename and metadata title
    meta = (state.get("parsed_json_data") or {}).get("DRAWING_METADATA", {})
    meta_title = str(meta.get("title", "")).upper()
    looks_like_floor = (
        "floor" in file_name.lower() or 
        "FLOOR" in meta_title or 
        "LEVEL" in meta_title
    )
    
    if state["processing_type_for_ai"] == "Architectural" and looks_like_floor:
        try:
            # Create room-data folder only when we're actually generating templates
            import os
            os.makedirs(templates_folder, exist_ok=True)
            
            from templates.room_templates import process_architectural_drawing
            
            result = process_architectural_drawing(
                state["parsed_json_data"], 
                pdf_path, 
                templates_folder
            )
            
            state["templates_created"]["floor_plan"] = True
            templates_created["floor_plan"] = True
            state.setdefault("template_files", [])
            state["template_files"] = result.get("generated_files", [])
            logger.info(f"Created room templates: {result}")

            artifact_paths = [
                result.get("e_rooms_file"),
                result.get("a_rooms_file"),
            ]
            await archive_additional_artifacts(
                services,
                artifact_paths,
                file_name,
                pipeline_id,
                storage_discipline="room-data",
                drawing_slug=drawing_slug,
                artifact_type="",
                content_type="application/json",
                extra_metadata={
                    "original_discipline": storage_discipline,
                },
            )
            
        except Exception as e:
            logger.error(f"Error creating room templates for {file_name}: {str(e)}")
            # Continue processing despite template generation failure
    
    return state

