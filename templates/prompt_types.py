from enum import Enum


class DrawingCategory(Enum):
    """Main drawing categories."""

    ARCHITECTURAL = "Architectural"
    ELECTRICAL = "Electrical"
    MECHANICAL = "Mechanical"
    PLUMBING = "Plumbing"
    GENERAL = "General"
    SPECIFICATIONS = "Specifications"


class ArchitecturalSubtype(Enum):
    """Architectural drawing subtypes."""

    ROOM = "ROOM"
    CEILING = "CEILING"
    WALL = "WALL"
    DOOR = "DOOR"
    DETAIL = "DETAIL"
    DEFAULT = "DEFAULT"


class ElectricalSubtype(Enum):
    """Electrical drawing subtypes."""

    PANEL_SCHEDULE = "PANEL_SCHEDULE"
    LIGHTING = "LIGHTING"
    POWER = "POWER"
    FIREALARM = "FIREALARM"
    TECHNOLOGY = "TECHNOLOGY"
    SPEC = "SPEC"
    RISER_ONE_LINE = "RISER_ONE_LINE"
    DEFAULT = "DEFAULT"


class MechanicalSubtype(Enum):
    """Mechanical drawing subtypes."""

    EQUIPMENT = "EQUIPMENT"
    VENTILATION = "VENTILATION"
    PIPING = "PIPING"
    DEFAULT = "DEFAULT"


class PlumbingSubtype(Enum):
    """Plumbing drawing subtypes."""

    FIXTURE = "FIXTURE"
    EQUIPMENT = "EQUIPMENT"
    PIPE = "PIPE"
    DEFAULT = "DEFAULT"
