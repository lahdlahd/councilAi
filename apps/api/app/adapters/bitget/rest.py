"""Bitget v2 spot REST adapter.

Public market endpoints — no auth required:
  GET /api/v2/spot/market/tickers?symbol=BTCUSDT
  GET /api/v2/spot/market/candles?symbol=BTCUSDT&granularity=15min&limit=200

Returns raw, typed primitives (dicts / lists of floats). All domain mapping and
indicator computation happens in the service layer, keeping this adapter thin.
"""

from __future__ import annotations

import httpx

from app.utils.logging import get_logger
from app.utils.retry import with_retry

log = get_logger("bitget.rest")

_OK_CODE = "00000"


class BitgetError(RuntimeError):
    """Raised when Bitget returns a non-success code or malformed payload."""


class BitgetRestClient:
    def __init__(self, client: httpx.AsyncClient, base_url: str) -> None:
        self._client = client
        self._base = base_url.rstrip("/")

    async def _get(self, path: str, params: dict[str, str | int]) -> dict | list:
        async def _call() -> dict:
            resp = await self._client.get(f"{self._base}{path}", params=params)
            resp.raise_for_status()
            return resp.json()

        payload = await with_retry(_call, label=f"bitget GET {path}")
        if not isinstance(payload, dict) or payload.get("code") != _OK_CODE:
            msg = payload.get("msg") if isinstance(payload, dict) else "bad payload"
            raise BitgetError(f"Bitget error on {path}: {msg}")
        return payload.get("data", [])

    async def get_ticker(self, symbol: str) -> dict[str, str]:
        """Return the raw ticker dict for one symbol."""
        data = await self._get(
            "/api/v2/spot/market/tickers", {"symbol": symbol}
        )
        if not data:
            raise BitgetError(f"No ticker data for {symbol}")
        # tickers returns a list; single-symbol query yields one element.
        return data[0] if isinstance(data, list) else data

    async def get_candles(
        self, symbol: str, granularity: str, limit: int
    ) -> list[list[float]]:
        """Return candles oldest->newest as [ts, open, high, low, close, baseVol, quoteVol].

        Bitget returns newest-first strings; we reverse and cast to float so the
        indicator layer can treat the series chronologically.
        """
        data = await self._get(
            "/api/v2/spot/market/candles",
            {"symbol": symbol, "granularity": granularity, "limit": limit},
        )
        if not isinstance(data, list) or not data:
            raise BitgetError(f"No candle data for {symbol}")
        candles = [[float(x) for x in row[:7]] for row in data]
        candles.reverse()  # chronological ascending
        return candles
