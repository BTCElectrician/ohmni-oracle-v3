Perfect! Now that your code is clean, here's EXACTLY what you need to add for Azure AI Search integration:

## Step 1: Add the Azure Formatter Service

Create a new file: `services/azure_formatter.py`

I'll update the artifact to use GPT-5 nano with the correct parameters:## Step 2: Add Integration to Your Existing Files

### In `processing/file_processor.py`:

Find the `_step_save_output` method (around line 380-420), and right AFTER it saves successfully, add:

```python
# Right after this existing code:
if not await self._step_save_output():
    pbar.update(20)
    return cast(ProcessingResult, self.processing_state["final_status_dict"])
pbar.update(10)

# ADD THIS NEW CODE:
# Azure AI Search format generation
if os.getenv("ENABLE_AZURE_FORMAT", "false").lower() == "true":
    try:
        from services.azure_formatter import enhance_with_azure_format
        await enhance_with_azure_format(
            self.processing_state["parsed_json_data"],
            self.pdf_path,
            self.client,  # Your existing OpenAI client
            self.storage,
            self.structured_output_path
        )
        self.logger.info("Generated Azure AI Search format")
    except Exception as e:
        self.logger.warning(f"Azure format generation failed (non-critical): {e}")
```

### In `templates/room_templates.py`:

At the end of the `process_architectural_drawing` function (around line 260), after saving the room files, add:

```python
# After these existing lines:
with open(a_rooms_file, "w") as f:
    json.dump(a_rooms_data, f, indent=2)

# ADD THIS:
if os.getenv("ENABLE_AZURE_FORMAT", "false").lower() == "true":
    try:
        from services.azure_formatter import save_room_templates_for_azure
        # Note: This needs to be async, so you might need to make process_architectural_drawing async
        # Or save it synchronously for now
        import asyncio
        asyncio.run(save_room_templates_for_azure(
            e_rooms_data,
            a_rooms_data,
            drawing_metadata.get("drawing_number", ""),
            output_folder,
            None  # storage service - can be None for local files
        ))
    except Exception as e:
        logger.warning(f"Azure room template format failed (non-critical): {e}")
```

## Step 3: Add to Your `.env` File

```bash
# Azure AI Search Integration
ENABLE_AZURE_FORMAT=true

# Optional - for future blob storage upload
AZURE_STORAGE_CONNECTION_STRING=your-connection-string-here
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-admin-key
```

## Step 4: Test It!

1. Set `ENABLE_AZURE_FORMAT=true` in your `.env`
2. Run your script on ONE test PDF
3. Check that you get both files:
   - `E101_structured.json` (your original)
   - `E101_azure.json` (new Azure format)

## That's It!

You're adding:
- 1 new file (`azure_formatter.py`)
- ~10 lines in `file_processor.py`
- ~10 lines in `room_templates.py`
- 1 environment variable

The Azure format files will appear alongside your regular files, ready to upload to Azure AI Search when you're ready for that step.

# services/azure_formatter.py
"""
Azure AI Search formatter for construction drawings.
AI-first approach: Let OpenAI generate the semantic summary.
"""
import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AzureSearchFormatter:
    """
    Formats extracted drawing data for Azure AI Search.
    Uses AI to generate semantic summaries rather than complex parsing logic.
    """
    
    def __init__(self, openai_client):
        self.client = openai_client
        self.enabled = os.getenv("ENABLE_AZURE_FORMAT", "false").lower() == "true"
        
    async def format_for_azure(self, 
                               extracted_json: Dict[str, Any],
                               pdf_path: str,
                               drawing_type: str) -> Optional[Dict[str, Any]]:
        """
        Wraps existing extraction in Azure AI Search format.
        
        Args:
            extracted_json: Your existing extracted JSON output
            pdf_path: Path to the original PDF
            drawing_type: Detected drawing type (Electrical, Mechanical, etc.)
            
        Returns:
            Azure-formatted document or None if disabled
        """
        if not self.enabled:
            return None
            
        # Get semantic summary using AI (the magic happens here)
        semantic_summary = await self._generate_semantic_summary(extracted_json)
        
        # Extract metadata
        metadata = extracted_json.get("DRAWING_METADATA", {})
        sheet_number = metadata.get("drawing_number", "")
        
        # Build blob path (future-proofing for when you upload)
        project_name = self._extract_project_name(pdf_path)
        discipline = drawing_type.lower() if drawing_type else "general"
        blob_path = f"{project_name}/{discipline}/{sheet_number}.pdf"
        
        # Classify drawing category for Azure team
        category = self._classify_category(pdf_path, metadata.get("title", ""))
        
        return {
            # Required fields
            "sheet_number": sheet_number,
            "source_file": blob_path,
            "content": semantic_summary,
            "raw_json": extracted_json,
            
            # Metadata
            "project": project_name,
            "sheet_title": metadata.get("title", ""),
            "discipline": discipline,
            "drawing_type": category,
            "revision": metadata.get("revision", ""),
            "processed_date": datetime.utcnow().isoformat(),
            "page_count": metadata.get("page_count", 1)
        }
    
    async def _generate_semantic_summary(self, json_data: Dict[str, Any]) -> str:
        """
        The AI-first magic: Let GPT-4o-mini create the perfect search summary.
        
        This is brilliant because:
        1. No complex parsing logic to maintain
        2. AI understands context and importance
        3. Automatically adapts to any drawing type
        4. Costs ~$0.0001 per drawing
        """
        
        prompt = """Create a searchable summary of this construction drawing data.
Include: equipment IDs, panel names, room numbers, circuit numbers, system types,
locations, and any other identifiable references. Keep it under 500 words.
Focus on terms someone would search for. Format as a single paragraph.

Drawing data:
"""
        
        # Take first 10KB of JSON to stay within token limits
        json_str = json.dumps(json_data)[:10000]
        
        try:
            response = await self.client.chat.completions.create(
                model="gpt-5-nano",  # Fastest and cheapest
                messages=[
                    {"role": "system", "content": "You are a construction drawing analyzer creating search keywords."},
                    {"role": "user", "content": prompt + json_str}
                ],
                temperature=0.1,  # More deterministic
                max_tokens=500,
                reasoning_effort="minimal",  # GPT-5 nano specific - perfect for keyword extraction
                verbosity="concise"  # Keep output tight
            )
            
            summary = response.choices[0].message.content
            logger.info(f"Generated semantic summary: {len(summary)} chars")
            return summary
            
        except Exception as e:
            logger.error(f"Failed to generate semantic summary: {e}")
            # Fallback: Just use title and basic info
            metadata = json_data.get("DRAWING_METADATA", {})
            return f"Drawing {metadata.get('drawing_number', '')} {metadata.get('title', '')}"
    
    def _classify_category(self, pdf_path: str, title: str) -> str:
        """Simple category classification for Azure team."""
        
        categories = {
            "schedule": ["schedule", "panel", "equipment", "fixture"],
            "plan": ["plan", "layout", "floor"],
            "detail": ["detail", "typical", "section"],
            "riser": ["riser", "diagram", "one-line"],
            "elevation": ["elevation", "facade"],
        }
        
        name_lower = os.path.basename(pdf_path).lower()
        title_lower = title.lower()
        
        for category, keywords in categories.items():
            if any(kw in name_lower or kw in title_lower for kw in keywords):
                return category
                
        return "general"
    
    def _extract_project_name(self, pdf_path: str) -> str:
        """Extract project name from file path."""
        # Assuming structure like: /path/to/veridian-block-1/electrical/E101.pdf
        parts = Path(pdf_path).parts
        
        # Look for common patterns
        for i, part in enumerate(parts):
            if any(disc in part.lower() for disc in ['electrical', 'mechanical', 'plumbing', 'architectural']):
                if i > 0:
                    return parts[i-1]
        
        # Default to parent directory name
        return Path(pdf_path).parent.parent.name


class RoomTemplateFormatter:
    """
    Formats room templates as searchable, writable documents.
    These are special - they start empty and get filled by field teams.
    """
    
    @staticmethod
    def format_for_azure(room_data: Dict[str, Any], 
                        floor_plan_sheet: str,
                        template_type: str) -> Dict[str, Any]:
        """
        Format room template for Azure AI Search.
        
        Args:
            room_data: Room template data (from e_rooms or a_rooms template)
            floor_plan_sheet: Reference to the floor plan drawing
            template_type: 'electrical' or 'architectural'
        """
        room_id = room_data.get("room_id", "")
        room_name = room_data.get("room_name", "")
        
        # Build searchable content for empty template
        content = f"Room template {room_id} {room_name} type {template_type} from floor plan {floor_plan_sheet}"
        
        # Add any pre-filled data to content
        if template_type == "electrical" and room_data.get("circuits"):
            circuits = room_data["circuits"]
            if circuits.get("lighting") or circuits.get("power"):
                content += f" circuits: {' '.join(circuits.get('lighting', []))} {' '.join(circuits.get('power', []))}"
        
        return {
            # Special document type to distinguish from drawings
            "document_type": "room_template",
            "sheet_number": f"TEMPLATE-{room_id}-{template_type[0].upper()}",
            "source_file": f"templates/{floor_plan_sheet}/{room_id}_{template_type}.json",
            "content": content,
            
            # The actual template data
            "template_data": room_data,
            "template_type": template_type,
            
            # Metadata
            "parent_drawing": floor_plan_sheet,
            "room_id": room_id,
            "room_name": room_name,
            "is_populated": False,  # Changes when foreman fills it
            "is_writable": True,    # Flags for Azure Function
            "processed_date": datetime.utcnow().isoformat()
        }


# ===== INTEGRATION POINT =====
# Add this to your existing processing/file_processor.py at the very end of process_pdf_async

async def enhance_with_azure_format(parsed_json: Dict[str, Any],
                                   pdf_path: str,
                                   client,
                                   storage_service,
                                   output_path: str) -> None:
    """
    Add this function call at the end of process_pdf_async, after the regular save.
    
    Example integration:
    
    # In process_pdf_async, after your existing save:
    if not await self._step_save_output():
        return self.processing_state["final_status_dict"]
    
    # ADD THIS:
    await enhance_with_azure_format(
        self.processing_state["parsed_json_data"],
        self.pdf_path,
        self.client,
        self.storage,
        self.structured_output_path
    )
    """
    
    # Only run if enabled
    if os.getenv("ENABLE_AZURE_FORMAT", "false").lower() != "true":
        return
    
    try:
        # Get drawing type from the path
        from utils.drawing_utils import detect_drawing_info
        drawing_type, _ = detect_drawing_info(pdf_path)
        
        # Create formatter with the same OpenAI client
        formatter = AzureSearchFormatter(client)
        
        # Generate Azure format
        azure_doc = await formatter.format_for_azure(
            parsed_json,
            pdf_path,
            drawing_type
        )
        
        if azure_doc:
            # Save alongside regular output
            azure_path = output_path.replace("_structured.json", "_azure.json")
            await storage_service.save_json(azure_doc, azure_path)
            logger.info(f"Saved Azure format to {azure_path}")
            
    except Exception as e:
        logger.error(f"Failed to create Azure format: {e}")
        # Don't fail the main processing


# ===== ROOM TEMPLATE INTEGRATION =====
# Add this to your existing templates/room_templates.py process_architectural_drawing function

async def save_room_templates_for_azure(e_rooms_data: Dict[str, Any],
                                       a_rooms_data: Dict[str, Any],
                                       floor_plan_sheet: str,
                                       output_folder: str,
                                       storage_service) -> None:
    """
    Add this to process_architectural_drawing after saving regular templates.
    
    Example:
    # After your existing saves:
    with open(e_rooms_file, 'w') as f:
        json.dump(e_rooms_data, f, indent=2)
    
    # ADD THIS:
    await save_room_templates_for_azure(
        e_rooms_data, a_rooms_data, 
        drawing_metadata.get('drawing_number'),
        output_folder, storage_service
    )
    """
    
    if os.getenv("ENABLE_AZURE_FORMAT", "false").lower() != "true":
        return
        
    formatter = RoomTemplateFormatter()
    
    # Process each room
    for e_room, a_room in zip(e_rooms_data.get("rooms", []), a_rooms_data.get("rooms", [])):
        room_id = e_room.get("room_id", "")
        
        # Create electrical template document
        e_doc = formatter.format_for_azure(e_room, floor_plan_sheet, "electrical")
        e_path = os.path.join(output_folder, f"room_{room_id}_electrical_azure.json")
        await storage_service.save_json(e_doc, e_path)
        
        # Create architectural template document  
        a_doc = formatter.format_for_azure(a_room, floor_plan_sheet, "architectural")
        a_path = os.path.join(output_folder, f"room_{room_id}_architectural_azure.json")
        await storage_service.save_json(a_doc, a_path)


# ===== CONFIGURATION =====
# Add to your .env file:
"""
# Azure AI Search Integration
ENABLE_AZURE_FORMAT=false  # Set to true to enable
AZURE_OPENAI_API_KEY=your-key-here  # If using Azure OpenAI
AZURE_SEARCH_ENDPOINT=https://your-search.search.windows.net
AZURE_SEARCH_KEY=your-search-key
"""