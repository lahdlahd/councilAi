"""Live PnL Engine — value, unrealized PnL, PnL %, and WebSocket streaming."""

from __future__ import annotations

import asyncio

import pytest

from app.config import get_settings
from app.domain.enums import MarketType, TradeDirection
from app.domain.models import (
    Ema, Indicators, Macd, MarketSnapshot,
)
from app.services.paper.manager import PortfolioManager
from app.services.paper.pnl import LivePnlEngine
from app.services.paper.portfolio import Portfolio
from app.services.paper.store import PaperStore


class _Hub:
    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event) -> None:
        self.events.append(event)


class _FakeMarket:
    """Returns a configurable price for any symbol/market."""

    def __init__(self, price: float) -> None:
        self.price = price

    async def get_snapshot(self, symbol: str, market: MarketType) -> MarketSnapshot:
        return MarketSnapshot(
            symbol=symbol, price=self.price, change24h=0, high24h=self.price, low24h=self.price,
            base_volume=1, quote_volume=1, volatility=0.1,
            indicators=Indicators(
                rsi=50, macd=Macd(macd=0, signal=0, histogram=0),
                ema=Ema(ema12=self.price, ema26=self.price, ema50=self.price),
            ),
            ts=1, source="bitget", market=market,
        )


def _mgr(price: float, market_service=None) -> PortfolioManager:
    settings = get_settings()
    return PortfolioManager(
        Portfolio.new(settings.paper_starting_balance), PaperStore(None, "pnl"), market_service
    )


def _open(mgr, direction, price, qty, market=MarketType.SPOT):
    mgr.portfolio.apply_decision(
        symbol="BTCUSDT", market=market, direction=direction, quantity=qty, price=price,
        fee=0.0, confidence=80, session_id="s", reasoning="r",
    )


def test_snapshot_calculates_value_unrealized_and_pct_long():
    mgr = _mgr(0)
    _open(mgr, TradeDirection.LONG, price=50_000, qty=0.1)  # cost 5,000
    mgr.portfolio.mark({("BTCUSDT", "spot"): 55_000})
    snap = mgr.pnl_snapshot()
    pos = snap.positions[0]
    assert pos.current_value == pytest.approx(5_500)        # 0.1 * 55000
    assert pos.unrealized_pnl == pytest.approx(500)         # (55000-50000)*0.1
    assert pos.pnl_pct == pytest.approx(10.0)               # 500 / 5000


def test_snapshot_pct_short_gains_when_price_falls():
    mgr = _mgr(0)
    _open(mgr, TradeDirection.SHORT, price=50_000, qty=0.1, market=MarketType.FUTURES)
    mgr.portfolio.mark({("BTCUSDT", "futures"): 45_000})
    pos = mgr.pnl_snapshot().positions[0]
    assert pos.unrealized_pnl == pytest.approx(500)         # (50000-45000)*0.1
    assert pos.pnl_pct == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_tick_uses_live_price_and_streams_update():
    market = _FakeMarket(price=55_000)
    mgr = _mgr(0, market)
    _open(mgr, TradeDirection.LONG, price=50_000, qty=0.1)
    hub = _Hub()
    engine = LivePnlEngine(mgr, hub, get_settings())
    snap = await engine.tick_once()
    # a pnl.update was streamed
    assert any(type(e).__name__ == "PnlUpdateEvent" for e in hub.events)
    # using the LIVE price (55000), not the entry
    assert snap.positions[0].mark_price == pytest.approx(55_000)
    assert snap.positions[0].pnl_pct == pytest.approx(10.0)


@pytest.mark.asyncio
async def test_loop_only_runs_while_positions_open():
    market = _FakeMarket(price=50_000)
    mgr = _mgr(0, market)  # no open positions
    hub = _Hub()
    engine = LivePnlEngine(mgr, hub, get_settings())
    engine.ensure_running()
    await asyncio.sleep(0.05)
    assert not engine.running          # never started — book is flat
    assert hub.events == []


@pytest.mark.asyncio
async def test_loop_starts_on_open_and_stops_when_flat():
    market = _FakeMarket(price=50_000)
    mgr = _mgr(0, market)
    _open(mgr, TradeDirection.LONG, price=50_000, qty=0.1)
    hub = _Hub()
    engine = LivePnlEngine(mgr, hub, get_settings())
    engine._interval = 0.01            # speed up for the test
    engine.ensure_running()
    await asyncio.sleep(0.05)
    assert engine.running
    assert len(hub.events) >= 1        # streaming while open
    # close the position; the loop should self-terminate
    mgr.portfolio.close_position("BTCUSDT", MarketType.SPOT, price=50_000, fee=0.0)
    await asyncio.sleep(0.05)
    assert not engine.running
