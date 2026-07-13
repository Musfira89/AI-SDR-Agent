"""Small shared utilities.

`async_retry` is the classic production pattern for calling rate-limited APIs:
if the call fails, wait (exponentially longer each time, plus a little random
"jitter" so parallel tasks don't all retry at the same instant) and try again.
"""

from __future__ import annotations

import asyncio
import functools
import random
from collections.abc import Callable


def async_retry(max_attempts: int = 3, base_delay: float = 1.5) -> Callable:
    """Retry an async function with exponential backoff + jitter."""

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            last_error: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:  # noqa: BLE001 — retry any transient failure
                    last_error = exc
                    if attempt == max_attempts:
                        break
                    delay = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                    await asyncio.sleep(delay)
            raise last_error  # type: ignore[misc]

        return wrapper

    return decorator
