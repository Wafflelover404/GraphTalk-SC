"""
Timing utilities for performance monitoring and debugging
"""
import time
import logging
import functools
from contextlib import contextmanager
from typing import Any, Dict, Optional, Callable
import threading

logger = logging.getLogger(__name__)

class Timer:
    """Simple timer class for tracking execution time"""

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.start_time = None
        self.end_time = None
        self.logger = logger or logging.getLogger(__name__)

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = time.time()
        elapsed_ms = (self.end_time - self.start_time) * 1000
        self.logger.info(f"[{self.name}] completed in {elapsed_ms:.2f}ms")

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds"""
        if self.start_time is None:
            return 0.0
        end_time = self.end_time if self.end_time else time.time()
        return (end_time - self.start_time) * 1000

    def log_elapsed(self, extra_info: str = ""):
        """Log the elapsed time with optional extra info"""
        elapsed_ms = self.elapsed_ms
        message = f"[{self.name}] took {elapsed_ms:.2f}ms"
        if extra_info:
            message += f" - {extra_info}"
        self.logger.info(message)

def time_function(func: Callable) -> Callable:
    """Decorator to time function execution"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        timer_name = f"{func.__module__}.{func.__qualname__}"
        with Timer(timer_name):
            return func(*args, **kwargs)
    return wrapper

def time_function_with_logger(logger: logging.Logger) -> Callable:
    """Decorator factory to time function execution with custom logger"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            timer_name = f"{func.__module__}.{func.__qualname__}"
            with Timer(timer_name, logger):
                return func(*args, **kwargs)
        return wrapper
    return decorator

@contextmanager
def time_block(name: str, logger: Optional[logging.Logger] = None):
    """Context manager for timing code blocks"""
    timer = Timer(name, logger)
    timer.__enter__()
    try:
        yield timer
    finally:
        timer.__exit__(None, None, None)

class PerformanceTracker:
    """Track performance metrics across multiple operations"""

    def __init__(self, name: str, logger: Optional[logging.Logger] = None):
        self.name = name
        self.logger = logger or logging.getLogger(__name__)
        self.metrics: Dict[str, float] = {}
        self.start_times: Dict[str, float] = {}

    def start_operation(self, operation_name: str):
        """Start timing an operation"""
        self.start_times[operation_name] = time.time()

    def end_operation(self, operation_name: str, extra_info: str = ""):
        """End timing an operation and log the result"""
        if operation_name not in self.start_times:
            self.logger.warning(f"Operation {operation_name} was not started")
            return

        elapsed_ms = (time.time() - self.start_times[operation_name]) * 1000
        self.metrics[operation_name] = elapsed_ms

        message = f"[{self.name}] {operation_name}: {elapsed_ms:.2f}ms"
        if extra_info:
            message += f" - {extra_info}"
        self.logger.info(message)

    def get_metric(self, operation_name: str) -> float:
        """Get the timing for a specific operation"""
        return self.metrics.get(operation_name, 0.0)

    def log_summary(self):
        """Log a summary of all operations"""
        if not self.metrics:
            return

        total_time = sum(self.metrics.values())
        self.logger.info(f"[{self.name}] Total time: {total_time:.2f}ms")

        # Sort operations by time (slowest first)
        sorted_metrics = sorted(self.metrics.items(), key=lambda x: x[1], reverse=True)

        for operation, time_ms in sorted_metrics:
            percentage = (time_ms / total_time) * 100 if total_time > 0 else 0
            self.logger.info(f"  - {operation}: {time_ms:.2f}ms ({percentage:.1f}%)")

# Thread-local storage for performance trackers
_thread_local = threading.local()

def get_current_tracker() -> Optional[PerformanceTracker]:
    """Get the current performance tracker for this thread"""
    return getattr(_thread_local, 'current_tracker', None)

def set_current_tracker(tracker: PerformanceTracker):
    """Set the current performance tracker for this thread"""
    _thread_local.current_tracker = tracker

@contextmanager
def track_performance(name: str, logger: Optional[logging.Logger] = None):
    """Context manager that creates a performance tracker"""
    tracker = PerformanceTracker(name, logger)
    set_current_tracker(tracker)
    try:
        yield tracker
    finally:
        tracker.log_summary()
        set_current_tracker(None)
