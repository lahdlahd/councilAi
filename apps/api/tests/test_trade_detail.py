"""Trade Details — composite of trade outcome + the council session that caused it."""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from app.config import get_settings
from app.domain.enums import MarketType, TradeDirection
from app.domain.events import SessionSnapshotEvent
from app.domain.models import Ema, Indicators, Macd, MarketSnapshot
from app.main import create_app
from app.services.council.session import SessionManager
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio
from app.services.paper.store import PaperStore


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTCUSDT", price=50000, change24h=2, high24h=51000, low24h=49000,
        base_volume=1, quote_volume=1, volatility=0.3,
        indicators=Indicators(
            rsi=55, macd=Macd(macd=1, signal=0, histogram=1),
            ema=Ema(ema12=50000, ema26=50000, ema50=50000),
        ),
        ts=1, source="bitget", market=MarketType.SPOT,
    )


def test_get_trade_by_id():
    mgr = PortfolioManager(Portfolio.new(get_settings().paper_starting_balance), PaperStore(None, "d"))
    mgr.portfolio.apply_decision(
        symbol="BTCUSDT", market=MarketType.SPOT, direction=TradeDirection.LONG,
        quantity=0.1, price=50000, fee=0.0, confidence=80, session_id="sess-9", reasoning="r",
    )
    t = mgr.open_positions()[0]
    assert mgr.get_trade(t.id) is t
    assert mgr.get_trade("nope") is None


def test_session_detail_fallback_builds_journal_entry():
    sm = SessionManager(get_settings(), None, None, None, None)
    ev = SessionSnapshotEvent(
        session_id="sess-7", symbol="BTCUSDT", snapshot=_snapshot(), started_at=1,
        phase="decided", agents=[], messages=[], votes=[],
    )
    sm._recent["sess-7"] = ev
    entry = sm.session_detail("sess-7")
    assert entry is not None
    assert entry.session_id == "sess-7"
    assert entry.symbol == "BTCUSDT"
    assert sm.session_detail("missing") is None


def test_trade_detail_unknown_returns_404():
    with TestClient(create_app()) as c:
        assert c.get("/portfolio/trades/does-not-exist").status_code == 404
