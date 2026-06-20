"""Council control routes (advisory only — never places orders).

  GET  /council         -> idle/running state + the last session, if any
  POST /council/start    -> convene the council on {symbol, market}; streams over /ws/council
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.domain.enums import MarketType
from app.services.council.session import SessionManager

router = APIRouter(prefix="/council", tags=["council"])


class StartRequest(BaseModel):
    symbol: str
    market: MarketType = MarketType.SPOT


def _sessions(request: Request) -> SessionManager:
    return request.app.state.session_manager


@router.get("")
async def council_state(request: Request) -> dict:
    sm = _sessions(request)
    live = sm.current
    return {
        "running": sm.running,
        "session": (
            {"sessionId": live.session_id, "symbol": live.symbol,
             "market": live.market.value, "phase": live.phase}
            if live else None
        ),
    }


@router.post("/start")
async def start_council(body: StartRequest, request: Request) -> dict:
    symbol = body.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")
    return await _sessions(request).start(symbol, body.market)
