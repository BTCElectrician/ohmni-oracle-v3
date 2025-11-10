"""
Service dependencies for the processing pipeline.

Contains the PipelineServices TypedDict that bundles all external services
needed by pipeline steps.
"""
import logging
from typing import Optional, TypedDict

from openai import AsyncOpenAI
from services.storage_service import FileSystemStorage, OriginalDocumentArchiver


class PipelineServices(TypedDict):
    """Bundled services required by pipeline steps.
    
    All steps receive this dictionary containing external dependencies.
    """
    client: AsyncOpenAI
    storage: FileSystemStorage
    logger: logging.Logger
    original_archiver: Optional[OriginalDocumentArchiver]
    structured_archiver: Optional[OriginalDocumentArchiver]

