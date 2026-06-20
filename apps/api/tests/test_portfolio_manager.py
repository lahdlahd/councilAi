"""Council Portfolio Manager — balances, positions, equity, PnL."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.domain.enums import MarketType, TradeDirection, TradeStatus
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio
from app.services.paper.store import PaperStore


def _mgr() -> PortfolioManager:
    settings = get_settings()
    return PortfolioManager(Portfolio.new(settings.paper_starting_balance), PaperStore(None, "m"))


def _open(mgr: PortfolioManager, direction: TradeDirection, price: float, qty: float,
          market: MarketType = MarketType.SPOT, symbol: str = "BTCUSDT"):
    return mgr.portfolio.apply_decision(
        symbol=symbol, market=market, direction=direction, quantity=qty, price=price,
        fee=qty * price * 0.0006, confidence=80, session_id="s", reasoning="r",
    )


def test_starting_balance_is_100k():
    assert get_settings().paper_starting_balance == 100000.0
    mgr = _mgr()
    assert mgr.cash == 100000.0
    assert mgr.equity() == 100000.0
    assert mgr.starting_balance == 100000.0


def test_maintains_cash_balance_on_spot_long():
    mgr = _mgr()
    start = mgr.cash
    _open(mgr, TradeDirection.LONG, price=50000, qty=0.2)  # notional 10,000
    assert mgr.cash == pytest.approx(start - (10000 + 10000 * 0.0006), rel=1e-9)


def test_maintains_open_and_closed_positions():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=50000, qty=0.1)
    assert len(mgr.open_positions()) == 1
    assert mgr.closed_positions() == []
    # flip closes the long and opens a short
    _open(mgr, TradeDirection.SHORT, price=51000, qty=0.1)
    closed = mgr.closed_positions()
    assert len(closed) == 1
    assert closed[0].status is TradeStatus.CLOSED
    assert len(mgr.open_positions()) == 1
    assert mgr.open_positions()[0].direction is TradeDirection.SHORT


def test_calculates_unrealized_pnl():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=50000, qty=0.1)
    mgr.portfolio.mark({("BTCUSDT", "spot"): 52000})
    # (52000-50000)*0.1 = 200
    assert mgr.unrealized_pnl() == pytest.approx(200, rel=1e-6)


def test_calculates_realized_pnl():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=50000, qty=0.1)
    _open(mgr, TradeDirection.SHORT, price=51000, qty=0.1)  # flip -> realize long
    # (51000-50000)*0.1 = 100, minus fees
    assert mgr.realized_pnl() > 90
    assert mgr.realized_pnl() < 100


def test_calculates_equity_long():
    mgr = _mgr()
    start = mgr.equity()
    _open(mgr, TradeDirection.LONG, price=50000, qty=0.1)
    mgr.portfolio.mark({("BTCUSDT", "spot"): 51000})
    # equity = start - fees + unrealized(100)
    assert mgr.equity() == pytest.approx(start + 100 - (0.1 * 50000 * 0.0006), rel=1e-6)


def test_equity_futures_short_gains_when_price_falls():
    mgr = _mgr()
    start = mgr.equity()
    _open(mgr, TradeDirection.SHORT, price=50000, qty=0.1, market=MarketType.FUTURES)
    mgr.portfolio.mark({("BTCUSDT", "futures"): 49000})
    # short gains (50000-49000)*0.1 = 100 minus fee
    assert mgr.equity() == pytest.approx(start + 100 - (0.1 * 50000 * 0.0006), rel=1e-6)


def test_state_snapshot_shape():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=50000, qty=0.1)
    _open(mgr, TradeDirection.SHORT, price=51000, qty=0.1)  # flip
    st = mgr.state()
    assert st.starting_balance == 100000.0
    assert len(st.open_positions) == 1
    assert len(st.closed_positions) == 1
    assert st.trades_count == 1
    assert st.win_rate in (0.0, 100.0)
    # total pnl reflects realized + unrealized vs starting
    assert st.total_pnl == pytest.approx(st.equity - st.starting_balance, rel=1e-9)


@pytest.mark.asyncio
async def test_reset_restores_starting_balance():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, price=50000, qty=0.1)
    await mgr.reset()
    assert mgr.cash == 100000.0
    assert mgr.open_positions() == []
    assert mgr.closed_positions() == []
    assert mgr.realized_pnl() == 0.0
