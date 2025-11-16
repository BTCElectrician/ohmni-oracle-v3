#!/usr/bin/env python3
"""
Test script to verify panel post-pass on E5.00 drawing.

This script:
1. Extracts text from the E5.00 PDF
2. Processes it through the pipeline (or uses existing structured JSON)
3. Runs the post-pass
4. Verifies that even circuits are filled in
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from openai import AsyncOpenAI
from config.settings import OPENAI_API_KEY
from services.extraction.electrical import ElectricalExtractor
from tools.schedule_postpass.panel_text_postpass import (
    fill_panels_from_sheet_text,
    is_panel_schedule_sheet,
)
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_postpass_on_e500():
    """Test the post-pass on E5.00 drawing."""
    # Paths
    pdf_path = "json-pdf/E5.00-PANEL-SCHEDULES-Rev.3 copy.pdf"
    existing_json_path = "/Users/collin/Desktop/ElecShuffleTest/processed/Electrical/e5-00-panel-schedules-copy/E5.00-PANEL-SCHEDULES-Rev.3 copy_structured.json"
    
    if not os.path.exists(pdf_path):
        logger.error(f"PDF not found: {pdf_path}")
        return False
    
    logger.info(f"Extracting text from {pdf_path}...")
    
    # Extract text using ElectricalExtractor
    extractor = ElectricalExtractor(logger=logger)
    extraction_result = await extractor.extract(pdf_path)
    
    if not extraction_result.success:
        logger.error(f"Extraction failed: {extraction_result.error}")
        return False
    
    sheet_text = extraction_result.raw_text
    logger.info(f"Extracted {len(sheet_text)} characters of text")
    
    # Check if we have Panel: markers
    panel_markers = sheet_text.count("Panel:")
    logger.info(f"Found {panel_markers} 'Panel:' markers in text")
    
    # Load existing structured JSON (or create minimal one)
    if os.path.exists(existing_json_path):
        logger.info(f"Loading existing structured JSON from {existing_json_path}...")
        with open(existing_json_path, 'r') as f:
            sheet_json = json.load(f)
    else:
        logger.warning("No existing JSON found, creating minimal structure...")
        sheet_json = {
            "ELECTRICAL": {
                "panels": []
            }
        }
    
    # Check if it's a panel schedule
    if not is_panel_schedule_sheet(sheet_json):
        logger.warning("Sheet JSON doesn't appear to be a panel schedule")
        return False
    
    # Count circuits before
    electrical = sheet_json.get("ELECTRICAL", {})
    panels = electrical.get("panels", [])
    before_counts = {}
    for panel in panels:
        panel_name = panel.get("panel_name") or panel.get("panel_id") or "Unknown"
        circuits = panel.get("circuits", [])
        count = len([c for c in circuits if isinstance(c, dict) and c.get("circuit_number") is not None])
        before_counts[panel_name] = count
        logger.info(f"Before: {panel_name} has {count} circuits")
    
    # Run post-pass
    logger.info("Running panel post-pass...")
    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    
    try:
        result_json = await fill_panels_from_sheet_text(
            sheet_json=sheet_json,
            sheet_text=sheet_text,
            client=client,
        )
        
        # Count circuits after
        result_electrical = result_json.get("ELECTRICAL", {})
        result_panels = result_electrical.get("panels", [])
        after_counts = {}
        for panel in result_panels:
            panel_name = panel.get("panel_name") or panel.get("panel_id") or "Unknown"
            circuits = panel.get("circuits", [])
            count = len([c for c in circuits if isinstance(c, dict) and c.get("circuit_number") is not None])
            after_counts[panel_name] = count
            logger.info(f"After: {panel_name} has {count} circuits")
        
        # Compare
        logger.info("\n=== Results ===")
        for panel_name in set(list(before_counts.keys()) + list(after_counts.keys())):
            before = before_counts.get(panel_name, 0)
            after = after_counts.get(panel_name, 0)
            diff = after - before
            status = "✓" if diff > 0 else "⚠️"
            logger.info(f"{status} {panel_name}: {before} → {after} circuits (+{diff})")
        
        # Check for even circuits
        logger.info("\n=== Even Circuit Check ===")
        for panel in result_panels:
            panel_name = panel.get("panel_name") or panel.get("panel_id") or "Unknown"
            circuits = panel.get("circuits", [])
            circuit_numbers = [c.get("circuit_number") for c in circuits if isinstance(c, dict) and c.get("circuit_number") is not None]
            if circuit_numbers:
                max_circuit = max(circuit_numbers)
                evens = [i for i in range(2, max_circuit + 1, 2) if i in circuit_numbers]
                odds = [i for i in range(1, max_circuit + 1, 2) if i in circuit_numbers]
                logger.info(f"{panel_name}: {len(evens)} even circuits, {len(odds)} odd circuits (max: {max_circuit})")
                if len(evens) > 0:
                    logger.info(f"  ✓ Even circuits present: {evens[:5]}{'...' if len(evens) > 5 else ''}")
        
        return True
        
    except Exception as e:
        logger.error(f"Post-pass failed: {e}", exc_info=True)
        return False


if __name__ == "__main__":
    success = asyncio.run(test_postpass_on_e500())
    sys.exit(0 if success else 1)

