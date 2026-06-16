"""Cadence controller — paces text output so streaming reads as deliberate.

Decouples reasoning speed from visual rhythm (the key demo decision): real LLM
tokens arrive in bursts; offline text arrives all at once. Both are normalized to
a steady word-by-word stream at ~`tokens_per_sec`, which is what makes the council
chamber feel like watching someone think rather than a paste.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator

# Split into words while keeping trailing whitespace attached, so reassembly is exact.
_WORD = re.compile(r"\S+\s*")


class Cadence:
    def __init__(self, tokens_per_sec: float) -> None:
        self._delay = 1.0 / max(1.0, tokens_per_sec)

    async def stream_text(self, text: str) -> AsyncIterator[str]:
        """Emit a complete string as paced word chunks (offline mode)."""
        for chunk in _WORD.findall(text):
            yield chunk
            await asyncio.sleep(self._delay)

    async def pace(self, source: AsyncIterator[str]) -> AsyncIterator[str]:
        """Re-chunk an arbitrary delta stream (LLM mode) into paced words.

        LLM deltas may be sub-word or multi-word; we buffer and re-split so the
        client always receives clean, evenly-timed word chunks.
        """
        buffer = ""
        async for delta in source:
            buffer += delta
            # Emit all complete words, keep any trailing partial word buffered.
            while True:
                m = _WORD.match(buffer)
                if not m or m.end() == len(buffer):
                    break  # nothing complete, or only a partial word remains
                yield m.group()
                buffer = buffer[m.end():]
                await asyncio.sleep(self._delay)
        if buffer:
            yield buffer
