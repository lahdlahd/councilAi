"""Portfolio dashboard metrics — daily return, avg confidence, win/loss counts."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.domain.enums import MarketType, TradeDirection
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio
from app.services.paper.store import PaperStore


def _mgr() -> PortfolioManager:
    return PortfolioManager(Portfolio.new(get_settings().paper_starting_balance), PaperStore(None, "d"))


def _open(mgr, direction, price, qty, conf=80, symbol="BTCUSDT"):
    mgr.portfolio.apply_decision(
        symbol=symbol, market=MarketType.SPOT, direction=direction, quantity=qty, price=price,
        fee=0.0, confidence=conf, session_id="s", reasoning="r",
    )


def test_avg_confidence_across_trades():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, 50000, 0.1, conf=60, symbol="BTCUSDT")
    _open(mgr, TradeDirection.LONG, 3000, 1, conf=100, symbol="ETHUSDT")
    assert mgr.state().avg_confidence == pytest.approx(80.0)


def test_win_loss_counts():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, 50000, 0.1)
    _open(mgr, TradeDirection.SHORT, 51000, 0.1)  # flip -> win
    st = mgr.state()
    assert st.wins == 1
    assert st.losses == 0
    assert st.win_rate == 100.0


def test_open_and_closed_counts():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, 50000, 0.1, symbol="BTCUSDT")
    _open(mgr, TradeDirection.LONG, 3000, 1, symbol="ETHUSDT")
    _open(mgr, TradeDirection.SHORT, 3100, 1, symbol="ETHUSDT")  # closes ETH long
    st = mgr.state()
    assert len(st.open_positions) == 2     # BTC long + new ETH short
    assert len(st.closed_positions) == 1   # ETH long closed


def test_daily_return_anchors_then_moves():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, 50000, 0.1)
    # first state() call anchors the day -> 0
    assert mgr.state().daily_return_pct == pytest.approx(0.0)
    # price rises -> daily return goes positive
    mgr.portfolio.mark({("BTCUSDT", "spot"): 55000})
    assert mgr.state().daily_return_pct > 0


def test_total_return_vs_starting():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, 50000, 0.1)
    mgr.portfolio.mark({("BTCUSDT", "spot"): 55000})
    st = mgr.state()
    # equity up ~500 on 100k start -> ~0.5%
    assert st.total_return_pct == pytest.approx(st.total_pnl / st.starting_balance * 100, rel=1e-6)
