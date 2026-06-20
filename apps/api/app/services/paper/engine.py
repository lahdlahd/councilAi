"""Council Paper Trade Execution Engine.

Turns the Execution Agent's final decision into a simulated trade:

    BUY  -> open (or add to / flip into) a LONG  position
    SELL -> open (or add to / flip into) a SHORT position
    HOLD -> no trade
    veto -> no trade   (the Risk Manager's block is honored)

Position size scales with council confidence. Fills are simulated at the live
Bitget price captured at the moment of decision. PAPER ONLY — no exchange order
is ever placed. The engine is pure service logic: it depends on a Portfolio
(state), a PaperStore (persistence), and a Broadcaster (live UI events).
"""

from __future__ import annotations

from app.config import Settings
from app.domain.enums import MarketType, Side, TradeDirection
from app.domain.events import PaperTradeEvent, PortfolioUpdateEvent
from app.domain.models import MarketSnapshot, PaperTrade, Recommendation
from app.services.hub.broadcaster import Broadcaster
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio, _cash_funded
from app.utils.logging import get_logger

log = get_logger("paper.engine")


class PaperTradingEngine:
    def __init__(
        self, settings: Settings, manager: PortfolioManager, broadcaster: Broadcaster,
        pnl_tracker=None,
    ) -> None:
        self._settings = settings
        self._m = manager
        self._hub = broadcaster
        self._pnl = pnl_tracker

    @property
    def manager(self) -> PortfolioManager:
        return self._m

    @property
    def portfolio(self) -> Portfolio:
        return self._m.portfolio

    async def on_recommendation(
        self, recommendation: Recommendation | None, snapshot: MarketSnapshot, session_id: str | None
    ) -> PaperTrade | None:
        """Create a paper trade from a council decision, or None if no trade is warranted."""
        if recommendation is None:
            return None
        side = recommendation.side
        conf = recommendation.confidence if recommendation.confidence is not None else 50.0

        if recommendation.vetoed:
            log.info("no trade for %s — Risk Manager veto", snapshot.symbol)
            return None
        if side is Side.HOLD:
            log.info("no trade for %s — council HOLD", snapshot.symbol)
            return None
        if conf < self._settings.paper_min_confidence:
            log.info("no trade for %s — confidence %.0f below floor", snapshot.symbol, conf)
            return None

        price = snapshot.price
        if price <= 0:
            log.warning("no trade for %s — invalid price", snapshot.symbol)
            return None

        direction = TradeDirection.LONG if side is Side.BUY else TradeDirection.SHORT
        quantity, fee = self._size(conf, price, direction, snapshot.market)
        if quantity <= 0:
            log.info("no trade for %s — sized to zero (insufficient cash)", snapshot.symbol)
            return None

        result = await self._m.apply_decision(
            symbol=snapshot.symbol, market=snapshot.market, direction=direction,
            quantity=quantity, price=price, fee=fee, confidence=conf,
            session_id=session_id,
            reasoning=recommendation.summary or f"Council {side.value} @ {conf:.0f}% confidence",
        )
        trade = result.trade

        await self._hub.publish(PaperTradeEvent(trade=trade))
        await self._hub.publish(PortfolioUpdateEvent(portfolio=self._m.state()))
        if self._pnl is not None:
            self._pnl.ensure_running()  # begin streaming live PnL while the position is open
        log.info(
            "paper %s %s %.6f @ %.2f (session %s)",
            result.action.value, direction.value, trade.quantity, trade.entry_price, session_id,
        )
        return trade

    async def list_trades(self, limit: int = 50) -> list[PaperTrade]:
        return await self._m.list_trades(limit)

    async def reset(self) -> None:
        await self._m.reset()
        await self._hub.publish(PortfolioUpdateEvent(portfolio=self._m.state()))

    def _size(
        self, confidence: float, price: float, direction: TradeDirection, market: MarketType
    ) -> tuple[float, float]:
        """Notional = account value × fraction × confidence.

        A spot long is cash-funded, so it's capped by available cash. Futures
        (and simulated spot shorts) are margin-free, so they only need the fee.
        """
        account = self._m.account_value()
        notional = account * self._settings.paper_position_fraction * (confidence / 100.0)
        notional = max(self._settings.paper_min_notional, notional)

        fee = notional * self._settings.paper_fee_rate
        if _cash_funded(market, direction):                 # spot long: capped by cash
            affordable = max(0.0, self._m.cash - fee)
            notional = min(notional, affordable)
            fee = notional * self._settings.paper_fee_rate
        elif self._m.cash < fee:                            # margin-free: just need the fee
            return 0.0, 0.0

        quantity = notional / price if price > 0 else 0.0
        return quantity, fee
