"""
Electrical prompt templates for construction drawing processing.
Consolidated with prompts from ai_service.py DRAWING_INSTRUCTIONS.
"""
from templates.prompt_registry import register_prompt, get_registry

# Get registry singleton
registry = get_registry()

# Register main electrical prompt
registry.register(
    "ELECTRICAL",
    """You are an electrical drawing expert extracting structured information. Focus on:
    
1. CRITICAL: Extract all metadata from the drawing's title block including:
   - drawing_number: The drawing number identifier 
   - title: The drawing title/description
   - revision: Revision number or letter
   - date: Drawing date
   - job_number: Project/job number
   - project_name: Full project name

2. All panel schedules - capture complete information about:
   - Panel metadata (name, voltage, phases, rating, location)
   - All circuits with numbers, trip sizes, poles, load descriptions
   - Any panel notes or specifications

3. All equipment schedules with:
   - Complete electrical characteristics (voltage, phase, current ratings)
   - Connection types and mounting specifications
   - Part numbers and manufacturers when available

4. Installation details:
   - Circuit assignments and home run information
   - Mounting heights and special requirements
   - Keyed notes relevant to electrical items
   
Structure all schedule information into consistent field names (e.g., use 'load_name' for descriptions, 
'circuit' for circuit numbers, 'trip' for breaker sizes).

IMPORTANT: Ensure ALL circuits, equipment items, and notes are captured in your output. Missing information 
can cause installation errors.
\n+IMPORTANT: Return your final answer as a single, valid JSON object. Use double quotes for all keys and string values. Do not include explanations or markdown; output only the JSON.
""",
    aliases=["E", "ELEC"],
)

# Register panel schedule subtype
registry.register(
    "ELECTRICAL_PANELSCHEDULE",
    """
You are an expert electrical engineer tasked with extracting ALL information from 
an electrical drawing containing one or more panel schedules. 

Your output MUST be a single, strictly valid JSON object:

1. Create a top-level "DRAWING_METADATA" object for drawing_number, title, revision, date, job_number, project_name, etc.
2. Under "ELECTRICAL", create a "PANEL_SCHEDULES" object (not array). 
   For EACH panel schedule found, create a property with the panel name as the key:
   {
      "PANEL_H1": {
          "total_estimated_demand": "...",
          "total_connected_load": "...",
          // load classification data...
          "circuit_details": [
              {
                 "circuit": "1", // Preserve circuit numbers!
                 "load_name": "...",
                 "trip": "...",
                 "poles": ...,
                 "phase_a": "...", // Include phase data
                 "phase_b": "...",
                 "phase_c": "...",
                 // other circuit properties
              },
              // ALL circuits in numerical order, do NOT omit any
          ]
      },
      "PANEL_L1": {
          // Similar structure for other panels
      }
   }
3. If there are load summary tables, include those under each panel.

IMPORTANT:
- Pay close attention to circuit numbers and preserve the correct numerical sequence
- If circuits appear in left/right paired arrangement (odd/even), maintain this relationship
- For each circuit, include phase load information (A/B/C columns) when present
- Never merge odd and even numbered circuits that appear on the same row
- Ensure numeric values have appropriate units (e.g., "A" for amps, "VA" for volt-amps)

This information is critical for engineers to accurately plan electrical systems.
""",
    aliases=["PANEL_SCHEDULE", "ELECTRICAL_PANEL", "E_PANEL"],
)

# Register lighting subtype
registry.register(
    "ELECTRICAL_LIGHTING",
    """
You are an expert in electrical lighting analyzing a lighting drawing or fixture schedule.

CRITICAL: Extract all metadata from the drawing's title block, including:
- drawing_number (e.g., "E1.00")
- title (e.g., "LIGHTING - FLOOR LEVEL")
- revision (e.g., "3")
- date (e.g., "08/15/2024")
- job_number (e.g., "30J7925")
- project_name (e.g., "ELECTRIC SHUFFLE")

Capture ALL lighting fixtures with these details:
- type_mark: The fixture type identifier
- count: Quantity of this fixture type
- manufacturer: Fixture manufacturer name
- product_number: Product/model number
- description: Complete fixture description
- finish: Material finish
- lamp_type: Lamp specification with wattage and color temp
- mounting: Mounting method
- dimensions: Physical dimensions with units
- location: Installation location
- wattage: Power consumption
- ballast_type: Driver/ballast type
- dimmable: Whether fixture is dimmable
- remarks: Any special notes
- catalog_series: Full catalog reference

Also document all lighting zones and controls:
- zone: Zone identifier
- area: Area served
- circuit: Circuit number
- fixture_type: Type of fixture
- dimming_control: Control type
- notes: Special conditions
- quantities_or_linear_footage: Installation quantity

Structure into a clear, consistent JSON format with metadata at the top level:
{
  "ELECTRICAL": {
    "metadata": {
      "drawing_number": "E1.00",
      "title": "LIGHTING - FLOOR LEVEL",
      "revision": "3",
      "date": "08/15/2024", 
      "job_number": "30J7925",
      "project_name": "ELECTRIC SHUFFLE"
    },
    "LIGHTING_FIXTURE": [...],
    "LIGHTING_ZONE": [...]
  }
}

Lighting design coordination requires COMPLETE accuracy in fixture specifications.
Missing or incorrect information can cause ordering errors and installation conflicts.
""",
    aliases=["LIGHTING", "E_LIGHTING"],
)

# Register riser one-line prompt
registry.register(
    "ELECTRICAL_RISER",
    """
You are analyzing an electrical Riser or One-Line diagram. Extract the system topology 
and key component info into a SINGLE valid JSON object:

1. "DRAWING_METADATA": top-level info (drawing_number, title, revision, date, etc.)
2. "ELECTRICAL": {
     "RISER_ONE_LINE": {
        "components": [
            {
               "id": "SWBD-1",
               "type": "Switchboard",
               "specifications": {
                  "voltage": "480/277V", 
                  "amperage_rating": "2000A",
                  "aic_rating": "65kAIC",
                  "phases": 3,
                  "wires": 4
               },
               "location": "Electrical Room 101"
            },
            // more components (transformers, panels, ATS, generator)
        ],
        "connections": [
            {
               "from_component_id": "UTILITY",
               "to_component_id": "TX-1",
               "feeder_details": {
                   "size": "3#500MCM CU", 
                   "conduit": "3 inch EMT"
               },
               "ocp_details": {
                   "device_type": "Breaker",
                   "trip_rating": "400A"
               }
            }
            // more connections
        ]
     },
     "general_notes": [
       "All conduit routing is schematic."
     ]
   }

CRITICAL JSON RULES:
- Use double quotes for ALL keys and string values.
- NO trailing commas in arrays or objects.
- Numeric fields unquoted (e.g., phases=3, aic_rating=65kAIC if purely numeric => "65" else "65kAIC").
- Capture ALL components and feeders. No partial solutions.
""",
    aliases=["RISER_ONE_LINE", "ONE_LINE", "SINGLE_LINE", "E_RISER"],
)

# Register power subtype
registry.register(
    "ELECTRICAL_POWER",
    """
You are an electrical power drawing expert. Extract and structure all power-related information including:

1. DRAWING_METADATA: Complete drawing identification:
   - drawing_number: Drawing number identifier (e.g., "E2.1")
   - title: Full drawing title (e.g., "POWER PLAN - FIRST FLOOR")
   - revision: Latest revision number or letter
   - date: Drawing date in original format
   - project_name: Complete project name
   - other metadata fields as available

2. POWER_CIRCUIT_DATA: Comprehensive information about power circuits shown:
   - home_runs: All home run connections and circuit numbers
   - circuit_numbers: All circuit identifiers
   - panel_designations: Panel identifiers (e.g., "Panel A", "DP-1")
   - special_circuits: Dedicated or special purpose circuits

3. RECEPTACLE_DATA: Complete details for all receptacles:
   - locations: Descriptive locations
   - mounting_heights: Specific mounting heights (AFF measurements)
   - circuit_assignments: Associated circuit numbers
   - specialty_types: GFCI, isolated ground, special purpose, etc.
   - counts: Total quantity by type/area

4. CONNECTED_EQUIPMENT: All electrically connected equipment:
   - HVAC connections
   - Plumbing equipment connections
   - Kitchen/specialty equipment
   - IT/data infrastructure

5. ANNOTATIONS: Capture all notes, callouts, and specifications:
   - Installation requirements
   - Special mounting details
   - Code compliance notes
   - Coordination requirements

Structure as a clearly organized JSON with ELECTRICAL as the main category. Preserve all field names and values exactly as shown on the drawing.

CRITICAL: Power distribution is essential for building function. ALL circuits, receptacles, and connection points must be captured for proper installation and load calculations.

{
  "DRAWING_METADATA": {
    "drawing_number": "E2.1",
    "title": "POWER PLAN - FIRST FLOOR"
  },
  "ELECTRICAL": {
    "POWER_DATA": {
      // All power-related information
    }
  }
}
""",
    aliases=["POWER", "E_POWER"],
)

# Register specifications subtype
registry.register(
    "ELECTRICAL_SPEC_",
    """
EXTRACT EVERY DETAIL from the Electrical Specification document. Do not summarize or condense.
Include ALL sections, subsections, and individual requirements VERBATIM.
Your response must be COMPREHENSIVE and COMPLETE, capturing the full text of:
- Every numbered section and subsection (e.g., PART 1, 1.1, A., 1., a.)
- All paragraphs associated with each section/subsection
- All bullet points and lists
- All tables and structured content within sections
- All technical requirements and specifications

Structure the output as a single, valid JSON object, nested under 'ELECTRICAL':
{
  "DRAWING_METADATA": {
    "drawing_number": "E0.01",
    "title": "ELECTRICAL SPECIFICATIONS",
    "revision": "...",
    "date": "..."
  },
  "ELECTRICAL": {
    "SPECIFICATIONS": {
      "sections": [
        {
          "number": "26 05 00",
          "title": "COMMON WORK RESULTS FOR ELECTRICAL",
          "content": "Full text of section, including ALL subsections...",
          "subsections": [
            {
              "number": "1.1",
              "title": "RELATED DOCUMENTS",
              "content": "Complete text of this subsection..."
            },
            // Additional subsections
          ]
        },
        // Additional specification sections
      ]
    }
  }
}

CRITICAL: Specifications contain contractually binding requirements. Missing or incorrectly transcribed information can lead to installation errors, change orders, and project delays. CAPTURE EVERYTHING EXACTLY AS WRITTEN.
""",
    aliases=["SPEC_", "E_SPEC_"],
)

# Also register the original form for backward compatibility
registry.register(
    "ELECTRICAL_SPEC",
    """
EXTRACT EVERY DETAIL from the Electrical Specification document. Do not summarize or condense.
Include ALL sections, subsections, and individual requirements VERBATIM.
Your response must be COMPREHENSIVE and COMPLETE, capturing the full text of:
- Every numbered section and subsection (e.g., PART 1, 1.1, A., 1., a.)
- All paragraphs associated with each section/subsection
- All bullet points and lists
- All tables and structured content within sections
- All technical requirements and specifications

Structure the output as a single, valid JSON object, nested under 'ELECTRICAL':
{
  "DRAWING_METADATA": {
    "drawing_number": "E0.01",
    "title": "ELECTRICAL SPECIFICATIONS",
    "revision": "...",
    "date": "..."
  },
  "ELECTRICAL": {
    "SPECIFICATIONS": {
      "sections": [
        {
          "number": "26 05 00",
          "title": "COMMON WORK RESULTS FOR ELECTRICAL",
          "content": "Full text of section, including ALL subsections...",
          "subsections": [
            {
              "number": "1.1",
              "title": "RELATED DOCUMENTS",
              "content": "Complete text of this subsection..."
            },
            // Additional subsections
          ]
        },
        // Additional specification sections
      ]
    }
  }
}

CRITICAL: Specifications contain contractually binding requirements. Missing or incorrectly transcribed information can lead to installation errors, change orders, and project delays. CAPTURE EVERYTHING EXACTLY AS WRITTEN.
""",
    aliases=["SPEC", "E_SPEC"],
)


# Keep backward compatibility with the decorator approach
@register_prompt("Electrical")
def default_electrical_prompt():
    """Default prompt for electrical drawings (if no specific subtype detected)."""
    return registry.get("ELECTRICAL")


@register_prompt("Electrical", "PANEL_SCHEDULE")
def panel_schedule_prompt():
    """Prompt for electrical panel schedules."""
    return registry.get("ELECTRICAL_PANELSCHEDULE")


@register_prompt("Electrical", "RISER_ONE_LINE")
def riser_one_line_prompt():
    """Prompt for electrical riser / one-line (single-line) diagrams."""
    return registry.get("ELECTRICAL_RISER")


@register_prompt("Electrical", "LIGHTING")
def lighting_fixture_prompt():
    """Prompt for lighting fixtures."""
    return registry.get("ELECTRICAL_LIGHTING")


@register_prompt("Electrical", "POWER")
def power_connection_prompt():
    """Prompt for power connections."""
    return registry.get("ELECTRICAL_POWER")


@register_prompt("Electrical", "SPEC")
def electrical_spec_prompt():
    """Prompt for Electrical Specifications, focusing on verbatim extraction."""
    return registry.get("ELECTRICAL_SPEC")
