"""FastAPI dependency providers.

Services are created once in the lifespan (main.py) and stashed on `app.state`.
These helpers expose them to routes/ws handlers via Depends, keeping handlers
free of construction logic.
"""

from __future__ import annotations

from fastapi import Request

from app.services.hub.broadcaster import Broadcaster
from app.services.market.service import MarketService


def get_market_service(request: Request) -> MarketService:
    return request.app.state.market_service


def get_broadcaster(request: Request) -> Broadcaster:
    return request.app.state.broadcaster
