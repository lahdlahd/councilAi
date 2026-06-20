"""Bitget v2 REST adapter — spot and futures (mix), public market data only.

Public market endpoints, no auth:
  SPOT     GET /api/v2/spot/market/tickers[?symbol=]
           GET /api/v2/spot/market/candles?symbol=&granularity=&limit=
  FUTURES  GET /api/v2/mix/market/tickers?productType=USDT-FUTURES[&symbol=]
           GET /api/v2/mix/market/candles?symbol=&productType=...&granularity=&limit=

Spot and futures differ in URL path, the `productType` param, and candle granularity
codes (spot: 15min/1h ; futures: 15m/1H). The service layer passes the right values.
"""

from __future__ import annotations

import httpx

from app.domain.enums import MarketType
from app.utils.logging import get_logger
from app.utils.retry import with_retry

log = get_logger("bitget.rest")

_OK_CODE = "00000"


class BitgetError(RuntimeError):
    """Raised when Bitget returns a non-success code or malformed payload."""


class BitgetRestClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str, product_type: str) -> None:
        self._client = client
        self._base = base_url.rstrip("/")
        self._product_type = product_type

    async def _get(self, path: str, params: dict[str, str | int]) -> list | dict:
        async def _call() -> dict:
            resp = await self._client.get(f"{self._base}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

        payload = await with_retry(_call, label=f"bitget GET {path}")
        if not isinstance(payload, dict) or payload.get("code") != _OK_CODE:
            msg = payload.get("msg") if isinstance(payload, dict) else "bad payload"
            raise BitgetError(f"Bitget error on {path}: {msg}")
        return payload.get("data", [])

    # ---- tickers -----------------------------------------------------------
    async def get_ticker(self, symbol: str, market: MarketType) -> dict:
        if market is MarketType.FUTURES:
            data = await self._get(
                "/api/v2/mix/market/tickers",
                {"productType": self._product_type, "symbol": symbol},
            )
        else:
            data = await self._get("/api/v2/spot/market/tickers", {"symbol": symbol})
        if not data:
            raise BitgetError(f"No ticker for {symbol} ({market.value})")
        return data[0] if isinstance(data, list) else data

    # ---- candles -----------------------------------------------------------
    async def get_candles(
        self, symbol: str, market: MarketType, granularity: str, limit: int
    ) -> list[list[float]]:
        """Candles oldest->newest as [ts, open, high, low, close, baseVol, quoteVol]."""
        if market is MarketType.FUTURES:
            data = await self._get(
                "/api/v2/mix/market/candles",
                {
                    "symbol": symbol,
                    "productType": self._product_type,
                    "granularity": granularity,
                    "limit": limit,
                },
            )
        else:
            data = await self._get(
                "/api/v2/spot/market/candles",
                {"symbol": symbol, "granularity": granularity, "limit": limit},
            )
        if not isinstance(data, list) or not data:
            raise BitgetError(f"No candles for {symbol} ({market.value})")
        candles = [[float(x) for x in row[:7]] for row in data]
        candles.reverse()
        return candles

    # ---- symbol universe ---------------------------------------------------
    async def list_tickers(self, market: MarketType) -> list[dict]:
        """All tickers for a market (used to build the symbol picker, volume-sorted)."""
        if market is MarketType.FUTURES:
            data = await self._get(
                "/api/v2/mix/market/tickers", {"productType": self._product_type}
            )
        else:
            data = await self._get("/api/v2/spot/market/tickers", {})
        return data if isinstance(data, list) else []
