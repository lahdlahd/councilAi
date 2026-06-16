"""Market service: orchestrates data sources + indicators into a MarketSnapshot.

Strategy:
  1. Try Bitget (ticker + candles -> full snapshot with indicators).
  2. On failure, fall back to CoinGecko (price/change/volume, no indicators).
  3. Cache snapshots per symbol for a short TTL to avoid hammering upstreams when
     both the REST routes and the WS stream want fresh data.
"""

from __future__ import annotations

import time

from app.adapters.bitget.rest import BitgetRestClient
from app.adapters.coingecko.rest import CoinGeckoClient
from app.config import Settings
from app.domain.enums import ConnectionState, DataSource
from app.domain.models import Candle, MarketSnapshot
from app.services.market.cache import AsyncTTLCache
from app.services.market.indicators import compute_indicators, realized_volatility
from app.utils.logging import get_logger

log = get_logger("market.service")


class MarketService:
    def __init__(
        self,
        bitget: BitgetRestClient,
        coingecko: CoinGeckoClient,
        settings: Settings,
    ) -> None:
        self._bitget = bitget
        self._coingecko = coingecko
        self._settings = settings
        # TTL + single-flight caches shield Bitget from bursty / concurrent demand.
        self._snap_cache: AsyncTTLCache[MarketSnapshot] = AsyncTTLCache(settings.snapshot_ttl_sec)
        self._candle_cache: AsyncTTLCache[list[Candle]] = AsyncTTLCache(settings.candle_cache_ttl_sec)
        # Overall data-source health, surfaced to clients.
        self.connection_state: ConnectionState = ConnectionState.OK

    async def get_snapshot(self, symbol: str, *, use_cache: bool = True) -> MarketSnapshot:
        if not use_cache:
            return await self._build_snapshot(symbol)
        return await self._snap_cache.get_or_load(symbol, lambda: self._build_snapshot(symbol))

    def peek_cached(self, symbol: str) -> MarketSnapshot | None:
        """Last known snapshot for a symbol, ignoring TTL. Used to enrich live ticks
        with the most recent indicators/volatility without a network round-trip."""
        return self._snap_cache.peek(symbol)

    async def get_candles(
        self, symbol: str, granularity: str | None = None, limit: int = 200
    ) -> list[Candle]:
        """OHLC bars for charting (oldest -> newest), via Bitget. Cached + single-flight."""
        gran = granularity or self._settings.candle_granularity
        key = f"{symbol}:{gran}:{limit}"
        return await self._candle_cache.get_or_load(key, lambda: self._load_candles(symbol, gran, limit))

    async def _load_candles(self, symbol: str, gran: str, limit: int) -> list[Candle]:
        rows = await self._bitget.get_candles(symbol, gran, limit)
        # row = [ts(ms), open, high, low, close, baseVol, quoteVol]
        return [
            Candle(time=int(r[0] // 1000), open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5])
            for r in rows
        ]

    async def _build_snapshot(self, symbol: str) -> MarketSnapshot:
        try:
            snap = await self._from_bitget(symbol)
            self.connection_state = ConnectionState.OK
            return snap
        except Exception as exc:  # noqa: BLE001
            log.warning("Bitget snapshot failed for %s (%s); trying CoinGecko", symbol, exc)

        snap = await self._from_coingecko(symbol)
        self.connection_state = ConnectionState.DEGRADED
        return snap

    async def _from_bitget(self, symbol: str) -> MarketSnapshot:
        ticker = await self._bitget.get_ticker(symbol)
        candles = await self._bitget.get_candles(
            symbol,
            self._settings.candle_granularity,
            self._settings.candle_limit,
        )
        closes = [row[4] for row in candles]
        indicators = compute_indicators(candles)
        volatility = realized_volatility(closes)

        # change24h: Bitget gives `change24h` as a ratio (e.g. 0.0234). Present as %.
        change_ratio = float(ticker.get("change24h") or 0.0)
        return MarketSnapshot(
            symbol=symbol,
            price=float(ticker["lastPr"]),
            change24h=round(change_ratio * 100, 3),
            high24h=float(ticker["high24h"]),
            low24h=float(ticker["low24h"]),
            base_volume=float(ticker.get("baseVolume") or 0.0),
            quote_volume=float(ticker.get("quoteVolume") or 0.0),
            volatility=volatility,
            indicators=indicators,
            ts=int(ticker.get("ts") or time.time() * 1000),
            source=DataSource.BITGET,
        )

    async def _from_coingecko(self, symbol: str) -> MarketSnapshot:
        m = await self._coingecko.get_market(symbol)
        return MarketSnapshot(
            symbol=symbol,
            price=m["price"],
            change24h=round(m["change24h"], 3),
            high24h=m["high24h"],
            low24h=m["low24h"],
            base_volume=0.0,
            quote_volume=m["quote_volume"],
            volatility=0.0,
            indicators=None,  # no OHLC -> no indicators on fallback
            ts=int(time.time() * 1000),
            source=DataSource.COINGECKO,
        )
