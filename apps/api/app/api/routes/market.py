"""Market REST routes — spot + futures.

  GET /symbols?market=spot|futures            -> selectable instruments (volume-sorted)
  GET /market?symbol=BTCUSDT&market=spot       -> full MarketSnapshot
  GET /market/candles?symbol=&market=&limit=   -> OHLC bars for the chart

Legacy per-coin routes (/market/btc ...) are kept for convenience (spot).
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_market_service
from app.config import SYMBOL_MAP
from app.domain.enums import MarketType
from app.domain.models import Candle, MarketSnapshot, SymbolInfo
from app.services.market.service import MarketService

router = APIRouter(tags=["market"])


async def _snapshot(symbol: str, market: MarketType, service: MarketService) -> MarketSnapshot:
    try:
        return await service.get_snapshot(symbol, market)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"market data unavailable: {exc}")


@router.get("/symbols", response_model=list[SymbolInfo])
async def list_symbols(
    market: MarketType = Query(default=MarketType.SPOT),
    service: MarketService = Depends(get_market_service),
) -> list[SymbolInfo]:
    try:
        return await service.list_symbols(market)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"symbol list unavailable: {exc}")


@router.get("/market", response_model=MarketSnapshot)
async def market_snapshot(
    symbol: str = Query(description="e.g. BTCUSDT"),
    market: MarketType = Query(default=MarketType.SPOT),
    service: MarketService = Depends(get_market_service),
) -> MarketSnapshot:
    return await _snapshot(symbol.upper(), market, service)


@router.get("/market/candles", response_model=list[Candle])
async def market_candles(
    symbol: str = Query(description="e.g. BTCUSDT"),
    market: MarketType = Query(default=MarketType.SPOT),
    limit: int = Query(default=200, ge=20, le=1000),
    service: MarketService = Depends(get_market_service),
) -> list[Candle]:
    try:
        return await service.get_candles(symbol.upper(), market, None, limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"candles unavailable: {exc}")


# ---- Legacy spot per-coin endpoints ---------------------------------------
def _legacy(symbol: str):
    async def handler(service: MarketService = Depends(get_market_service)) -> MarketSnapshot:
        return await _snapshot(symbol, MarketType.SPOT, service)
    return handler


for _key, _sym in SYMBOL_MAP.items():
    router.add_api_route(f"/market/{_key}", _legacy(_sym), response_model=MarketSnapshot, tags=["market"])
