"""Live PnL Engine.

A background loop that continuously marks every open paper position to live Bitget
prices and streams the result over the WebSocket as `pnl.update` events. For each
open position it reports current value, unrealized PnL, and PnL %; plus account
totals (equity, total PnL, return %).

Idle-respecting by design: the loop runs ONLY while positions are open. It's
(re)started when a trade opens and self-terminates once the book is flat, so there
is no always-on polling against Bitget when the council is idle.
"""

from __future__ import annotations

import asyncio

from app.config import Settings
from app.domain.events import PnlUpdateEvent
from app.domain.models import PnlSnapshot
from app.services.hub.broadcaster import Broadcaster
from app.services.paper.manager import PortfolioManager
from app.utils.logging import get_logger

log = get_logger("paper.pnl")


class LivePnlEngine:
    def __init__(
        self, manager: PortfolioManager, broadcaster: Broadcaster, settings: Settings
    ) -> None:
        self._m = manager
        self._hub = broadcaster
        self._interval = max(0.25, settings.paper_pnl_interval_sec)
        self._task: asyncio.Task | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    def ensure_running(self) -> None:
        """Start the live loop if it isn't already (called when a trade opens)."""
        if not self.running and self._m.has_open_positions():
            self._task = asyncio.create_task(self._loop())
            log.info("live PnL loop started (interval=%.2fs)", self._interval)

    async def tick_once(self) -> PnlSnapshot:
        """Mark once and broadcast — used on demand and by the loop."""
        await self._m.mark_to_market()
        snap = self._m.pnl_snapshot()
        await self._hub.publish(PnlUpdateEvent(pnl=snap))
        return snap

    async def _loop(self) -> None:
        try:
            while self._m.has_open_positions():
                await self.tick_once()
                await asyncio.sleep(self._interval)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must never crash the app
            log.warning("live PnL loop error: %s", exc)
        finally:
            log.info("live PnL loop stopped (book flat)")

    def stop(self) -> None:
        if self._task is not None and not self._task.done():
            self._task.cancel()
