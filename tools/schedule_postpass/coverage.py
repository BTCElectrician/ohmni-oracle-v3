"""Coverage report generation."""
from __future__ import annotations

from typing import Any, Dict, List


def coverage_rows(
    sheet_doc: Dict[str, Any],
    facts: List[Dict[str, Any]],
    templates: List[Dict[str, Any]],
) -> List[List[str]]:
    """Generate coverage report rows for a sheet."""
    bucket: Dict[str, List[Dict[str, Any]]] = {}
    for fact in facts:
        bucket.setdefault(fact["schedule_type"], []).append(fact)

    rows: List[List[str]] = []
    sheet_number = sheet_doc.get("sheet_number") or "<unknown>"

    for stype, items in bucket.items():
        total = len(items)
        with_keys = sum(1 for item in items if item.get("key"))
        with_panel_circuit = sum(
            1
            for item in items
            if (item.get("key") or {}).get("panel") and (item.get("key") or {}).get("circuit")
        )
        with_voltage = sum(1 for item in items if (item.get("attributes") or {}).get("voltage") is not None)
        with_mca_mop = sum(
            1
            for item in items
            if (item.get("attributes") or {}).get("mca") is not None
            and (item.get("attributes") or {}).get("mop") is not None
        )
        rows.append(
            [
                sheet_number,
                stype,
                str(total),
                str(with_keys),
                str(with_panel_circuit),
                str(with_voltage),
                str(with_mca_mop),
                "",
                "",
                "",
            ]
        )

    if templates:
        total_templates = len(templates)
        last_mod = max((t.get("template_last_modified") for t in templates), default="N/A")
        signed_off = sum(1 for t in templates if t.get("template_status") == "signed_off")
        pct = f"{(signed_off / total_templates) * 100:.1f}%" if total_templates else "0%"
        rows.append(
            [
                sheet_number,
                "template",
                str(total_templates),
                "",
                "",
                "",
                "",
                last_mod,
                str(signed_off),
                pct,
            ]
        )

    return rows

