#!/usr/bin/env python3
"""
Test script for various panel grid layouts.
Use this to validate detection of 3x2, 5x5, and other grid configurations.
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.minimal_panel_clip import panel_rects, _find_panel_anchors, _group_rows
import fitz
import argparse


def analyze_panel_layout(pdf_path: str, y_tolerance: float = None):
    """Analyze panel layout and suggest optimal parameters."""
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        return
        
    doc = fitz.open(pdf_path)
    
    for page_num, page in enumerate(doc):
        print(f"\n{'='*80}")
        print(f"PAGE {page_num + 1} ANALYSIS")
        print(f"{'='*80}")
        
        # First, find all anchors
        anchors = _find_panel_anchors(page)
        if not anchors:
            print("No panels found on this page")
            continue
            
        print(f"\nFound {len(anchors)} panel anchors:")
        for name, rect in anchors:
            print(f"  {name}: y={rect.y0:.1f}, x={rect.x0:.1f}")
        
        # Analyze Y spacing between panels
        y_positions = sorted(set(rect.y0 for _, rect in anchors))
        if len(y_positions) > 1:
            y_gaps = [y_positions[i+1] - y_positions[i] for i in range(len(y_positions)-1)]
            min_gap = min(y_gaps)
            avg_gap = sum(y_gaps) / len(y_gaps)
            print(f"\nY-spacing analysis:")
            print(f"  Unique Y positions: {len(y_positions)}")
            print(f"  Min gap between rows: {min_gap:.1f}")
            print(f"  Avg gap between rows: {avg_gap:.1f}")
            print(f"  Suggested y_tolerance: {min_gap * 0.8:.1f}")
        
        # Test different tolerances
        test_tolerances = [50, 100, 200, 300, 500] if y_tolerance is None else [y_tolerance]
        
        print(f"\nTesting different y_tolerance values:")
        for tol in test_tolerances:
            rows = _group_rows(anchors, y_tol=tol)
            print(f"\n  y_tolerance={tol}:")
            print(f"    Rows detected: {len(rows)}")
            for i, row in enumerate(rows):
                panels = [name for name, _ in row]
                print(f"    Row {i+1}: {panels} ({len(panels)} panels)")
                
        # Show the grid layout
        if y_tolerance:
            rows = _group_rows(anchors, y_tol=y_tolerance)
        else:
            # Auto-detect best tolerance
            rows = _group_rows(anchors, y_tol=min_gap * 0.8 if len(y_positions) > 1 else 300)
            
        print(f"\nDetected grid layout: {len(rows)}x{max(len(r) for r in rows)} "
              f"({sum(len(r) for r in rows)} total panels)")
        
        # Test panel rectangle extraction
        panels = panel_rects(page, y_tol=y_tolerance or (min_gap * 0.8 if len(y_positions) > 1 else 300))
        print(f"\nPanel rectangles:")
        for name, rect in panels:
            print(f"  {name}: {rect}")
    
    doc.close()


def test_specific_layout(pdf_path: str, expected_rows: int, expected_cols: int):
    """Test if a PDF matches expected grid layout."""
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        return False
        
    doc = fitz.open(pdf_path)
    success = True
    
    for page_num, page in enumerate(doc):
        anchors = _find_panel_anchors(page)
        if not anchors:
            continue
            
        # Try different tolerances to find the right grouping
        for tol in [50, 100, 200, 300, 500]:
            rows = _group_rows(anchors, y_tol=tol)
            if len(rows) == expected_rows:
                max_cols = max(len(r) for r in rows)
                if max_cols == expected_cols:
                    print(f"✓ Page {page_num + 1}: Correctly detected {expected_rows}x{expected_cols} grid with y_tol={tol}")
                    break
        else:
            print(f"✗ Page {page_num + 1}: Failed to detect {expected_rows}x{expected_cols} grid")
            success = False
    
    doc.close()
    return success


def main():
    parser = argparse.ArgumentParser(description='Test panel grid layout detection')
    parser.add_argument('pdf_path', help='Path to PDF file')
    parser.add_argument('--tolerance', '-t', type=float, help='Y tolerance for grouping')
    parser.add_argument('--expect', '-e', help='Expected layout (e.g., "3x2" or "5x5")')
    
    args = parser.parse_args()
    
    if args.expect:
        rows, cols = map(int, args.expect.split('x'))
        test_specific_layout(args.pdf_path, rows, cols)
    else:
        analyze_panel_layout(args.pdf_path, args.tolerance)


if __name__ == "__main__":
    if len(sys.argv) == 1:
        # Default test
        print("Usage: python test_panel_grid_layouts.py <pdf_path> [--tolerance N] [--expect RxC]")
        print("\nExample PDFs to test:")
        print("  - 2x2 grid: E5.00-PANEL-SCHEDULES-Rev.3")
        print("  - 3x2 grid: (need example)")
        print("  - 5x5 grid: (need example)")
    else:
        main()
