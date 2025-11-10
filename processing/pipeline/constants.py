"""
Constants used throughout the processing pipeline.
"""
import os

OCR_TOKEN_THRESHOLD = int(os.getenv("OCR_TOKEN_THRESHOLD", "5000"))
AVERAGE_CHARS_PER_TOKEN = float(os.getenv("OCR_AVG_CHARS_PER_TOKEN", "4"))

