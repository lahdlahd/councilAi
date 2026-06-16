"""In-process async pub/sub hub.

A single backend process fans out events to every connected WebSocket client.
Each subscriber gets its own bounded queue; slow clients drop oldest messages
rather than back-pressuring the producer. Swap for Redis pub/sub if we ever run
multiple backend instances (the interface stays the same).
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from app.domain.events import WsEvent
from app.utils.logging import get_logger

log = get_logger("hub")


class Broadcaster:
    def __init__(self, max_queue: int = 256) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._max_queue = max_queue
        self._lock = asyncio.Lock()

    async def publish(self, event: WsEvent) -> None:
        # Serialize once; clients receive identical JSON.
        async with self._lock:
            subscribers = list(self._subscribers)
        for q in subscribers:
            if q.full():
                try:
                    q.get_nowait()  # drop oldest to make room
                except asyncio.QueueEmpty:
                    pass
            q.put_nowait(event)

    async def subscribe(self) -> AsyncIterator[WsEvent]:
        q: asyncio.Queue = asyncio.Queue(maxsize=self._max_queue)
        async with self._lock:
            self._subscribers.add(q)
        log.info("subscriber added (total=%d)", len(self._subscribers))
        try:
            while True:
                yield await q.get()
        finally:
            async with self._lock:
                self._subscribers.discard(q)
            log.info("subscriber removed (total=%d)", len(self._subscribers))

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)
