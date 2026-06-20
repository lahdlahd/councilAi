"""Council Paper Trade Execution Engine — rules and bookkeeping."""

from __future__ import annotations

import pytest

from app.config import get_settings
from app.domain.enums import AgentId, MarketType, Side, TradeDirection
from app.domain.models import (
    Ema, Indicators, Macd, MarketSnapshot, Recommendation,
)
from app.services.paper.engine import PaperTradingEngine
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio
from app.services.paper.store import PaperStore


class _Hub:
    def __init__(self) -> None:
        self.events: list = []

    async def publish(self, event) -> None:
        self.events.append(event)


def _snapshot(symbol: str = "BTCUSDT", price: float = 50_000.0, market: MarketType = MarketType.SPOT) -> MarketSnapshot:
    return MarketSnapshot(
        symbol=symbol, price=price, change24h=2.0, high24h=price * 1.02, low24h=price * 0.98,
        base_volume=1000, quote_volume=5e7, volatility=0.3,
        indicators=Indicators(
            rsi=55, macd=Macd(macd=10, signal=5, histogram=5),
            ema=Ema(ema12=price, ema26=price, ema50=price),
        ),
        ts=1, source="bitget", market=market,
    )


def _rec(side: Side, confidence: float = 80.0, vetoed: bool = False) -> Recommendation:
    return Recommendation(
        session_id="sess-test", symbol="BTCUSDT", side=side, confidence=confidence,
        summary="test", consensus_ratio=1.0, consensus_reached=True, vetoed=vetoed,
        veto_reason="risk" if vetoed else None, ts=1,
    )


def _engine() -> tuple[PaperTradingEngine, Portfolio, _Hub]:
    settings = get_settings()
    portfolio = Portfolio.new(settings.paper_starting_balance)
    manager = PortfolioManager(portfolio, PaperStore(supabase=None, portfolio_id="p-test"))
    hub = _Hub()
    return PaperTradingEngine(settings, manager, hub), portfolio, hub


@pytest.mark.asyncio
async def test_buy_opens_long_with_required_fields():
    engine, portfolio, hub = _engine()
    trade = await engine.on_recommendation(_rec(Side.BUY), _snapshot(), "sess-1")

    assert trade is not None
    assert trade.direction is TradeDirection.LONG
    # required stored fields
    assert trade.symbol == "BTCUSDT"
    assert trade.opened_at > 0                 # timestamp
    assert trade.entry_price == 50_000.0       # entry price (live fill)
    assert trade.quantity > 0                  # quantity
    assert trade.confidence == 80.0            # confidence
    assert trade.session_id == "sess-1"        # council session id
    # a paper.trade event was broadcast
    assert any(type(e).__name__ == "PaperTradeEvent" for e in hub.events)


@pytest.mark.asyncio
async def test_sell_opens_short():
    engine, portfolio, _ = _engine()
    trade = await engine.on_recommendation(_rec(Side.SELL), _snapshot(), "sess-2")
    assert trade is not None
    assert trade.direction is TradeDirection.SHORT
    assert ("BTCUSDT", "spot") in portfolio.open


@pytest.mark.asyncio
async def test_hold_creates_no_trade():
    engine, portfolio, _ = _engine()
    trade = await engine.on_recommendation(_rec(Side.HOLD), _snapshot(), "sess-3")
    assert trade is None
    assert portfolio.open == {}


@pytest.mark.asyncio
async def test_veto_creates_no_trade():
    engine, portfolio, _ = _engine()
    trade = await engine.on_recommendation(_rec(Side.BUY, vetoed=True), _snapshot(), "sess-4")
    assert trade is None
    assert portfolio.open == {}


@pytest.mark.asyncio
async def test_long_open_reduces_cash():
    engine, portfolio, _ = _engine()
    start = portfolio.cash
    trade = await engine.on_recommendation(_rec(Side.BUY), _snapshot(), "sess-5")
    assert portfolio.cash < start
    # cash drop ~= notional + fee
    assert portfolio.cash == pytest.approx(start - (trade.quantity * trade.entry_price + trade.fee), rel=1e-6)


@pytest.mark.asyncio
async def test_sizing_scales_with_confidence():
    settings = get_settings()
    big = Portfolio.new(settings.paper_starting_balance)
    small = Portfolio.new(settings.paper_starting_balance)
    e_big = PaperTradingEngine(settings, PortfolioManager(big, PaperStore(None, "a")), _Hub())
    e_small = PaperTradingEngine(settings, PortfolioManager(small, PaperStore(None, "b")), _Hub())
    t_big = await e_big.on_recommendation(_rec(Side.BUY, confidence=100), _snapshot(), "s")
    t_small = await e_small.on_recommendation(_rec(Side.BUY, confidence=20), _snapshot(), "s")
    assert t_big.quantity > t_small.quantity


@pytest.mark.asyncio
async def test_opposite_decision_flips_and_books_pnl():
    engine, portfolio, _ = _engine()
    await engine.on_recommendation(_rec(Side.BUY), _snapshot(price=50_000), "sess-a")
    # price rises, then council says SELL -> close long (profit) and open short
    trade = await engine.on_recommendation(_rec(Side.SELL), _snapshot(price=51_000), "sess-b")
    assert trade.direction is TradeDirection.SHORT
    assert portfolio.realized_pnl > 0          # the long was closed at a profit
    assert portfolio.trades_count == 1
    assert portfolio.wins == 1


@pytest.mark.asyncio
async def test_futures_buy_opens_long():
    engine, portfolio, _ = _engine()
    trade = await engine.on_recommendation(
        _rec(Side.BUY), _snapshot(market=MarketType.FUTURES), "f-1"
    )
    assert trade is not None
    assert trade.direction is TradeDirection.LONG
    assert trade.market is MarketType.FUTURES
    assert ("BTCUSDT", "futures") in portfolio.open


@pytest.mark.asyncio
async def test_futures_sell_opens_short():
    engine, portfolio, _ = _engine()
    trade = await engine.on_recommendation(
        _rec(Side.SELL), _snapshot(market=MarketType.FUTURES), "f-2"
    )
    assert trade is not None
    assert trade.direction is TradeDirection.SHORT
    assert trade.market is MarketType.FUTURES


@pytest.mark.asyncio
async def test_futures_is_margin_free_both_directions():
    # On futures, neither a long nor a short consumes notional — only the fee.
    e_long, p_long, _ = _engine()
    e_short, p_short, _ = _engine()
    start = p_long.cash
    tl = await e_long.on_recommendation(_rec(Side.BUY), _snapshot(market=MarketType.FUTURES), "fl")
    ts = await e_short.on_recommendation(_rec(Side.SELL), _snapshot(market=MarketType.FUTURES), "fs")
    # cash only drops by the (tiny) fee, not by qty*price
    assert p_long.cash == pytest.approx(start - tl.fee, rel=1e-9)
    assert p_short.cash == pytest.approx(start - ts.fee, rel=1e-9)
    # and both are sized the same (symmetric)
    assert tl.quantity == pytest.approx(ts.quantity, rel=1e-9)


@pytest.mark.asyncio
async def test_futures_long_pnl_correct_on_close():
    engine, portfolio, _ = _engine()
    await engine.on_recommendation(_rec(Side.BUY), _snapshot(price=50_000, market=MarketType.FUTURES), "a")
    # price rises 2% then council flips to SELL -> closes long in profit
    await engine.on_recommendation(_rec(Side.SELL), _snapshot(price=51_000, market=MarketType.FUTURES), "b")
    # realized ~= (51000-50000)*qty - fees, must be positive
    assert portfolio.realized_pnl > 0
    assert portfolio.wins == 1


@pytest.mark.asyncio
async def test_spot_and_futures_positions_coexist():
    engine, portfolio, _ = _engine()
    await engine.on_recommendation(_rec(Side.BUY), _snapshot(market=MarketType.SPOT), "s")
    await engine.on_recommendation(_rec(Side.SELL), _snapshot(market=MarketType.FUTURES), "f")
    assert ("BTCUSDT", "spot") in portfolio.open
    assert ("BTCUSDT", "futures") in portfolio.open
    assert portfolio.open[("BTCUSDT", "spot")].direction is TradeDirection.LONG
    assert portfolio.open[("BTCUSDT", "futures")].direction is TradeDirection.SHORT
