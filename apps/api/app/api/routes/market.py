"""Market REST routes.

  GET /market/btc | /eth | /sol | /xrp | /doge   -> full MarketSnapshot
  GET /market/{symbol}                            -> generic (any supported symbol)
  GET /market                                     -> all supported snapshots

Explicit per-coin routes are declared (as the spec requests) and delegate to a
shared handler so there's no duplication.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Path, Query

from app.api.deps import get_market_service
from app.config import SYMBOL_MAP
from app.domain.models import Candle, MarketSnapshot
from app.services.market.service import MarketService

router = APIRouter(prefix="/market", tags=["market"])


async def _snapshot(symbol: str, service: MarketService) -> MarketSnapshot:
    try:
        return await service.get_snapshot(symbol)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"market data unavailable: {exc}")


@router.get("", response_model=list[MarketSnapshot])
async def all_markets(
    service: MarketService = Depends(get_market_service),
) -> list[MarketSnapshot]:
    return [await _snapshot(sym, service) for sym in SYMBOL_MAP.values()]


# ---- Explicit per-coin endpoints (as specified) ----------------------------
@router.get("/btc", response_model=MarketSnapshot)
async def market_btc(service: MarketService = Depends(get_market_service)):
    return await _snapshot("BTCUSDT", service)


@router.get("/eth", response_model=MarketSnapshot)
async def market_eth(service: MarketService = Depends(get_market_service)):
    return await _snapshot("ETHUSDT", service)


@router.get("/sol", response_model=MarketSnapshot)
async def market_sol(service: MarketService = Depends(get_market_service)):
    return await _snapshot("SOLUSDT", service)


@router.get("/xrp", response_model=MarketSnapshot)
async def market_xrp(service: MarketService = Depends(get_market_service)):
    return await _snapshot("XRPUSDT", service)


@router.get("/doge", response_model=MarketSnapshot)
async def market_doge(service: MarketService = Depends(get_market_service)):
    return await _snapshot("DOGEUSDT", service)


# ---- Candles for charting --------------------------------------------------
@router.get("/{symbol}/candles", response_model=list[Candle])
async def market_candles(
    symbol: str = Path(description="Friendly key (btc) or full symbol (BTCUSDT)"),
    granularity: str | None = Query(default=None, description="e.g. 1min, 15min, 1h"),
    limit: int = Query(default=200, ge=20, le=1000),
    service: MarketService = Depends(get_market_service),
) -> list[Candle]:
    resolved = SYMBOL_MAP.get(symbol.lower(), symbol.upper())
    try:
        return await service.get_candles(resolved, granularity, limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"candles unavailable: {exc}")


# ---- Generic catch-all for any other supported symbol ----------------------
@router.get("/{symbol}", response_model=MarketSnapshot)
async def market_generic(
    symbol: str = Path(description="Friendly key (btc) or full symbol (BTCUSDT)"),
    service: MarketService = Depends(get_market_service),
):
    resolved = SYMBOL_MAP.get(symbol.lower(), symbol.upper())
    return await _snapshot(resolved, service)
