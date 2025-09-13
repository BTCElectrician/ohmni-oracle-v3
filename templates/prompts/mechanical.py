"""
Mechanical prompt templates for construction drawing processing.
Consolidated with prompts from ai_service.py DRAWING_INSTRUCTIONS.
"""
from templates.prompt_registry import register_prompt, get_registry

# Get registry singleton
registry = get_registry()

# Register main mechanical prompt
registry.register(
    "MECHANICAL",
    """Extract ALL mechanical information with a simplified, comprehensive structure.

1. Create a straightforward JSON structure with these main categories:
   - "equipment": Object containing arrays of ALL mechanical equipment grouped by type
   - "systems": Information about ductwork, piping, and distribution systems
   - "notes": ALL notes, specifications, and requirements
   - "remarks": ALL remarks and numbered references

2. For ANY type of equipment (air handlers, fans, VAVs, pumps, etc.):
   - Group by equipment type using descriptive keys (airHandlers, exhaustFans, chillers, etc.)
   - Include EVERY specification field with its EXACT value - never round or approximate
   - Use camelCase field names based on original headers
   - Always include identification (tag/ID), manufacturer, model, and capacity information
   - Capture ALL performance data (CFM, tonnage, BTU, static pressure, etc.)
   - Include ALL electrical characteristics (voltage, phase, FLA, MCA, etc.)

3. For ALL mechanical information:
   - Preserve EXACT values - never round or approximate
   - Include units of measurement
   - Keep the structure flat and simple
   - Don't skip ANY information shown on the drawing

Example simplified structure:
{
  "equipment": {
    "airHandlingUnits": [
      {
        "id": "AHU-1",
        "manufacturer": "Trane",
        "model": "M-Series",
        "cfm": "10,000",
        // ALL other fields exactly as shown
      }
    ],
    "exhaustFans": [
      // ALL fan data with EVERY field
    ]
  },
  "notes": [
    // ALL notes and specifications
  ],
  "remarks": [
    // ALL remarks and references
  ]
}

CRITICAL: Engineers need EVERY mechanical element and specification value EXACTLY as shown - complete accuracy is essential for proper system design, ordering, and installation.
\n+IMPORTANT: Return your final answer as a single, valid JSON object. Use double quotes for all keys and string values. Do not include explanations or markdown; output only the JSON.
""",
    aliases=["M", "MECH"],
)

# Register equipment schedule subtype
registry.register(
    "MECHANICAL_SCHEDULE",
    """
You are a mechanical engineer analyzing equipment schedules. Extract ALL equipment data with complete precision.

For EACH equipment item (air handlers, fans, VAVs, pumps, etc.) capture EVERY specification field with its EXACT value:

1. Required for ALL equipment:
   - Tag/ID/Mark: Exact equipment identifier 
   - Service/Location: Where the equipment serves or is located
   - Manufacturer: Make/manufacturer name
   - Model: Complete model number (preserve ALL alphanumerics)
   - Capacities: ALL performance metrics (CFM, cooling tons, heating MBH, etc.)
   - Physical dimensions: Size and weight
   - Motor/electrical data: HP, voltage, phase, FLA, MCA
   - Options/accessories: ALL specified components

2. Schedule-specific fields:
   - AHUs: Supply/return CFM, static pressure, filter types, coil data
   - Fans: CFM, static pressure, drive type, wheel type
   - VAVs: Min/max CFM, heating capacity, control type
   - Pumps: GPM, head, impeller size, efficiency
   - Diffusers: Neck size, throw distance, noise criteria

3. ALL notes and references:
   - Equipment-specific notes
   - General schedule notes
   - Specification references

Structure as a valid JSON with this format:
{
  "DRAWING_METADATA": {
    "drawing_number": "M5.1",
    "title": "MECHANICAL SCHEDULES"
  },
  "MECHANICAL": {
    "EQUIPMENT_SCHEDULES": {
      "AHU_SCHEDULE": [
        {
          "mark": "AHU-1",
          "location": "Mechanical Room 101",
          "service": "First Floor Offices",
          "manufacturer": "Trane",
          "model": "M-Series CSAA012",
          "supply_cfm": "10,000",
          "external_static_pressure": "2.5\" W.C.",
          "cooling_capacity": "40 tons",
          "cooling_coil_rows": "6",
          "heating_capacity": "450 MBH",
          "filter_type": "MERV 13",
          "electrical": "460V/3Ph/60Hz",
          "motor_hp": "15",
          "fla": "21.0",
          "mca": "26.3",
          "dimensions": "120\"L x 88\"W x 78\"H",
          "weight": "2,800 lbs",
          "remarks": ["Provide BACnet interface", "Provide low ambient control"]
        },
        // Additional units
      ],
      "EXHAUST_FAN_SCHEDULE": [
        {
          "mark": "EF-1",
          "location": "Roof",
          "service": "Restrooms",
          "manufacturer": "Greenheck",
          "model": "CUE-095-VG",
          "cfm": "1,200",
          "esp": "0.75\" W.C.",
          "rpm": "1,725",
          "motor_hp": "0.5",
          "voltage": "120/1/60",
          "drive_type": "Direct",
          "weight": "85 lbs",
          "remarks": ["Provide disconnect switch", "Provide gravity backdraft damper"]
        },
        // Additional fans
      ],
      // Additional schedules (VAV_SCHEDULE, PUMP_SCHEDULE, etc.)
    },
    "general_notes": [
      "ALL EQUIPMENT TO BE INSTALLED PER MANUFACTURER'S REQUIREMENTS",
      "COORDINATE EXACT LOCATIONS WITH ARCHITECTURAL AND STRUCTURAL DRAWINGS"
    ]
  }
}

CRITICAL: Mechanical equipment schedules contain the EXACT specifications needed for procurement and installation. Values must NEVER be rounded or approximated, and model numbers must include ALL characters. Missing or inaccurate information can lead to improper equipment selection, coordination issues, and system failures.
""",
    aliases=["EQUIPMENT", "EQUIP", "M_SCHEDULE"],
)

# Register ventilation subtype
registry.register(
    "MECHANICAL_VENTILATION",
    """
You are a mechanical HVAC specialist analyzing a ventilation/ductwork drawing. Extract ALL relevant information with complete precision.

Create a comprehensive structure capturing:

1. ALL duct runs with:
   - Size dimensions (width x height or diameter)
   - CFM/airflow values when shown
   - Duct material and insulation requirements
   - Elevation/height information
   - Special construction requirements

2. ALL air devices:
   - Type and model
   - Size and connection details
   - CFM/airflow values
   - Mounting details
   - Special requirements

3. ALL mechanical equipment shown:
   - Location and identification
   - Connection details
   - Space requirements
   - Access requirements

4. Control information:
   - Thermostat/sensor locations
   - Zoning details
   - Control sequences shown

5. Coordination requirements:
   - Clearances
   - Access panels
   - Fire/smoke dampers
   - Seismic bracing

Structure as a valid JSON object with this format:
{
  "DRAWING_METADATA": {
    "drawing_number": "M2.1",
    "title": "FIRST FLOOR HVAC PLAN"
  },
  "MECHANICAL": {
    "VENTILATION": {
      "duct_runs": [
        {
          "id": "SA-1",
          "from": "AHU-1",
          "to": "First Floor Main Trunk",
          "size": "30\" x 14\"",
          "cfm": "10,000",
          "material": "Galvanized Steel",
          "insulation": "1.5\" R6 External",
          "elevation": "10'-0\" AFF to bottom",
          "notes": "Provide flexible connection at AHU"
        },
        // Additional duct runs
      ],
      "air_devices": [
        {
          "type": "Supply Diffuser",
          "mark": "SD-1",
          "model": "Titus TMS-AA",
          "size": "24\" x 24\"",
          "neck_size": "12\"",
          "cfm": "400",
          "location": "Room 101",
          "mounting": "Lay-in ceiling grid",
          "notes": "Provide opposed blade damper"
        },
        // Additional air devices
      ],
      "equipment": [
        {
          "id": "AHU-1",
          "type": "Air Handling Unit",
          "location": "Mechanical Room 101",
          "connections": {
            "supply": "30\" x 14\" UP",
            "return": "32\" x 16\" DOWN",
            "outside_air": "24\" x 12\" THROUGH WALL"
          },
          "clearance": "36\" minimum all sides for maintenance",
          "notes": "Provide housekeeping pad per detail 3/M5.1"
        },
        // Additional equipment
      ],
      "controls": [
        {
          "device": "Thermostat",
          "id": "T-101",
          "location": "Room 101, North Wall",
          "serves": "VAV-1",
          "mounting_height": "48\" AFF",
          "notes": "Verify exact location with architectural elevations"
        },
        // Additional control devices
      ],
      "coordination_items": [
        {
          "item": "Fire/Smoke Damper",
          "id": "FSD-1",
          "location": "Corridor 100, Station 1+25",
          "size": "24\" x 16\"",
          "access": "Provide 24\" x 24\" ceiling access panel",
          "notes": "Coordinate with fire alarm contractor"
        },
        // Additional coordination items
      ]
    },
    "general_notes": [
      "ALL DUCTWORK TO BE CONSTRUCTED PER SMACNA STANDARDS",
      "INSULATE ALL SUPPLY AND OUTDOOR AIR DUCTWORK WITH 1.5\" EXTERNAL INSULATION WITH VAPOR BARRIER"
    ]
  }
}

CRITICAL: Ventilation drawings establish the EXACT routing, sizing, and air distribution essential for proper system operation. Precise extraction of ALL duct sizes, air device specifications, and coordination requirements is CRITICAL for proper installation and system performance. Conflicting or missing information can cause coordination issues with other trades.
""",
    aliases=["VENTILATION", "DUCTWORK", "M_VENT"],
)

# Register piping subtype
registry.register(
    "MECHANICAL_PIPING",
    """
You are a mechanical piping specialist analyzing a piping system drawing. Extract ALL piping-related information with complete precision.

Create a comprehensive structure capturing:

1. ALL piping systems with details:
   - System type (chilled water, hot water, steam, refrigerant, etc.)
   - Pipe sizes
   - Flow rates/GPM when shown
   - Material specifications
   - Insulation requirements
   - Elevation information
   - Special installation requirements

2. ALL valves and specialties:
   - Type and function
   - Size and connection details
   - Pressure ratings
   - Special requirements

3. ALL mechanical equipment connections:
   - Connection sizes
   - Flow requirements
   - Special connection details
   - Access requirements

4. Control components:
   - Control valves
   - Sensors and gauges
   - Flow meters
   - Special control requirements

5. Coordination requirements:
   - Clearances
   - Access points
   - Seismic bracing
   - Expansion provisions

Structure as a valid JSON object with this format:
{
  "DRAWING_METADATA": {
    "drawing_number": "M3.1",
    "title": "MECHANICAL PIPING PLAN"
  },
  "MECHANICAL": {
    "PIPING": {
      "systems": [
        {
          "system_name": "Chilled Water Supply",
          "abbreviation": "CHWS",
          "material": "Schedule 40 Steel",
          "insulation": "1\" Closed Cell with Vapor Barrier",
          "segments": [
            {
              "from": "Chiller",
              "to": "AHU-1",
              "size": "4\"",
              "flow": "240 GPM",
              "elevation": "8'-0\" AFF to centerline",
              "notes": "Route above corridor ceiling"
            },
            // Additional pipe segments
          ]
        },
        // Additional piping systems
      ],
      "valves_and_specialties": [
        {
          "type": "Butterfly Valve",
          "symbol": "BFV-1",
          "size": "4\"",
          "location": "CHWS to AHU-1",
          "pressure_rating": "150 PSI",
          "notes": "Provide chain operator if mounted over 7' AFF"
        },
        // Additional valves and specialties
      ],
      "equipment_connections": [
        {
          "equipment_id": "AHU-1",
          "connections": [
            {
              "service": "CHWS",
              "size": "3\"",
              "flow": "180 GPM",
              "notes": "Provide flexible connection and thermometer"
            },
            {
              "service": "CHWR",
              "size": "3\"",
              "flow": "180 GPM",
              "notes": "Provide flexible connection and pressure gauge"
            }
          ],
          "notes": "Provide isolation valves at all connections"
        },
        // Additional equipment connections
      ],
      "control_components": [
        {
          "type": "Control Valve",
          "id": "CV-1",
          "size": "3\"",
          "service": "CHWS to AHU-1",
          "characteristics": "Equal percentage",
          "action": "Normally closed",
          "signal": "0-10V modulating",
          "notes": "Provided by controls contractor"
        },
        // Additional control components
      ],
      "coordination_items": [
        {
          "item": "Pipe Anchors",
          "location": "CHWS at Column Line C/5",
          "notes": "Coordinate anchor detail with structural engineer"
        },
        // Additional coordination items
      ]
    },
    "general_notes": [
      "ALL PIPING TO BE INSTALLED PER APPLICABLE CODES AND STANDARDS",
      "PROVIDE ISOLATION VALVES AT ALL EQUIPMENT CONNECTIONS",
      "SLOPE ALL PIPING TO DRAIN POINTS AT MINIMUM 1/4\" PER 10'"
    ]
  }
}

CRITICAL: Piping drawings establish the EXACT routing, sizing, and distribution essential for proper mechanical system operation. Precise extraction of ALL pipe sizes, connections, valve requirements, and coordination details is ESSENTIAL for proper installation and system performance. Errors in piping configuration can cause system failures and coordination conflicts with other trades.
""",
    aliases=["PIPING", "PIPE", "M_PIPE"],
)


# Keep backward compatibility with the decorator approach
@register_prompt("Mechanical")
def default_mechanical_prompt():
    """Default prompt for mechanical drawings."""
    return registry.get("MECHANICAL")


@register_prompt("Mechanical", "EQUIPMENT")
def equipment_schedule_prompt():
    """Prompt for mechanical equipment schedules."""
    return registry.get("MECHANICAL_SCHEDULE")


@register_prompt("Mechanical", "VENTILATION")
def ventilation_prompt():
    """Prompt for ventilation drawings."""
    return registry.get("MECHANICAL_VENTILATION")


@register_prompt("Mechanical", "PIPING")
def piping_prompt():
    """Prompt for piping drawings."""
    return registry.get("MECHANICAL_PIPING")
