from utils.drawing_utils import detect_drawing_info


def get_drawing_type(filename: str) -> str:
    """
    Detect the drawing type by using the improved detect_drawing_info function.
    Kept for backward compatibility.

    Args:
        filename: The filename to analyze

    Returns:
        String representing the main drawing type
    """
    main_type, _ = detect_drawing_info(filename)
    return main_type


# Legacy function kept for backward compatibility
def get_drawing_subtype(filename: str) -> str:
    """
    Detect the drawing subtype based on keywords in the filename.
    Kept for backward compatibility.

    Args:
        filename: The filename to analyze

    Returns:
        String representing the drawing subtype
    """
    main_type, subtype = detect_drawing_info(filename)

    if subtype:
        return f"{main_type}_{subtype}".lower()
    else:
        return "default"
