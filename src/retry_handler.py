"""Exponential backoff retry decorator for transient API failures."""

import logging
import time
from functools import wraps

logger = logging.getLogger(__name__)


class TransientError(Exception):
    """Raised for errors that are safe to retry."""
    pass


def with_retry(max_attempts: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Decorator: retry with exponential backoff on TransientError.

    Usage:
        @with_retry(max_attempts=3)
        def call_api():
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except TransientError as e:
                    if attempt == max_attempts - 1:
                        logger.error(f"{func.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    delay = min(base_delay * (2 ** attempt), max_delay)
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
            return None
        return wrapper
    return decorator
