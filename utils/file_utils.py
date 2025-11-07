import os
import logging
from typing import Iterable, List, Optional, Set

logger = logging.getLogger(__name__)


def _normalize_paths(paths: Iterable[str]) -> Set[str]:
    """Normalize a list of filesystem paths to their absolute form."""
    normalized = set()
    for path in paths:
        if not path:
            continue
        normalized.add(os.path.abspath(path))
    return normalized


def traverse_job_folder(job_folder: str, exclude_paths: Optional[List[str]] = None) -> List[str]:
    """
    Traverse the job folder and collect all PDF files, optionally excluding paths.
    
    Args:
        job_folder: Root folder to search
        exclude_paths: Optional list of paths (files or directories) to ignore
    """
    job_folder = os.path.abspath(job_folder)
    excluded = _normalize_paths(exclude_paths or [])
    pdf_files: List[str] = []

    try:
        for root, dirs, files in os.walk(job_folder, topdown=True):
            abs_root = os.path.abspath(root)

            # Trim excluded directories before descending further
            dirs[:] = [
                d
                for d in dirs
                if os.path.abspath(os.path.join(abs_root, d)) not in excluded
            ]

            for file in files:
                if file.lower().endswith(".pdf"):
                    pdf_path = os.path.join(abs_root, file)

                    # Guard against files that live inside an excluded path (e.g., symlinks)
                    if any(
                        os.path.commonpath([pdf_path, excluded_path]) == excluded_path
                        for excluded_path in excluded
                    ):
                        continue

                    pdf_files.append(pdf_path)

        logger.info(f"Found {len(pdf_files)} PDF files in {job_folder}")
    except Exception as e:
        logger.error(f"Error traversing job folder {job_folder}: {str(e)}")
    return pdf_files
