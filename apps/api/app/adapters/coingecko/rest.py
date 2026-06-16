"""CoinGecko fallback adapter.

Used only when Bitget is unreachable. Provides enough for a price/change/volume
snapshot. CoinGecko does not give us OHLC cheaply on the free tier in the same
shape, so fallback snapshots carry no indicators and volatility is best-effort 0.
The frontend is told via a `connection.status: degraded` event.
"""

from __future__ import annotations

import httpx

from app.config import COINGECKO_IDS
from app.utils.logging import get_logger
from app.utils.retry import with_retry

log = get_logger("coingecko.rest")


class CoinGeckoError(RuntimeError):
    pass


class CoinGeckoClient:
    def __init__(
        self, client: httpx.AsyncClient, base_url: str, api_key: str | None
    ) -> None:
        self._client = client
        self._base = base_url.rstrip("/")
        self._headers = {"x-cg-demo-api-key": api_key} if api_key else {}

    async def get_market(self, symbol: str) -> dict[str, float]:
        coin_id = COINGECKO_IDS.get(symbol)
        if not coin_id:
            raise CoinGeckoError(f"No CoinGecko mapping for {symbol}")

        async def _call() -> dict:
            resp = await self._client.get(
                f"{self._base}/coins/markets",
                params={"vs_currency": "usd", "ids": coin_id},
                headers=self._headers,
            )
            resp.raise_for_status()
            return resp.json()

        data = await with_retry(_call, label="coingecko markets")
        if not data:
            raise CoinGeckoError(f"No market data for {coin_id}")
        row = data[0]
        return {
            "price": float(row["current_price"]),
            "change24h": float(row.get("price_change_percentage_24h") or 0.0),
            "high24h": float(row.get("high_24h") or row["current_price"]),
            "low24h": float(row.get("low_24h") or row["current_price"]),
            "quote_volume": float(row.get("total_volume") or 0.0),
        }
