"""
Domain models for extraction results.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional


@dataclass
class ExtractionResult:
    """
    Domain model representing the result of a PDF extraction operation.
    Includes a flag to indicate if meaningful content was extracted.
    """

    raw_text: str
    tables: List[Dict[str, Any]]
    success: bool
    has_content: bool
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)
    titleblock_text: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert the result to a dictionary."""
        return {
            "raw_text": self.raw_text,
            "tables": self.tables,
            "success": self.success,
            "has_content": self.has_content,
            "error": self.error,
            "metadata": self.metadata,
            "titleblock_text": self.titleblock_text,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExtractionResult":
        """Create an ExtractionResult from a dictionary."""
        return cls(
            raw_text=data.get("raw_text", ""),
            tables=data.get("tables", []),
            success=data.get("success", False),
            has_content=data.get("has_content", False),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
            titleblock_text=data.get("titleblock_text"),
        )

