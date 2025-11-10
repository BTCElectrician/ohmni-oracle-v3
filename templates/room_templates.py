import json
import os
import logging
import copy  # Added for deepcopy
import re

logger = logging.getLogger(__name__)


def _normalize_identifier_value(value: str) -> str:
    """Normalize whitespace while preserving meaningful alphanumeric identifiers."""
    if not value:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def _slugify_identifier(value: str) -> str:
    """Create a filesystem-safe identifier fragment."""
    if not value:
        return "UNIDENTIFIED"
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value.upper()).strip("_")
    return slug or "UNIDENTIFIED"


def load_template(template_name):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(current_dir, f"{template_name}_template.json")
    try:
        with open(template_path, "r") as file:
            return json.load(file)
    except FileNotFoundError:
        logger.error(f"Template file not found: {template_path}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from file {template_path}: {e}")
        return {}


def generate_rooms_data(parsed_data, room_type):
    """
    Generates room data by merging AI parsed data into a predefined template.
    Ensures all fields from the template are present in the output for each room.
    """
    base_template = load_template(room_type)
    if not base_template:
        logger.error(f"Failed to load base template for {room_type}.")
        return {"metadata": {}, "project_name": "", "floor_number": "", "rooms": []}

    # Extract metadata and project name
    metadata = parsed_data.get("DRAWING_METADATA", {})
    project_name = metadata.get("project_name", "")

    rooms_data_output = {
        "metadata": metadata,
        "project_name": project_name,
        "floor_number": "",
        "rooms": [],
    }

    # SEARCH STRATEGY: Check multiple locations for room data
    parsed_rooms = []

    # 1. Check primary expected location
    if (
        "ARCHITECTURAL" in parsed_data
        and isinstance(parsed_data.get("ARCHITECTURAL"), dict)
        and "ROOMS" in parsed_data["ARCHITECTURAL"]
        and isinstance(parsed_data["ARCHITECTURAL"].get("ROOMS"), list)
    ):
        parsed_rooms = parsed_data["ARCHITECTURAL"]["ROOMS"]
        logger.info(f"Found {len(parsed_rooms)} rooms in ARCHITECTURAL.ROOMS")

    # 2. Check if rooms are in a top-level array
    elif "rooms" in parsed_data and isinstance(parsed_data.get("rooms"), list):
        parsed_rooms = parsed_data.get("rooms", [])
        logger.info(f"Found {len(parsed_rooms)} rooms in top-level 'rooms' array")

    # 3. Check if rooms are in room_information
    elif (
        "room_information" in parsed_data
        and isinstance(parsed_data.get("room_information"), dict)
        and "rooms" in parsed_data["room_information"]
        and isinstance(parsed_data["room_information"].get("rooms"), list)
    ):
        parsed_rooms = parsed_data["room_information"]["rooms"]
        logger.info(f"Found {len(parsed_rooms)} rooms in room_information.rooms")

    # 4. Check if rooms are directly in ARCHITECTURAL
    elif (
        "ARCHITECTURAL" in parsed_data
        and isinstance(parsed_data.get("ARCHITECTURAL"), dict)
        and any(
            k.lower().startswith("room") for k in parsed_data["ARCHITECTURAL"].keys()
        )
    ):
        # Look for room arrays in ARCHITECTURAL
        for key, value in parsed_data["ARCHITECTURAL"].items():
            if isinstance(value, list) and key.lower().startswith("room"):
                parsed_rooms = value
                logger.info(f"Found {len(parsed_rooms)} rooms in ARCHITECTURAL.{key}")
                break

    # 5. Look for any array of objects that look like rooms
    if not parsed_rooms:
        for key, value in parsed_data.items():
            if (
                isinstance(value, list)
                and len(value) > 0
                and isinstance(value[0], dict)
            ):
                # Check if these look like rooms (have room_number or name keys)
                room_keys = ["room_number", "number", "room_name", "name", "room"]
                if any(rk in value[0] for rk in room_keys):
                    parsed_rooms = value
                    logger.info(f"Found {len(parsed_rooms)} possible rooms in {key}")
                    break

    # If we still don't have rooms, try one more fallback:
    # Look for room-like keys in ARCHITECTURAL
    if not parsed_rooms and "ARCHITECTURAL" in parsed_data:
        arch_data = parsed_data["ARCHITECTURAL"]
        room_candidate_keys = [
            k
            for k in arch_data.keys()
            if k.lower().startswith("room") or "room" in k.lower()
        ]

        for key in room_candidate_keys:
            value = arch_data[key]
            if isinstance(value, list) and len(value) > 0:
                parsed_rooms = value
                logger.info(f"Found {len(parsed_rooms)} rooms in ARCHITECTURAL.{key}")
                break

    # If no rooms found through any method, log a warning
    if not parsed_rooms:
        drawing_num = metadata.get("drawing_number", "N/A")
        logger.warning(
            f"No rooms found in parsed data for {room_type}. File: {drawing_num}"
        )
        structure_info = list(parsed_data.keys())
        if "ARCHITECTURAL" in parsed_data:
            structure_info.append(
                f"ARCHITECTURAL keys: {list(parsed_data['ARCHITECTURAL'].keys())}"
            )
        logger.warning(f"JSON structure: {structure_info}")
        return rooms_data_output

    # Process all found rooms
    for parsed_room in parsed_rooms:
        # Skip if not a dictionary
        if not isinstance(parsed_room, dict):
            continue

        # Try different keys for room number and name
        room_keys = {
            "number": ["room_number", "number", "id", "room_id", "mark", "room"],
            "name": ["room_name", "name", "function", "usage", "description"],
        }

        # Extract room number using multiple possible keys
        room_number_str = ""
        for key in room_keys["number"]:
            if key in parsed_room and parsed_room[key]:
                room_number_str = _normalize_identifier_value(str(parsed_room[key]))
                if room_number_str.startswith("Room_"):
                    room_number_str = room_number_str.replace("Room_", "")
                break

        # Extract room name using multiple possible keys
        room_name = ""
        for key in room_keys["name"]:
            if key in parsed_room and parsed_room[key]:
                room_name = _normalize_identifier_value(str(parsed_room[key]))
                break

        if not room_number_str and room_name:
            room_number_str = room_name
            logger.info(
                "Room missing explicit number; using name as identifier: %s",
                room_name,
            )

        # Skip rooms without identifiers
        if not room_number_str:
            logger.warning(f"Skipping room missing number: {parsed_room}")
            continue

        room_identifier_slug = _slugify_identifier(room_number_str)

        # Create a new room entry from the template
        room_data = copy.deepcopy(base_template)

        # Set required fields
        room_data["room_id"] = f"Room_{room_identifier_slug}"
        room_data["room_number"] = room_number_str

        if room_name and room_name.lower() != room_number_str.lower():
            room_label = f"{room_name}_{room_number_str}"
        else:
            room_label = room_name or f"Room_{room_number_str}"
        room_data["room_name"] = room_label

        # Copy other fields that match template structure
        for key, value in parsed_room.items():
            # Skip already processed fields
            if key in ["room_number", "number", "room_name", "name"]:
                continue

            # Copy fields that exist in the template
            if key in room_data:
                room_data[key] = value
            # For nested structures, try to merge
            elif isinstance(value, dict) and isinstance(room_data.get(key, {}), dict):
                # Shallow merge of dictionaries
                if key not in room_data:
                    room_data[key] = {}
                room_data[key].update(value)

        # Add completed room to output
        rooms_data_output["rooms"].append(room_data)

    # Additional sanity check on output
    if not rooms_data_output["rooms"]:
        logger.warning(
            f"Failed to populate any rooms after processing {len(parsed_rooms)} found rooms"
        )
    else:
        logger.info(
            f"Successfully populated {len(rooms_data_output['rooms'])} rooms for {room_type}"
        )

    return rooms_data_output


def process_architectural_drawing(parsed_data, file_path, output_folder):
    """
    Process architectural drawing data and generate room template files.
    """
    # Get drawing metadata from various possible locations
    drawing_metadata = {}
    metadata_keys = ["DRAWING_METADATA", "metadata", "drawing_info"]

    # Try standard locations
    for key in metadata_keys:
        if key in parsed_data:
            drawing_metadata = parsed_data[key]
            break

    # Try in ARCHITECTURAL section
    if not drawing_metadata and "ARCHITECTURAL" in parsed_data:
        for key in metadata_keys:
            if key in parsed_data["ARCHITECTURAL"]:
                drawing_metadata = parsed_data["ARCHITECTURAL"][key]
                break

    # Get basic info
    drawing_number = drawing_metadata.get("drawing_number", "")
    title = drawing_metadata.get("title", "").upper()
    is_reflected_ceiling = "REFLECTED CEILING" in title

    # Detailed logging of parsed data structure for debugging
    logger.info(f"Generating room templates for {drawing_number}...")
    logger.info(f"Parsed data contains keys: {list(parsed_data.keys())}")
    if "ARCHITECTURAL" in parsed_data:
        logger.info(
            f"ARCHITECTURAL section contains: {list(parsed_data['ARCHITECTURAL'].keys())}"
        )

    # Generate room data
    e_rooms_data = generate_rooms_data(parsed_data, "e_rooms")
    a_rooms_data = generate_rooms_data(parsed_data, "a_rooms")

    # Attach source document reference so templates know their origin
    source_document_info = parsed_data.get("source_document")
    if not source_document_info:
        source_document_info = {
            "filename": os.path.basename(file_path),
            "local_path": file_path,
        }

    e_rooms_data["source_document"] = source_document_info
    a_rooms_data["source_document"] = source_document_info

    # Ensure metadata is propagated to template files
    if drawing_metadata:
        # Update metadata in output if it wasn't already populated
        if not e_rooms_data.get("metadata"):
            e_rooms_data["metadata"] = drawing_metadata
            a_rooms_data["metadata"] = drawing_metadata

        # Ensure project name is populated
        if "project_name" in drawing_metadata:
            project_name = drawing_metadata["project_name"]
            if not e_rooms_data.get("project_name"):
                e_rooms_data["project_name"] = project_name
                a_rooms_data["project_name"] = project_name

    # Generate output filenames
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    e_rooms_file = os.path.join(output_folder, f"{base_filename}_e_rooms_details.json")
    a_rooms_file = os.path.join(output_folder, f"{base_filename}_a_rooms_details.json")

    # Save files with detailed error handling
    try:
        with open(e_rooms_file, "w") as f:
            json.dump(e_rooms_data, f, indent=2)
        logger.info(
            f"Saved electrical room details to: {e_rooms_file} with {len(e_rooms_data['rooms'])} rooms"
        )
    except Exception as e:
        logger.error(f"Failed to save e_rooms data: {str(e)}")

    try:
        with open(a_rooms_file, "w") as f:
            json.dump(a_rooms_data, f, indent=2)
        logger.info(
            f"Saved architectural room details to: {a_rooms_file} with {len(a_rooms_data['rooms'])} rooms"
        )
    except Exception as e:
        logger.error(f"Failed to save a_rooms data: {str(e)}")

    return {
        "e_rooms_file": e_rooms_file,
        "a_rooms_file": a_rooms_file,
        "is_reflected_ceiling": is_reflected_ceiling,
        "room_count": len(a_rooms_data["rooms"]),
        "generated_files": [e_rooms_file, a_rooms_file],
    }
