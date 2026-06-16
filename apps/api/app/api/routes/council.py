"""Council control routes.

  GET  /council         -> current subject + supported symbols
  POST /council/symbol  -> switch the council's subject (takes effect next round)
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.config import SUPPORTED_SYMBOLS, SYMBOL_MAP
from app.services.council.session import SessionManager

router = APIRouter(prefix="/council", tags=["council"])


class SymbolRequest(BaseModel):
    symbol: str


def _sessions(request: Request) -> SessionManager:
    return request.app.state.session_manager


@router.get("")
async def council_state(request: Request) -> dict:
    sm = _sessions(request)
    return {"symbol": sm.symbol, "supported": SUPPORTED_SYMBOLS}


@router.post("/symbol")
async def set_symbol(body: SymbolRequest, request: Request) -> dict:
    resolved = SYMBOL_MAP.get(body.symbol.lower(), body.symbol.upper())
    if resolved not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail=f"unsupported symbol: {body.symbol}")
    _sessions(request).set_symbol(resolved)
    return {"symbol": resolved, "applied": "next_round"}
