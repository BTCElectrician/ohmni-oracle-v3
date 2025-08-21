"""
Architectural prompt templates for construction drawing processing.
Consolidated with prompts from ai_service.py DRAWING_INSTRUCTIONS.
"""
from templates.prompt_registry import register_prompt, get_registry

# Get registry singleton
registry = get_registry()

# Register main architectural prompt
registry.register(
    "ARCHITECTURAL",
    """Extract and structure the following information with PRECISE detail:
    
1. Room information:
   Create a comprehensive 'rooms' array with objects for EACH room, including:
   - 'number': Room number as string (EXACTLY as shown)
   - 'name': Complete room name
   - 'finish': All ceiling finishes
   - 'height': Ceiling height (with units)
   - 'electrical_info': Any electrical specifications
   - 'architectural_info': Additional architectural details
   - 'wall_types': Wall construction for each wall (north/south/east/west)

2. Complete door and window schedules:
   - Door/window numbers, types, sizes, and materials
   - Hardware specifications and fire ratings
   - Frame types and special requirements

3. Wall type details:
   - Create a 'wall_types' array with complete construction details
   - Include fire ratings, acoustic values, and specific assembly info
   - Document wall thickness and material types

4. Key elevations and dimension data:
   - Floor-to-ceiling heights
   - Key dimensions
   - Finish floor elevations

5. Finishes and materials:
   - Catalog all specified finishes (ceiling, wall, floor)
   - Manufacturer-specific details and codes
   - Special installation requirements

6. General notes:
   - Capture ALL general notes shown on drawings
   - Include ALL symbols and abbreviations from legends
   - Document all reference standards cited

IMPORTANT: Architecture drawings establish room numbering, construction, and finishes for all subsequent trades. 
Accurate extraction and structure is essential for coordinated building systems. Missing or incorrect information 
can cause construction conflicts and rework.
""",
    aliases=["A", "ARCH"],
)

# Register floor plan subtype
registry.register(
    "ARCHITECTURAL_FLOORPLAN",
    """
You are an architectural drawing specialist analyzing a floor plan drawing. Extract ALL critical information with complete precision.

Focus on creating a comprehensive 'rooms' array that contains objects for EVERY room shown on the drawing, with these precise details:
- room_number: The exact room number as shown (maintain format with leading zeros, etc.)
- room_name: The complete room name/function
- dimensions: Room dimensions with units (e.g., "12'-0" x 14'-6"")
- area: Room area in square feet/meters if shown
- floor_finish: Floor finish material
- wall_finish: Wall finish material
- ceiling_type: Ceiling type (e.g., ACT, GWB)
- ceiling_height: Height with units (e.g., "9'-0" AFF")
- door_numbers: Array of door numbers accessing this room
- adjacent_rooms: Array of adjacent room numbers
- function_category: Room usage category (e.g., "Office", "Circulation", "Support")
- notes: Any specific notes about this room

Also extract all metadata:
- drawing_number: Sheet number
- title: Drawing title
- scale: Drawing scale
- project_name: Complete project name
- date: Drawing date
- revision: Latest revision

Structure the output as a single, valid JSON object with this format:
{
  "DRAWING_METADATA": {
    "drawing_number": "A1.0",
    "title": "FIRST FLOOR PLAN",
    "scale": "1/8\" = 1'-0\"",
    "project_name": "OFFICE BUILDING",
    "date": "09/15/2023",
    "revision": "3"
  },
  "ARCHITECTURAL": {
    "FLOOR_PLAN": {
      "floor_level": "FIRST FLOOR",
      "floor_elevation": "0'-0\"",
      "rooms": [
        {
          "room_number": "101",
          "room_name": "LOBBY",
          "dimensions": "20'-0\" x 30'-0\"",
          "area": "600 SF",
          "floor_finish": "PT-1",
          "wall_finish": "PNT-1",
          "ceiling_type": "ACT-1",
          "ceiling_height": "10'-0\" AFF",
          "door_numbers": ["101A", "101B"],
          "adjacent_rooms": ["102", "103", "EXTERIOR"],
          "function_category": "Public",
          "notes": "Main building entrance"
        },
        // Additional rooms
      ],
      "general_notes": [
        "ALL DIMENSIONS ARE TO FACE OF STUD U.O.N.",
        "VERIFY ALL DIMENSIONS IN FIELD PRIOR TO CONSTRUCTION"
      ]
    }
  }
}

CRITICAL: Floor plans establish THE definitive room layout, numbering, and relationships that ALL other building systems reference. Missing or incorrect room data will cause downstream coordination issues for ALL trades.
""",
    aliases=["FLOOR_PLAN", "PLAN", "A_PLAN"],
)

# Register reflected ceiling plan subtype
registry.register(
    "ARCHITECTURAL_REFLECTEDCEILING",
    """
You are analyzing a Reflected Ceiling Plan drawing. Extract ALL ceiling-related information with complete precision.

Create a comprehensive structure capturing:

1. Complete 'rooms' array with detailed ceiling information for EVERY room:
   - room_number: The exact room identifier (e.g., "101")
   - room_name: Complete room name
   - ceiling_type: Primary ceiling material (e.g., "ACT-1", "GWB", "Open")
   - ceiling_height: Height with units (e.g., "9'-0\" AFF")
   - ceiling_details: Any special ceiling features (coffers, soffits, exposed structure)
   - light_fixtures: Types and counts of light fixtures shown
   - mechanical_elements: Air devices (diffusers, returns, etc.)
   - sprinklers: Fire sprinkler locations if shown
   - special_elements: Special ceiling-mounted elements

2. Ceiling material specifications:
   - Complete material legends
   - Manufacturer details
   - Special mounting requirements

3. Coordination elements:
   - Ceiling grid layout and orientation
   - Bulkhead and soffit details
   - Ceiling transitions
   - Access panel locations

Format as a valid JSON object with this structure:
{
  "DRAWING_METADATA": {
    "drawing_number": "A2.2",
    "title": "FIRST FLOOR REFLECTED CEILING PLAN",
    "scale": "1/8\" = 1'-0\"",
    "project_name": "OFFICE BUILDING",
    "date": "09/15/2023", 
    "revision": "2"
  },
  "ARCHITECTURAL": {
    "REFLECTED_CEILING_PLAN": {
      "floor_level": "FIRST FLOOR",
      "rooms": [
        {
          "room_number": "101",
          "room_name": "LOBBY",
          "ceiling_type": "ACT-1",
          "ceiling_height": "10'-0\" AFF",
          "ceiling_details": "2'x2' grid, running N-S",
          "light_fixtures": ["Type A (4)", "Type C (2)"],
          "mechanical_elements": ["24\"x24\" Supply Diffuser (3)", "Linear Return (1)"],
          "sprinklers": "Standard pendant, centered in ACT tiles",
          "special_elements": "Decorative pendant lights over reception desk"
        },
        // Additional rooms
      ],
      "ceiling_materials": [
        {
          "code": "ACT-1",
          "description": "Armstrong Ultima #1914, White, 2'x2'",
          "mounting": "15/16\" exposed grid, white"
        },
        // Additional materials
      ],
      "general_notes": [
        "ALL CEILING HEIGHTS ARE TO FINISHED FACE OF CEILING U.O.N.",
        "COORDINATE ALL CEILING-MOUNTED ITEMS WITH MECHANICAL, ELECTRICAL, AND FIRE PROTECTION DRAWINGS."
      ]
    }
  }
}

CRITICAL: Reflected Ceiling Plans coordinate locations of ALL ceiling-mounted systems and establish ceiling heights throughout the building. Complete extraction of ceiling types, heights, and coordination elements is ESSENTIAL for proper MEP system integration.
""",
    aliases=["RCP", "CEILING", "REFLECTED"],
)

# Register wall type subtype
registry.register(
    "ARCHITECTURAL_WALL",
    """
Extract COMPLETE DETAILS for ALL wall types shown in this architectural drawing.

For EACH wall type identified, capture:
1. Wall type identifier (e.g., "Type A", "W1", etc.) - exactly as shown
2. Complete and DETAILED construction information:
   - ALL layers of materials from exterior to interior
   - EXACT thicknesses of each material
   - Special components (vapor barriers, insulation)
   - Rating information (fire rating, STC rating)
   - Full height requirements (to structure, above ceiling)
   - Base and top conditions
3. Special requirements:
   - Staggering of joints
   - Specific fastening requirements
   - Sealing/fireproofing details
   - Special framing

Structure as a valid JSON with this format:
{
  "DRAWING_METADATA": {
    "drawing_number": "A5.1",
    "title": "WALL TYPES"
  },
  "ARCHITECTURAL": {
    "WALL_TYPES": [
      {
        "type_id": "W1",
        "description": "1-HR RATED PARTITION",
        "fire_rating": "1 HR",
        "stc_rating": "STC 45",
        "total_thickness": "5 5/8\"",
        "extends_to": "UNDERSIDE OF STRUCTURE",
        "layers": [
          {"side": "both", "material": "5/8\" TYPE X GWB", "thickness": "5/8\""},
          {"side": "middle", "material": "3 5/8\" METAL STUDS @ 16\" O.C.", "thickness": "3 5/8\""},
          {"side": "middle", "material": "BATT INSULATION", "thickness": "3 1/2\""}
        ],
        "notes": ["PROVIDE ACOUSTICAL SEALANT AT TOP AND BOTTOM TRACKS", "STAGGER JOINTS ON OPPOSITE SIDES"]
      },
      // Additional wall types
    ]
  }
}

CRITICAL: Wall type details are essential reference information that determines construction methods, costs, and performance requirements. Each layer must be precisely documented with exact thickness and specification to ensure proper construction.
""",
    aliases=["WALL", "PARTITION", "A_WALL"],
)

# Register door schedule subtype
registry.register(
    "ARCHITECTURAL_DOOR",
    """
Extract COMPLETE DETAILS for the ENTIRE door schedule.

For EACH door in the schedule, capture:
1. Door number/ID (exactly as shown, e.g., "101A") 
2. ALL specifications:
   - Door type/style
   - Material
   - Size (width, height, thickness)
   - Fire rating
   - Frame type/material
   - Hardware group/set
   - Special requirements
   - Remarks/notes
3. Associated information:
   - Room connections (from/to)
   - Locking requirements
   - Access control integration

Also extract complete door type elevations, frame types, and hardware sets if shown.

Structure as valid JSON with this format:
{
  "DRAWING_METADATA": {
    "drawing_number": "A6.1",
    "title": "DOOR SCHEDULE"
  },
  "ARCHITECTURAL": {
    "DOOR_SCHEDULE": {
      "doors": [
        {
          "door_number": "101A",
          "location": "CORRIDOR TO OFFICE",
          "type": "A",
          "material": "WOOD",
          "size": {"width": "3'-0\"", "height": "7'-0\"", "thickness": "1 3/4\""},
          "fire_rating": "20 MIN",
          "frame_type": "HM",
          "hardware_set": "HW-1",
          "remarks": "CARD READER"
        },
        // Additional doors
      ],
      "door_types": [
        {
          "type_id": "A",
          "description": "FLUSH WOOD DOOR",
          "details": "SOLID CORE, PLAIN SLICED WHITE MAPLE VENEER"
        },
        // Additional door types
      ],
      "frame_types": [
        {
          "type_id": "HM",
          "description": "HOLLOW METAL FRAME",
          "details": "16 GA. WELDED FRAME, FACTORY PRIMED"
        },
        // Additional frame types
      ],
      "hardware_sets": [
        {
          "set_id": "HW-1",
          "components": [
            "HINGES: 3 EA 4.5\" x 4.5\" BALL BEARING",
            "LOCKSET: OFFICE FUNCTION, LEVER HANDLE",
            "CLOSER: SURFACE MOUNTED",
            "STOPS, SILENCERS, KICK PLATE"
          ]
        },
        // Additional hardware sets
      ]
    }
  }
}

CRITICAL: Door schedules define the properties of EVERY door opening in the building and directly impact life safety, security, and accessibility. COMPLETE extraction of ALL door information is essential for proper estimating, procurement, and installation.
""",
    aliases=["DOOR", "DOOR_SCHEDULE", "A_DOOR"],
)

# Register detail subtype
registry.register(
    "ARCHITECTURAL_DETAIL",
    """
You are analyzing architectural detail drawings. Extract ALL critical construction detail information with complete precision.

For EACH detail shown, capture:
1. Detail identifier (number, letter, or reference)
2. Detail name/title
3. Complete components shown in the detail:
   - ALL materials with specifications
   - Dimensions and thicknesses
   - Connection methods
   - Special requirements
4. Reference notes and callouts
5. Relevant sheet cross-references

Structure as a valid JSON object with this format:
{
  "DRAWING_METADATA": {
    "drawing_number": "A5.3",
    "title": "WALL SECTIONS AND DETAILS"
  },
  "ARCHITECTURAL": {
    "DETAILS": [
      {
        "detail_id": "1/A5.3",
        "title": "TYPICAL WINDOW HEAD DETAIL",
        "components": [
          {"element": "WINDOW FRAME", "material": "ALUMINUM", "notes": "SEE WINDOW SCHEDULE"},
          {"element": "FLASHING", "material": "24 GA. GALV. STEEL", "notes": "SLOPE TO EXTERIOR"},
          {"element": "SEALANT", "material": "SILICONE", "notes": "CONTINUOUS BEAD"},
          {"element": "SHEATHING", "material": "5/8\" GLASS-MAT GYPSUM", "notes": ""},
          {"element": "AIR BARRIER", "material": "FLUID-APPLIED MEMBRANE", "notes": "CONTINUOUS, LAP 2\" MIN."}
        ],
        "dimensions": [
          {"description": "HEAD SEALANT JOINT", "value": "1/4\""},
          {"description": "FLASHING OVERLAP", "value": "4\" MIN."}
        ],
        "reference_notes": [
          "PROVIDE CONTINUOUS SEALANT AT ALL JOINTS",
          "INSTALL AIR BARRIER CONTINUOUS WITH WALL AIR BARRIER"
        ],
        "cross_references": ["WINDOW SCHEDULE ON A6.2"]
      },
      // Additional details
    ]
  }
}

CRITICAL: Architectural details show the specific construction methodology that ensures building performance, weather-tightness, and durability. COMPLETE and ACCURATE extraction of ALL detail components and specifications is ESSENTIAL for proper construction and coordination.
""",
    aliases=["DETAIL", "SECTION", "A_DETAIL"],
)


# Keep backward compatibility with the decorator approach
@register_prompt("Architectural")
def default_architectural_prompt():
    """Default prompt for architectural drawings."""
    return registry.get("ARCHITECTURAL")


@register_prompt("Architectural", "ROOM")
def floorplan_prompt():
    """Prompt for architectural floor plans with room data."""
    return registry.get("ARCHITECTURAL_FLOORPLAN")


@register_prompt("Architectural", "CEILING")
def ceiling_prompt():
    """Prompt for reflected ceiling plans."""
    return registry.get("ARCHITECTURAL_REFLECTEDCEILING")


@register_prompt("Architectural", "WALL")
def wall_prompt():
    """Prompt for wall types."""
    return registry.get("ARCHITECTURAL_WALL")


@register_prompt("Architectural", "DOOR")
def door_prompt():
    """Prompt for door schedules."""
    return registry.get("ARCHITECTURAL_DOOR")


@register_prompt("Architectural", "DETAIL")
def detail_prompt():
    """Prompt for architectural details."""
    return registry.get("ARCHITECTURAL_DETAIL")
