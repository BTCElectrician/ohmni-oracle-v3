"""
Test script to verify the enhanced performance tracking functionality.
"""
import logging
import time
from utils.performance_utils import time_operation_context, get_tracker

# Configure logging
logging.basicConfig(level=logging.INFO)

# Set up test variables
pdf_path = "test.pdf"
drawing_type = "Architectural"

# Get the tracker
tracker = get_tracker()

# Test API metrics
print("Testing API metrics...")
tracker.add_api_metric(2.5)
tracker.add_api_metric(3.7)

# Test the context manager
print("Testing time_operation_context...")
with time_operation_context("normalization"):
    print("- Sleeping for 1 second inside normalization context...")
    time.sleep(1)

with time_operation_context("json_parsing"):
    print("- Sleeping for 0.5 seconds inside json_parsing context...")
    time.sleep(0.5)

with time_operation_context("extraction_pdf_read"):
    print("- Sleeping for 0.8 seconds inside extraction_pdf_read context...")
    time.sleep(0.8)

# Add a metric for total_processing to calculate API percentage
tracker.add_metric("total_processing", pdf_path, drawing_type, 10.0)

# Log the performance report
print("\nPerformance Report:")
tracker.log_report()

print("\nTest completed successfully!")
