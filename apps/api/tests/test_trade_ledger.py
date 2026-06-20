"""Trade Ledger — fields, open/closed unification, and pagination."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.domain.enums import MarketType, TradeDirection, TradeStatus
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio
from app.services.paper.store import PaperStore


def _mgr() -> PortfolioManager:
    settings = get_settings()
    return PortfolioManager(Portfolio.new(settings.paper_starting_balance), PaperStore(None, "led"))


def _open(mgr, direction, price, qty, market=MarketType.SPOT, symbol="BTCUSDT", session="sess-x"):
    mgr.portfolio.apply_decision(
        symbol=symbol, market=market, direction=direction, quantity=qty, price=price,
        fee=0.0, confidence=77, session_id=session, reasoning="r",
    )


@pytest.mark.asyncio
async def test_ledger_entry_has_all_display_fields():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=50_000, qty=0.1, session="sess-42")
    mgr.portfolio.mark({("BTCUSDT", "spot"): 55_000})
    page = await mgr.ledger_page(limit=10, offset=0)
    e = page.items[0]
    assert e.trade_id.startswith("trade-")          # Trade ID
    assert e.opened_at > 0                           # Timestamp
    assert e.symbol == "BTCUSDT"                     # Trading Pair
    assert e.direction is TradeDirection.LONG        # Direction
    assert e.entry_price == 50_000                   # Entry Price
    assert e.quantity == pytest.approx(0.1)          # Quantity
    assert e.current_price == pytest.approx(55_000)  # Current Price (live)
    assert e.pnl_pct == pytest.approx(10.0)          # PnL %
    assert e.pnl_usd == pytest.approx(500.0)         # PnL USD
    assert e.status is TradeStatus.OPEN              # Status
    assert e.confidence == 77                        # Confidence
    assert e.session_id == "sess-42"                 # Council Session ID


@pytest.mark.asyncio
async def test_closed_trade_shows_realized_pnl_and_exit_price():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=50_000, qty=0.1)
    _open(mgr, TradeDirection.SHORT, price=51_000, qty=0.1)  # flip closes the long
    page = await mgr.ledger_page(limit=10, offset=0)
    closed = [e for e in page.items if e.status is TradeStatus.CLOSED][0]
    assert closed.current_price == pytest.approx(51_000)     # exit price
    assert closed.pnl_usd == pytest.approx(100.0)            # realized (no fees here)
    assert closed.pnl_pct == pytest.approx(2.0)              # 100 / 5000


@pytest.mark.asyncio
async def test_pagination_pages_and_has_more():
    mgr = _mgr()
    # open 5 positions on distinct symbols
    for i, sym in enumerate(["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT"]):
        _open(mgr, TradeDirection.LONG, price=100 + i, qty=1, symbol=sym, session=f"s{i}")
    p1 = await mgr.ledger_page(limit=2, offset=0)
    assert p1.total == 5
    assert len(p1.items) == 2
    assert p1.has_more is True
    p2 = await mgr.ledger_page(limit=2, offset=2)
    assert len(p2.items) == 2
    assert p2.has_more is True
    p3 = await mgr.ledger_page(limit=2, offset=4)
    assert len(p3.items) == 1
    assert p3.has_more is False
    # newest-first ordering: page 1 holds the most recently opened
    assert p1.items[0].symbol == "ADAUSDT"


@pytest.mark.asyncio
async def test_ledger_newest_first():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=100, qty=1, symbol="AAAUSDT", session="a")
    _open(mgr, TradeDirection.LONG, price=100, qty=1, symbol="BBBUSDT", session="b")
    page = await mgr.ledger_page(limit=10, offset=0)
    assert page.items[0].symbol == "BBBUSDT"
    assert page.items[1].symbol == "AAAUSDT"
