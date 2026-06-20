"""Market service: spot + futures snapshots, candles, and the symbol universe.

Strategy per snapshot:
  1. Bitget (ticker + candles -> full snapshot with indicators), using the right
     path + granularity for the chosen market.
  2. CoinGecko fallback (spot majors only; no indicators).
Caches (TTL + single-flight) shield Bitget from bursty/concurrent demand.
"""

from __future__ import annotations

import time

from app.adapters.bitget.rest import BitgetRestClient
from app.adapters.coingecko.rest import CoinGeckoClient
from app.config import COINGECKO_IDS, Settings
from app.domain.enums import ConnectionState, DataSource, MarketType
from app.domain.models import Candle, MarketSnapshot, SymbolInfo
from app.services.market.cache import AsyncTTLCache
from app.services.market.indicators import compute_indicators, realized_volatility
from app.utils.logging import get_logger

log = get_logger("market.service")

_QUOTES = ("USDT", "USDC", "USD", "BTC", "ETH")


def _split_symbol(sym: str) -> tuple[str, str]:
    for q in _QUOTES:
        if sym.endswith(q) and len(sym) > len(q):
            return sym[: -len(q)], q
    return sym, ""


class MarketService:
    def __init__(
        self, bitget: BitgetRestClient, coingecko: CoinGeckoClient, settings: Settings
    ) -> None:
        self._bitget = bitget
        self._coingecko = coingecko
        self._settings = settings
        self._snap_cache: AsyncTTLCache[MarketSnapshot] = AsyncTTLCache(settings.snapshot_ttl_sec)
        self._candle_cache: AsyncTTLCache[list[Candle]] = AsyncTTLCache(settings.candle_cache_ttl_sec)
        self._symbols_cache: AsyncTTLCache[list[SymbolInfo]] = AsyncTTLCache(300.0)
        self.connection_state: ConnectionState = ConnectionState.OK

    def _granularity(self, market: MarketType) -> str:
        return (
            self._settings.candle_granularity_futures
            if market is MarketType.FUTURES
            else self._settings.candle_granularity
        )

    # ---- snapshot ----------------------------------------------------------
    async def get_snapshot(
        self, symbol: str, market: MarketType = MarketType.SPOT, *, use_cache: bool = True
    ) -> MarketSnapshot:
        key = f"{market.value}:{symbol}"
        if not use_cache:
            return await self._build_snapshot(symbol, market)
        return await self._snap_cache.get_or_load(key, lambda: self._build_snapshot(symbol, market))

    def peek_cached(self, symbol: str, market: MarketType = MarketType.SPOT) -> MarketSnapshot | None:
        return self._snap_cache.peek(f"{market.value}:{symbol}")

    async def _build_snapshot(self, symbol: str, market: MarketType) -> MarketSnapshot:
        try:
            snap = await self._from_bitget(symbol, market)
            self.connection_state = ConnectionState.OK
            return snap
        except Exception as exc:  # noqa: BLE001
            log.warning("Bitget snapshot failed for %s/%s (%s)", symbol, market.value, exc)
            if market is MarketType.SPOT and symbol in COINGECKO_IDS:
                snap = await self._from_coingecko(symbol)
                self.connection_state = ConnectionState.DEGRADED
                return snap
            raise

    async def _from_bitget(self, symbol: str, market: MarketType) -> MarketSnapshot:
        ticker = await self._bitget.get_ticker(symbol, market)
        candles = await self._bitget.get_candles(
            symbol, market, self._granularity(market), self._settings.candle_limit
        )
        closes = [row[4] for row in candles]
        indicators = compute_indicators(candles)
        volatility = realized_volatility(closes)
        change_ratio = float(ticker.get("change24h") or 0.0)
        return MarketSnapshot(
            symbol=symbol,
            price=float(ticker["lastPr"]),
            change24h=round(change_ratio * 100, 3),
            high24h=float(ticker.get("high24h") or ticker["lastPr"]),
            low24h=float(ticker.get("low24h") or ticker["lastPr"]),
            base_volume=float(ticker.get("baseVolume") or 0.0),
            quote_volume=float(ticker.get("quoteVolume") or ticker.get("usdtVolume") or 0.0),
            volatility=volatility,
            indicators=indicators,
            ts=int(ticker.get("ts") or time.time() * 1000),
            source=DataSource.BITGET,
            market=market,
        )

    async def _from_coingecko(self, symbol: str) -> MarketSnapshot:
        m = await self._coingecko.get_market(symbol)
        return MarketSnapshot(
            symbol=symbol, price=m["price"], change24h=round(m["change24h"], 3),
            high24h=m["high24h"], low24h=m["low24h"], base_volume=0.0,
            quote_volume=m["quote_volume"], volatility=0.0, indicators=None,
            ts=int(time.time() * 1000), source=DataSource.COINGECKO, market=MarketType.SPOT,
        )

    # ---- candles -----------------------------------------------------------
    async def get_candles(
        self, symbol: str, market: MarketType = MarketType.SPOT,
        granularity: str | None = None, limit: int = 200,
    ) -> list[Candle]:
        gran = granularity or self._granularity(market)
        key = f"{market.value}:{symbol}:{gran}:{limit}"
        return await self._candle_cache.get_or_load(
            key, lambda: self._load_candles(symbol, market, gran, limit)
        )

    async def _load_candles(self, symbol: str, market: MarketType, gran: str, limit: int) -> list[Candle]:
        rows = await self._bitget.get_candles(symbol, market, gran, limit)
        return [
            Candle(time=int(r[0] // 1000), open=r[1], high=r[2], low=r[3], close=r[4], volume=r[5])
            for r in rows
        ]

    # ---- symbol universe ---------------------------------------------------
    async def list_symbols(self, market: MarketType = MarketType.SPOT) -> list[SymbolInfo]:
        return await self._symbols_cache.get_or_load(market.value, lambda: self._load_symbols(market))

    async def _load_symbols(self, market: MarketType) -> list[SymbolInfo]:
        tickers = await self._bitget.list_tickers(market)

        def vol(t: dict) -> float:
            try:
                return float(t.get("usdtVolume") or t.get("quoteVolume") or 0.0)
            except (TypeError, ValueError):
                return 0.0

        tickers.sort(key=vol, reverse=True)
        out: list[SymbolInfo] = []
        for t in tickers:
            sym = t.get("symbol")
            if not sym:
                continue
            base, quote = _split_symbol(sym)
            out.append(SymbolInfo(symbol=sym, base=base, quote=quote, market=market))
        return out
