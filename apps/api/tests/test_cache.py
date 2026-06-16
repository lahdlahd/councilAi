"""Tests for the market cache: TTL reuse + single-flight de-duplication."""

from __future__ import annotations

import asyncio

import pytest

from app.services.market.cache import AsyncTTLCache


@pytest.mark.asyncio
async def test_single_flight_collapses_concurrent_loads():
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.05)  # simulate a slow upstream call
        return "value"

    cache: AsyncTTLCache[str] = AsyncTTLCache(ttl=10)
    # 20 simultaneous cold-cache requests for the same key.
    results = await asyncio.gather(*[cache.get_or_load("k", loader) for _ in range(20)])

    assert results == ["value"] * 20
    assert calls == 1  # only ONE upstream fetch happened


@pytest.mark.asyncio
async def test_ttl_reuses_then_refreshes():
    calls = 0

    async def loader():
        nonlocal calls
        calls += 1
        return calls

    cache: AsyncTTLCache[int] = AsyncTTLCache(ttl=0.05)
    a = await cache.get_or_load("k", loader)
    b = await cache.get_or_load("k", loader)  # within TTL -> cached
    assert a == b == 1
    assert calls == 1

    await asyncio.sleep(0.06)  # let it expire
    c = await cache.get_or_load("k", loader)
    assert c == 2 and calls == 2


@pytest.mark.asyncio
async def test_peek_returns_last_value_ignoring_ttl():
    cache: AsyncTTLCache[str] = AsyncTTLCache(ttl=0.01)
    assert cache.peek("k") is None
    await cache.get_or_load("k", lambda: _const("hi"))
    await asyncio.sleep(0.02)  # expired for get_or_load, but peek still sees it
    assert cache.peek("k") == "hi"


@pytest.mark.asyncio
async def test_loader_exception_propagates_and_clears_inflight():
    async def boom():
        raise RuntimeError("upstream down")

    cache: AsyncTTLCache[str] = AsyncTTLCache(ttl=10)
    with pytest.raises(RuntimeError):
        await cache.get_or_load("k", boom)
    # A later successful load must still work (in-flight slot was cleared).
    assert await cache.get_or_load("k", lambda: _const("ok")) == "ok"


async def _const(v):
    return v
