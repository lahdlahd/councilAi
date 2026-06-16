"""Async exponential backoff helper for flaky upstream calls."""

from __future__ import annotations

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import TypeVar

from app.utils.logging import get_logger

T = TypeVar("T")
log = get_logger("retry")


async def with_retry(
    fn: Callable[[], Awaitable[T]],
    *,
    attempts: int = 3,
    base_delay: float = 0.4,
    max_delay: float = 4.0,
    label: str = "operation",
) -> T:
    """Run `fn`, retrying on any exception with jittered exponential backoff.

    Re-raises the last exception if every attempt fails.
    """
    last_exc: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await fn()
        except Exception as exc:  # noqa: BLE001 - we deliberately retry broadly
            last_exc = exc
            if attempt == attempts:
                break
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            delay += random.uniform(0, delay * 0.25)  # jitter
            log.warning(
                "%s failed (attempt %d/%d): %s — retrying in %.2fs",
                label, attempt, attempts, exc, delay,
            )
            await asyncio.sleep(delay)
    assert last_exc is not None
    raise last_exc
