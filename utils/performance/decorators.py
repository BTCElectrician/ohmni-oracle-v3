"""
Decorators and context managers for timing operations.
"""
import time
import asyncio
import os
from typing import Optional, Tuple, Any
from functools import wraps
from contextlib import contextmanager

from utils.performance.tracker import get_tracker


def _extract_context(args: tuple, kwargs: dict) -> Tuple[Optional[str], Optional[str], dict]:
    """
    Extract file path and drawing type from function arguments.
    
    Args:
        args: Positional arguments
        kwargs: Keyword arguments
        
    Returns:
        Tuple of (file_path, drawing_type, extra_context)
    """
    file_path = None
    drawing_type = None
    extra = {}
    
    # Step 1: Check if self (first arg) has a pdf_path attribute
    if args and hasattr(args[0], 'pdf_path'):
        candidate = getattr(args[0], 'pdf_path', None)
        if isinstance(candidate, str) and candidate.lower().endswith('.pdf'):
            file_path = candidate
    
    # Step 2: Check positional arguments for PDF paths
    if not file_path:
        for arg in args:
            if isinstance(arg, str) and arg.lower().endswith('.pdf'):
                file_path = arg
                break
    
    # Step 3: Check keyword arguments for common file path parameter names
    if not file_path:
        for param_name in ['pdf_path', 'file_path', 'filepath', 'path']:
            kw_file_path = kwargs.get(param_name)
            if isinstance(kw_file_path, str) and kw_file_path.lower().endswith('.pdf'):
                file_path = kw_file_path
                break
    
    # Step 4: If we found a file path, derive the drawing type
    if file_path:
        from utils.drawing_utils import detect_drawing_info
        detected_type, _ = detect_drawing_info(file_path)
        drawing_type = detected_type
    
    return file_path, drawing_type, extra


def time_operation(category: str):
    """
    Decorator to time an operation and add it to the tracker.
    
    Automatically extracts file path and drawing type from function arguments,
    checking both positional and keyword arguments.
    
    Args:
        category: Category name for the metric (e.g., 'extraction', 'ai_processing')
    
    Returns:
        Decorated function that tracks execution time
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            file_path, drawing_type, extra = _extract_context(args, kwargs)
            
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                tracker = get_tracker()
                
                # Add debug info when file_path not found
                if not file_path:
                    extra['func_name'] = func.__name__
                
                tracker.add_metric_with_context(
                    category=category,
                    duration=duration,
                    file_path=file_path,
                    drawing_type=drawing_type,
                    **extra
                )

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            file_path, drawing_type, extra = _extract_context(args, kwargs)
            
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration = time.time() - start_time
                tracker = get_tracker()
                
                # Add debug info when file_path not found
                if not file_path:
                    extra['func_name'] = func.__name__
                
                tracker.add_metric_with_context(
                    category=category,
                    duration=duration,
                    file_path=file_path,
                    drawing_type=drawing_type,
                    **extra
                )

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


@contextmanager
def time_operation_context(category: str, file_path: Optional[str] = None, drawing_type: Optional[str] = None):
    """
    Context manager for timing operations with explicit context.

    Args:
        category: Category of the operation
        file_path: Optional path to the file being processed
        drawing_type: Optional type of drawing
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration = time.time() - start_time
        tracker = get_tracker()
        tracker.add_metric_with_context(
            category=category,
            duration=duration,
            file_path=file_path,
            drawing_type=drawing_type
        )

