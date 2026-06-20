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


# --- User-defined position sizing (Trade Configuration) -----------------------

from app.domain.enums import RiskLevel, SizingMode  # noqa: E402
from app.domain.models import TradeConfig  # noqa: E402


@pytest.mark.asyncio
async def test_percent_cap_limits_notional():
    engine, portfolio, _ = _engine()
    # 5% of a 100k book = 5,000 cap; futures so margin-free (not cash-limited).
    cfg = TradeConfig(sizing_mode=SizingMode.PERCENT, size_value=5, risk_level=RiskLevel.MODERATE)
    trade = await engine.on_recommendation(
        _rec(Side.BUY, confidence=100.0), _snapshot(market=MarketType.FUTURES), "s", trade_config=cfg
    )
    assert trade is not None
    notional = trade.quantity * trade.entry_price
    assert notional <= 5_000.0 + 1e-6


@pytest.mark.asyncio
async def test_fixed_usdt_cap():
    engine, *_ = _engine()
    cfg = TradeConfig(sizing_mode=SizingMode.FIXED, size_value=750, risk_level=RiskLevel.AGGRESSIVE)
    trade = await engine.on_recommendation(
        _rec(Side.BUY, confidence=100.0), _snapshot(market=MarketType.FUTURES), "s", trade_config=cfg
    )
    assert trade is not None
    notional = trade.quantity * trade.entry_price
    assert notional <= 750.0 + 1e-6  # never exceeds the user's hard cap


@pytest.mark.asyncio
async def test_aggressive_sizes_larger_than_conservative():
    def size_for(level: RiskLevel) -> float:
        engine, *_ = _engine()
        cfg = TradeConfig(sizing_mode=SizingMode.PERCENT, size_value=50, risk_level=level)
        q, _fee = engine._size(80.0, 50_000.0, TradeDirection.SHORT, MarketType.FUTURES, cfg)
        return q * 50_000.0

    assert size_for(RiskLevel.AGGRESSIVE) > size_for(RiskLevel.CONSERVATIVE)


@pytest.mark.asyncio
async def test_cap_below_floor_skips_trade():
    engine, *_ = _engine()
    # 0.01% of 100k = 10 USDT, below the 25 USDT min notional -> no trade.
    cfg = TradeConfig(sizing_mode=SizingMode.PERCENT, size_value=0.01, risk_level=RiskLevel.MODERATE)
    trade = await engine.on_recommendation(
        _rec(Side.BUY, confidence=100.0), _snapshot(market=MarketType.FUTURES), "s", trade_config=cfg
    )
    assert trade is None


@pytest.mark.asyncio
async def test_trade_stores_sizing_breakdown():
    engine, *_ = _engine()
    cfg = TradeConfig(sizing_mode=SizingMode.PERCENT, size_value=20, risk_level=RiskLevel.MODERATE)
    trade = await engine.on_recommendation(
        _rec(Side.BUY, confidence=100.0), _snapshot(market=MarketType.FUTURES), "s", trade_config=cfg
    )
    assert trade is not None
    assert trade.user_requested_size is not None
    assert trade.risk_adjusted_size is not None
    assert trade.final_executed_size is not None
    # Final never exceeds the user's requested cap.
    assert trade.final_executed_size <= trade.user_requested_size + 1e-6


@pytest.mark.asyncio
async def test_high_volatility_reduces_size_and_annotates_reasoning():
    engine, *_ = _engine()
    snap = _snapshot(market=MarketType.FUTURES)
    snap = snap.model_copy(update={"volatility": 0.8})  # high vol
    cfg = TradeConfig(sizing_mode=SizingMode.PERCENT, size_value=50, risk_level=RiskLevel.MODERATE)
    trade = await engine.on_recommendation(_rec(Side.BUY, confidence=100.0), snap, "s", trade_config=cfg)
    assert trade is not None
    # risk-adjusted (post-vol) is below the raw suggestion
    assert trade.risk_adjusted_size < trade.user_requested_size
    assert "volatility risk" in (trade.reasoning or "")


# --- Canonical trade schema consistency --------------------------------------

from app.domain.enums import TradeStatus  # noqa: E402
from app.domain.models import LedgerEntry, PaperTrade  # noqa: E402

CANONICAL_KEYS = {
    "id", "sessionId", "timestamp", "asset", "direction", "directionSignal",
    "entryPrice", "quantityRequested", "quantityExecuted", "riskAdjustedQuantity",
    "confidenceScore", "councilReasoning", "status", "pnlUsd", "pnlPercent",
}


def test_paper_trade_and_ledger_share_canonical_schema():
    trade = PaperTrade(
        id="t1", session_id="s1", symbol="BTCUSDT", market=MarketType.FUTURES,
        direction=TradeDirection.LONG, quantity=0.5, entry_price=60000.0,
        status=TradeStatus.OPEN, confidence=72.0, reasoning="because",
        user_requested_size=20000.0, risk_adjusted_size=15000.0, final_executed_size=12000.0,
        unrealized_pnl=300.0, pnl_pct=2.5, opened_at=1000,
    )
    entry = LedgerEntry(
        trade_id="t1", opened_at=1000, symbol="BTCUSDT", market=MarketType.FUTURES,
        direction=TradeDirection.LONG, entry_price=60000.0, quantity=0.5,
        current_price=60600.0, pnl_pct=2.5, pnl_usd=300.0, status=TradeStatus.OPEN,
        confidence=72.0, session_id="s1", quantity_requested=0.3333, risk_adjusted_quantity=0.25,
        reasoning="because",
    )
    td, ed = trade.model_dump(), entry.model_dump()
    assert CANONICAL_KEYS <= set(td.keys())
    assert CANONICAL_KEYS <= set(ed.keys())
    # Shared values line up across the two representations.
    for k in ("id", "sessionId", "timestamp", "asset", "directionSignal", "quantityExecuted"):
        assert td[k] == ed[k], k
