"""Market WebSocket endpoint: /ws/market

On connect:
  1. Sends a one-shot snapshot of every supported symbol (so the client paints
     immediately — no empty state).
  2. Streams every market.tick / connection.status event from the broadcaster.

The client never sends anything meaningful; we still drain its receive side so we
notice disconnects promptly.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import SYMBOL_MAP
from app.domain.events import MarketTickEvent
from app.services.hub.broadcaster import Broadcaster
from app.services.market.service import MarketService
from app.utils.logging import get_logger

router = APIRouter()
log = get_logger("ws.market")


@router.websocket("/ws/market")
async def market_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    service: MarketService = websocket.app.state.market_service
    hub: Broadcaster = websocket.app.state.broadcaster

    # 1) Initial snapshots so the UI is populated on first paint.
    for sym in SYMBOL_MAP.values():
        try:
            snap = await service.get_snapshot(sym)
            await websocket.send_text(MarketTickEvent(snapshot=snap).model_dump_json())
        except Exception as exc:  # noqa: BLE001
            log.warning("initial snapshot failed for %s: %s", sym, exc)

    # 2) Live stream + disconnect detection run concurrently.
    async def pump_events() -> None:
        async for event in hub.subscribe():
            await websocket.send_text(event.model_dump_json())

    async def watch_disconnect() -> None:
        # Receiving raises WebSocketDisconnect when the client goes away.
        while True:
            await websocket.receive_text()

    pump = asyncio.create_task(pump_events())
    watch = asyncio.create_task(watch_disconnect())
    try:
        done, pending = await asyncio.wait(
            {pump, watch}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        pump.cancel()
        watch.cancel()
        log.info("market ws client disconnected")
