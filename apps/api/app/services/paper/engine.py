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

from dataclasses import dataclass

from app.config import Settings
from app.domain.enums import MarketType, Side, TradeDirection
from app.domain.events import PaperTradeEvent, PortfolioUpdateEvent
from app.domain.models import MarketSnapshot, PaperTrade, Recommendation
from app.services.hub.broadcaster import Broadcaster
from app.services.paper.manager import PortfolioManager
from app.services.paper.portfolio import Portfolio, _cash_funded
from app.utils.logging import get_logger

log = get_logger("paper.engine")


@dataclass
class _Sizing:
    """Full position-sizing breakdown for one decision (notionals in USDT)."""

    suggested: float            # council suggestion
    user_requested: float | None  # user cap, if set
    risk_adjusted: float        # after risk-level + volatility reduction
    final: float                # executed notional
    quantity: float
    fee: float
    vol_reduced: bool


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
        self, recommendation: Recommendation | None, snapshot: MarketSnapshot, session_id: str | None,
        trade_config=None,
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
        sizing = self._compute_sizing(
            conf, price, direction, snapshot.market, snapshot.volatility, trade_config
        )
        if sizing.quantity <= 0:
            log.info("no trade for %s — sized to zero (cap/cash floor)", snapshot.symbol)
            return None

        reasoning = self._build_reasoning(recommendation, side, conf, sizing, trade_config)

        result = await self._m.apply_decision(
            symbol=snapshot.symbol, market=snapshot.market, direction=direction,
            quantity=sizing.quantity, price=price, fee=sizing.fee, confidence=conf,
            session_id=session_id,
            reasoning=reasoning,
            user_requested_size=sizing.user_requested,
            risk_adjusted_size=sizing.risk_adjusted,
            final_executed_size=sizing.final,
        )
        trade = result.trade

        log.info(
            "TRADE CREATED id=%s session=%s %s %s qty=%.6f entry=%.2f final=%.2f USDT",
            trade.id, session_id, side.value, direction.value,
            trade.quantity, trade.entry_price, sizing.final,
        )

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

    # Risk appetite scales the council's suggested size *within* the user cap.
    _RISK_MULT = {"conservative": 0.5, "moderate": 1.0, "aggressive": 1.5}

    @staticmethod
    def _cap_label(trade_config) -> str:
        from app.domain.enums import SizingMode
        if trade_config.sizing_mode is SizingMode.PERCENT:
            return f"{trade_config.size_value:.0f}% of book"
        return f"{trade_config.size_value:.0f} USDT"

    def _build_reasoning(self, recommendation, side, conf, sizing, trade_config) -> str:
        base = recommendation.summary or f"Council {side.value} @ {conf:.0f}% confidence"
        sizes = f"Suggested {sizing.suggested:.0f} USDT"
        if sizing.user_requested is not None:
            sizes += f", user max {sizing.user_requested:.0f} USDT"
        sizes += f", executed {sizing.final:.0f} USDT"
        parts = [base, sizes]
        if sizing.vol_reduced:
            parts.append("Position size adjusted due to volatility risk")
        return " · ".join(parts)

    def _size(
        self, confidence: float, price: float, direction: TradeDirection, market: MarketType,
        trade_config=None,
    ) -> tuple[float, float]:
        """Back-compat shim — returns (quantity, fee) with no volatility input."""
        s = self._compute_sizing(confidence, price, direction, market, 0.0, trade_config)
        return s.quantity, s.fee

    def _compute_sizing(
        self, confidence: float, price: float, direction: TradeDirection, market: MarketType,
        volatility: float, trade_config=None,
    ) -> "_Sizing":
        """Council suggests; risk appetite scales it; volatility trims it; the user
        cap is a hard ceiling.

            suggested      = equity × fraction × confidence          (council)
            scaled         = suggested × risk_level_multiplier        (user appetite)
            risk_adjusted  = scaled × volatility_factor               (Risk Manager / Quant)
            final          = min(user_cap, max(risk_adjusted, floor)) (hard user cap)

        A spot long is also capped by available cash. The Risk Manager can only
        reduce the size (or veto); it can never raise it above the user cap.
        """
        from app.domain.enums import SizingMode

        account = self._m.account_value()
        suggested = account * self._settings.paper_position_fraction * (confidence / 100.0)

        if trade_config is not None:
            mult = self._RISK_MULT.get(trade_config.risk_level.value, 1.0)
            scaled = suggested * mult
            if trade_config.sizing_mode is SizingMode.PERCENT:
                user_cap: float | None = account * max(0.0, trade_config.size_value) / 100.0
            else:
                user_cap = max(0.0, trade_config.size_value)
        else:
            scaled = suggested
            user_cap = None

        # Volatility risk adjustment — trim size as volatility rises (up to -50%).
        vol = max(0.0, volatility)
        vol_factor = 1.0 - min(vol, 1.0) * 0.5
        risk_adjusted = scaled * vol_factor
        vol_reduced = vol_factor < 0.999

        floor = self._settings.paper_min_notional
        if user_cap is not None:
            notional = min(user_cap, max(risk_adjusted, floor))
            if notional < floor:  # user capped below the tradeable floor
                return _Sizing(suggested, user_cap, risk_adjusted, 0.0, 0.0, 0.0, vol_reduced)
        else:
            notional = max(floor, risk_adjusted)

        fee = notional * self._settings.paper_fee_rate
        if _cash_funded(market, direction):                 # spot long: capped by cash
            affordable = max(0.0, self._m.cash - fee)
            notional = min(notional, affordable)
            fee = notional * self._settings.paper_fee_rate
        elif self._m.cash < fee:                            # margin-free: just need the fee
            return _Sizing(suggested, user_cap, risk_adjusted, 0.0, 0.0, 0.0, vol_reduced)

        quantity = notional / price if price > 0 else 0.0
        return _Sizing(suggested, user_cap, risk_adjusted, notional, quantity, fee, vol_reduced)
