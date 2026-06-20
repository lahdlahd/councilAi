"""Hackathon compliance record — event log, report, CSV."""

from __future__ import annotations

import csv
import io

import pytest
from starlette.testclient import TestClient

from app.config import get_settings
from app.domain.enums import MarketType, TradeAction, TradeDirection
from app.main import create_app
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio
from app.services.paper.store import PaperStore


def _mgr() -> PortfolioManager:
    return PortfolioManager(Portfolio.new(get_settings().paper_starting_balance), PaperStore(None, "c"))


def _open(mgr, direction, price, qty, fee=3.0):
    mgr.portfolio.apply_decision(
        symbol="BTCUSDT", market=MarketType.SPOT, direction=direction, quantity=qty, price=price,
        fee=fee, confidence=80, session_id="s", reasoning="r",
    )


def test_event_log_records_open_and_close_with_balance_and_pnl():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, 50000, 0.1)
    _open(mgr, TradeDirection.SHORT, 51000, 0.1)  # flip: close long + open short
    events = mgr.event_log()
    kinds = [e.event_type for e in events]
    assert kinds == [TradeAction.OPEN, TradeAction.CLOSE, TradeAction.OPEN]
    open_ev, close_ev, _ = events
    # open: balance change negative, no pnl
    assert open_ev.cash_delta < 0
    assert open_ev.realized_pnl_delta == 0.0
    # close: realized pnl recorded, balance_after reflects it
    assert close_ev.realized_pnl_delta == pytest.approx((51000 - 50000) * 0.1 - 3.0)
    assert close_ev.balance_after > 0  # balance recorded after the event
    # every event carries the required fields
    for e in events:
        assert e.ts > 0 and e.symbol == "BTCUSDT" and e.price > 0 and e.quantity > 0


def test_compliance_report_shape_and_note():
    mgr = _mgr()
    _open(mgr, TradeDirection.LONG, 50000, 0.1)
    rep = mgr.compliance_report()
    assert rep.starting_balance == 100000.0
    assert rep.base_currency == "USDT"
    assert len(rep.records) == 1
    assert "simulated" in rep.note.lower()
    assert "no real orders" in rep.note.lower()


def test_compliance_csv_endpoint():
    with TestClient(create_app()) as c:
        r = c.get("/portfolio/compliance.csv")
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("text/csv")
        assert "attachment" in r.headers.get("content-disposition", "")
        header = next(csv.reader(io.StringIO(r.text)))
        for col in ["timestamp_ms", "pair", "direction", "price", "quantity", "balance_change", "pnl"]:
            assert col in header


def test_compliance_json_endpoint_public():
    with TestClient(create_app()) as c:
        r = c.get("/portfolio/compliance")
        assert r.status_code == 200
        d = r.json()
        assert "records" in d and "note" in d and "startingBalance" in d
