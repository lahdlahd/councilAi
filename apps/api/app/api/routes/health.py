"""Health + readiness route (used by Render's health check)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import get_broadcaster, get_market_service
from app.services.hub.broadcaster import Broadcaster
from app.services.market.service import MarketService

router = APIRouter(tags=["health"])


@router.get("/health")
async def health(
    service: MarketService = Depends(get_market_service),
    hub: Broadcaster = Depends(get_broadcaster),
) -> dict:
    return {
        "status": "ok",
        "marketConnection": service.connection_state.value,
        "wsSubscribers": hub.subscriber_count,
    }
