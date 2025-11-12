"""
Table extraction utilities for PDF pages.
"""
import logging
from typing import List, Dict, Any, Optional

import pymupdf as fitz


def extract_tables_for_page(
    page: fitz.Page,
    page_num: int,
    enable_table_extraction: bool,
    logger: Optional[logging.Logger] = None,
) -> List[Dict[str, Any]]:
    """
    Extract tables from a PDF page safely.

    Args:
        page: PyMuPDF page object
        page_num: Page number (1-based for display)
        enable_table_extraction: Whether table extraction is enabled
        logger: Optional logger instance

    Returns:
        List of table dictionaries with page, table_index, and content
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    tables = []

    if not enable_table_extraction:
        return tables

    try:
        # Only attempt table extraction if page has text
        page_text = page.get_text("text")
        if page_text and page_text.strip():
            try:
                table_finder = page.find_tables()
                if table_finder and hasattr(table_finder, "tables"):
                    for j, table in enumerate(table_finder.tables or []):
                        try:
                            if hasattr(table, "to_markdown"):
                                table_markdown = table.to_markdown()
                                if table_markdown:
                                    tables.append(
                                        {
                                            "page": page_num,
                                            "table_index": j,
                                            "content": table_markdown,
                                        }
                                    )
                        except Exception as e:
                            # Skip individual table errors
                            logger.debug(f"Skipping table {j} on page {page_num}: {str(e)}")
            except AttributeError:
                # Page doesn't support tables - this is normal
                logger.debug(f"Page {page_num} doesn't support table extraction")
    except Exception as e:
        # Log at debug level since this isn't critical
        logger.debug(f"Table extraction skipped for page {page_num}: {str(e)}")

    return tables

