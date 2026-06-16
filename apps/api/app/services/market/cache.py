"""Async TTL cache with single-flight de-duplication.

Two protections against upstream (Bitget) rate limits:
  * TTL: a value is reused until it expires.
  * Single-flight: if many callers ask for the same cold key at once (e.g. 20 demo
    viewers loading the chart simultaneously), only ONE upstream fetch runs and the
    rest await its result — instead of 20 parallel calls.

`peek()` returns the last value regardless of freshness (used to enrich live ticks).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class AsyncTTLCache(Generic[T]):
    def __init__(self, ttl: float) -> None:
        self._ttl = ttl
        self._store: dict[str, tuple[float, T]] = {}
        self._inflight: dict[str, asyncio.Future[T]] = {}

    def peek(self, key: str) -> T | None:
        entry = self._store.get(key)
        return entry[1] if entry else None

    async def get_or_load(self, key: str, loader: Callable[[], Awaitable[T]]) -> T:
        now = time.monotonic()
        entry = self._store.get(key)
        if entry and entry[0] > now:
            return entry[1]

        # A fetch for this key is already running — ride along with it.
        existing = self._inflight.get(key)
        if existing is not None:
            return await existing

        loop = asyncio.get_running_loop()
        fut: asyncio.Future[T] = loop.create_future()
        self._inflight[key] = fut
        try:
            value = await loader()
            self._store[key] = (time.monotonic() + self._ttl, value)
            if not fut.done():
                fut.set_result(value)
            return value
        except Exception as exc:  # noqa: BLE001 - propagate to all awaiters
            if not fut.done():
                fut.set_exception(exc)
            raise
        finally:
            self._inflight.pop(key, None)
