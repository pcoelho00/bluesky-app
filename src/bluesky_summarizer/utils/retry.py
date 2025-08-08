"""Simple retry / backoff utilities for external API robustness."""

from __future__ import annotations
import time
import logging
from functools import wraps
from typing import Callable, Type, Tuple

logger = logging.getLogger(__name__)


def retry(
    *,
    exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    attempts: int = 3,
    base_delay: float = 0.5,
    factor: float = 2.0,
    jitter: float = 0.1,
) -> Callable:
    """Retry decorator with exponential backoff and jitter.

    Args:
        exceptions: Exception types to catch.
        attempts: Total attempts (initial + retries).
        base_delay: Initial sleep seconds.
        factor: Exponential multiplier.
        jitter: Added random jitter up to this value.
    """
    import random

    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            delay = base_delay
            last_exc = None
            for attempt in range(1, attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except exceptions as exc:  # noqa: PERF203 acceptable here
                    last_exc = exc
                    if attempt == attempts:
                        logger.error(
                            "Retry failed after %s attempts for %s: %s",
                            attempts,
                            fn.__name__,
                            exc,
                        )
                        raise
                    sleep_for = delay + random.uniform(0, jitter)
                    logger.warning(
                        "Attempt %s/%s failed for %s (%s). Retrying in %.2fs",
                        attempt,
                        attempts,
                        fn.__name__,
                        exc,
                        sleep_for,
                    )
                    time.sleep(sleep_for)
                    delay *= factor
            raise last_exc  # type: ignore[misc]

        return wrapper

    return decorator
