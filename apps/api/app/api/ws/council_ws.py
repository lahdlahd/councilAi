"""Council WebSocket endpoint: /ws/council

On connect:
  1. Sends a `session.snapshot` of the round currently in progress — so the client
     drops straight into a live debate with full context (no empty state).
  2. Streams every council/session/agent/vote event from the broadcaster.

Market ticks are filtered out here (they have their own /ws/market channel); the
client routes everything else by `type`.
"""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.council.session import SessionManager
from app.services.hub.broadcaster import Broadcaster
from app.utils.logging import get_logger

router = APIRouter()
log = get_logger("ws.council")


@router.websocket("/ws/council")
async def council_ws(websocket: WebSocket) -> None:
    await websocket.accept()
    hub: Broadcaster = websocket.app.state.broadcaster
    sessions: SessionManager = websocket.app.state.session_manager

    # 1) Hydrate with the in-progress session.
    snapshot_event = sessions.snapshot_event()
    if snapshot_event is not None:
        await websocket.send_text(snapshot_event.model_dump_json())

    # 2) Live stream (everything except market ticks) + disconnect detection.
    async def pump_events() -> None:
        async for event in hub.subscribe():
            if event.type == "market.tick":
                continue
            await websocket.send_text(event.model_dump_json())

    async def watch_disconnect() -> None:
        while True:
            await websocket.receive_text()

    pump = asyncio.create_task(pump_events())
    watch = asyncio.create_task(watch_disconnect())
    try:
        _, pending = await asyncio.wait({pump, watch}, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        pump.cancel()
        watch.cancel()
        log.info("council ws client disconnected")
