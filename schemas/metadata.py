"""
Pydantic schemas for validating drawing metadata.
"""
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import date as date_type


class DrawingMetadata(BaseModel):
    """Schema for validating drawing metadata."""

    drawing_number: str = Field(..., description="Sheet ID or drawing number")
    title: Optional[str] = Field(None, description="Drawing title")
    revision: Optional[str] = Field(None, description="Revision number or letter")
    date: Optional[date_type] = Field(None, description="Drawing date")
    project_name: Optional[str] = Field(None, description="Project name")
    job_number: Optional[str] = Field(None, description="Job or project number")

    class Config:
        """Pydantic model configuration."""

        extra = "allow"  # Allow extra fields that aren't in the model


class FlexibleDrawingMetadata(BaseModel):
    """
    Flexible schema that accepts common variations of field names.
    All fields are optional to handle varying drawing standards.
    """
    # Standard fields (all optional) with common aliases
    drawing_number: Optional[str] = Field(None, alias="sheet_number")
    title: Optional[str] = Field(None, alias="drawing_title") 
    revision: Optional[str] = Field(None, alias="rev")
    date: Optional[Any] = Field(None, alias="issue_date")
    project_name: Optional[str] = Field(None, alias="project")
    job_number: Optional[str] = Field(None, alias="job_no")
    
    # Alternative field names that map to standard ones
    sheet_no: Optional[str] = Field(None, alias="drawing_number")
    pa: Optional[str] = Field(None, alias="project_name")  # Common abbreviation
    
    class Config:
        """Allow any extra fields without errors."""
        extra = "allow"
        populate_by_name = True  # Accept both field name and alias


class ExtractionResultMetadata(BaseModel):
    """Schema for extraction result metadata."""

    title: Optional[str] = None
    author: Optional[str] = None
    subject: Optional[str] = None
    creator: Optional[str] = None
    producer: Optional[str] = None
    creation_date: Optional[str] = None
    modification_date: Optional[str] = None
    page_count: Optional[int] = None
