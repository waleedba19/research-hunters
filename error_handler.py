"""
error_handler.py — Exponential backoff + retry for transient network/API errors.
"""
import time
import functools
from typing import Callable, Tuple, Type
from logger import get_logger

log = get_logger("error_handler")

RETRYABLE_EXCEPTIONS: Tuple[Type[BaseException], ...] = (
    ConnectionError,
    TimeoutError,
    OSError,
)


def retry(
    max_attempts: int = 3,
    base_delay: float = 1.5,
    backoff: float = 2.0,
    exceptions: Tuple[Type[BaseException], ...] = RETRYABLE_EXCEPTIONS,
) -> Callable:
    """Decorator: retry on transient errors with exponential backoff."""

    def deco(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            delay = base_delay
            last_exc = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as e:
                    last_exc = e
                    if attempt == max_attempts:
                        log.error(f"{fn.__name__} failed after {max_attempts} attempts: {e}")
                        raise
                    log.warning(
                        f"{fn.__name__} attempt {attempt}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    delay *= backoff
            raise last_exc  # unreachable

        return wrapped

    return deco
