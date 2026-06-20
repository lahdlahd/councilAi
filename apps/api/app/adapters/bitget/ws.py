"""Bitget public WebSocket consumer.

Connects to wss://ws.bitget.com/v2/ws/public, subscribes to the SPOT `ticker`
channel for every supported symbol, and republishes each push as a MarketTickEvent
on the in-process broadcaster. Live ticks are enriched with the latest indicators
from the MarketService cache so volatility/RSI stay populated between REST refreshes.

Bitget keepalive: the server closes idle connections after 30s. We send the literal
string "ping" every 20s; the server replies "pong". We also answer server "ping".
Reconnects with exponential backoff on any drop.
"""

from __future__ import annotations

import asyncio
import json
import time

import websockets

from app.config import SUPPORTED_SYMBOLS, Settings
from app.domain.enums import ConnectionState, DataSource, MarketType
from app.domain.events import ConnectionStatusEvent, MarketTickEvent
from app.domain.models import MarketSnapshot
from app.services.hub.broadcaster import Broadcaster
from app.services.market.service import MarketService
from app.utils.logging import get_logger

log = get_logger("bitget.ws")

_PING_INTERVAL = 20.0


class BitgetWsConsumer:
    def __init__(
        self,
        settings: Settings,
        broadcaster: Broadcaster,
        market_service: MarketService,
    ) -> None:
        self._settings = settings
        self._hub = broadcaster
        self._market = market_service
        self._stop = asyncio.Event()

    async def run(self) -> None:
        """Run forever, reconnecting on failure. Cancel the task to stop."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                await self._connect_and_stream()
                backoff = 1.0  # reset after a clean session
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001
                log.warning("Bitget WS dropped: %s — reconnecting in %.1fs", exc, backoff)
                await self._hub.publish(
                    ConnectionStatusEvent(
                        state=ConnectionState.DEGRADED,
                        detail="market stream reconnecting",
                    )
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    def stop(self) -> None:
        self._stop.set()

    async def _connect_and_stream(self) -> None:
        async with websockets.connect(
            self._settings.bitget_ws_public,
            ping_interval=None,  # we manage keepalive manually per Bitget's protocol
            close_timeout=5,
        ) as ws:
            await self._subscribe(ws)
            await self._hub.publish(
                ConnectionStatusEvent(state=ConnectionState.OK, detail="market stream live")
            )
            log.info("Bitget WS connected; subscribed to %d symbols", len(SUPPORTED_SYMBOLS))

            ping_task = asyncio.create_task(self._keepalive(ws))
            try:
                async for raw in ws:
                    await self._handle_message(raw)
            finally:
                ping_task.cancel()

    async def _subscribe(self, ws: websockets.WebSocketClientProtocol) -> None:
        args = [
            {"instType": "SPOT", "channel": "ticker", "instId": sym}
            for sym in SUPPORTED_SYMBOLS
        ]
        await ws.send(json.dumps({"op": "subscribe", "args": args}))

    async def _keepalive(self, ws: websockets.WebSocketClientProtocol) -> None:
        try:
            while True:
                await asyncio.sleep(_PING_INTERVAL)
                await ws.send("ping")
        except (asyncio.CancelledError, websockets.ConnectionClosed):
            return

    async def _handle_message(self, raw: str | bytes) -> None:
        if isinstance(raw, bytes):
            raw = raw.decode()
        if raw == "pong":
            return
        if raw == "ping":  # server-initiated ping
            return
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return

        # Subscription acks / errors carry an `event` field, not data.
        if msg.get("event") == "error":
            log.warning("Bitget WS error: %s", msg.get("msg"))
            return
        if "data" not in msg or msg.get("arg", {}).get("channel") != "ticker":
            return

        for row in msg["data"]:
            snapshot = self._row_to_snapshot(row)
            if snapshot is not None:
                await self._hub.publish(MarketTickEvent(snapshot=snapshot))

    def _row_to_snapshot(self, row: dict) -> MarketSnapshot | None:
        try:
            symbol = row["instId"]
            price = float(row["lastPr"])
        except (KeyError, ValueError, TypeError):
            return None

        change_ratio = float(row.get("change24h") or 0.0)
        cached = self._market.peek_cached(symbol, MarketType.SPOT)
        return MarketSnapshot(
            symbol=symbol,
            price=price,
            change24h=round(change_ratio * 100, 3),
            high24h=float(row.get("high24h") or price),
            low24h=float(row.get("low24h") or price),
            base_volume=float(row.get("baseVolume") or 0.0),
            quote_volume=float(row.get("quoteVolume") or 0.0),
            # Enrich from the last REST snapshot so these don't read as zero live.
            volatility=cached.volatility if cached else 0.0,
            indicators=cached.indicators if cached else None,
            ts=int(row.get("ts") or time.time() * 1000),
            source=DataSource.BITGET,
        )
