"""Architectural schedule fallback iterator (wall/door/ceiling/finish)."""
from __future__ import annotations

from typing import Any, Dict, Generator, Tuple

from .common import ci_get, first_non_empty


def iter_arch_rows(raw_json: Dict[str, Any]) -> Generator[Tuple[str, Dict[str, Any]], None, None]:
    """
    Yield (schedule_type, row) tuples for Architectural schedules from nested sources.

    Supports:
      - Wall/Partition: WALL_TYPES, PARTITION_TYPES, WALL_PARTITIONS, WALL_SCHEDULE, PARTITION_SCHEDULE
      - Door: DOOR_SCHEDULE, DOORS, DOOR_SCHEDULES
      - Ceiling: CEILING_SCHEDULE, RCP_SCHEDULE, CEILINGS
      - Finish: FINISH_SCHEDULE, FINISHES

    Returns:
        Generator of (schedule_type, row_dict) tuples where schedule_type is one of:
        'wall_partition', 'door', 'ceiling', 'finish'
    """
    if not isinstance(raw_json, dict):
        return

    arch = None
    for k, v in raw_json.items():
        if isinstance(k, str) and k.lower() in ("architectural", "arch"):
            arch = v
            break
    if not isinstance(arch, dict):
        return

    # Wall / Partition schedules
    for key in ("WALL_TYPES", "PARTITION_TYPES", "WALL_PARTITIONS", "WALL_SCHEDULE", "PARTITION_SCHEDULE"):
        rows = ci_get(arch, key)
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict):
                    wt = first_non_empty(
                        ci_get(r, "wall_type"),
                        ci_get(r, "partition_type"),
                        ci_get(r, "type"),
                    )
                    if wt:
                        rr = dict(r)
                        rr.setdefault("wall_type", wt)
                        yield ("wall_partition", rr)

    # Door schedule
    for key in ("DOOR_SCHEDULE", "DOORS", "DOOR_SCHEDULES"):
        rows = ci_get(arch, key)
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict):
                    dn = first_non_empty(
                        ci_get(r, "door_number"),
                        ci_get(r, "mark"),
                        ci_get(r, "door"),
                        ci_get(r, "id"),
                    )
                    if dn:
                        yield ("door", r)

    # Ceiling schedule
    for key in ("CEILING_SCHEDULE", "RCP_SCHEDULE", "CEILINGS"):
        rows = ci_get(arch, key)
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict):
                    ct = first_non_empty(
                        ci_get(r, "ceiling_type"),
                        ci_get(r, "type"),
                    )
                    if ct:
                        rr = dict(r)
                        rr.setdefault("ceiling_type", ct)
                        yield ("ceiling", rr)

    # Finish schedule (often by room/space)
    for key in ("FINISH_SCHEDULE", "FINISHES"):
        rows = ci_get(arch, key)
        if isinstance(rows, list):
            for r in rows:
                if isinstance(r, dict):
                    space = first_non_empty(
                        ci_get(r, "space"),
                        ci_get(r, "room"),
                        ci_get(r, "area"),
                        ci_get(r, "name"),
                    )
                    if space:
                        yield ("finish", r)

