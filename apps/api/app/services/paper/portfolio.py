"""In-memory portfolio aggregate for paper trading.

Authoritative at runtime; the store mirrors it to Supabase when configured.
PAPER ONLY — fills are simulated against live prices, nothing hits an exchange.

Position model:
  * One open position per (symbol, market).
  * BUY  -> long, SELL -> short (paper short is allowed on spot data too).
  * A decision opposite to an open position FLIPS it (close then open the other side);
    same-direction INCREASES it (weighted-average entry).
Cash model (simple, paper):
  * Long  open: cash -= qty*price + fee   (you bought the asset)
  * Short open: cash -= fee               (margin-free paper)
  * Close: realized PnL booked to cash (and to cumulative realized_pnl)
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.enums import MarketType, TradeAction, TradeDirection, TradeStatus
from app.domain.models import PaperTrade, PortfolioState, TradeEvent

_DEFAULT_PORTFOLIO_ID = "00000000-0000-0000-0000-000000000001"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _cash_funded(market: MarketType, direction: TradeDirection) -> bool:
    """Only a SPOT LONG actually buys the asset and consumes notional cash.

    Spot shorts (simulated paper) and all FUTURES positions — long or short — are
    margin-free paper: opening costs only the fee, PnL is realized on close. This
    makes BUY and SELL symmetric on futures.
    """
    return market is MarketType.SPOT and direction is TradeDirection.LONG


@dataclass
class OpenResult:
    """Outcome of applying a council decision to the portfolio."""

    trade: PaperTrade                 # the resulting open position
    action: TradeAction               # OPEN | INCREASE | FLIP
    closed: PaperTrade | None = None  # a position closed by a flip


@dataclass
class Portfolio:
    starting_balance: float
    cash: float
    realized_pnl: float = 0.0
    base_currency: str = "USDT"
    portfolio_id: str = _DEFAULT_PORTFOLIO_ID
    open: dict[tuple[str, str], PaperTrade] = field(default_factory=dict)
    trades_count: int = 0
    wins: int = 0
    losses: int = 0
    ledger: list[PaperTrade] = field(default_factory=list)  # all trades, chronological
    events: list[TradeEvent] = field(default_factory=list)  # per-fill record (compliance log)
    day_anchor_equity: float | None = None   # equity at the start of the current UTC day
    day_anchor_day: str = ""                  # the UTC date the anchor was taken

    @classmethod
    def new(cls, starting_balance: float) -> "Portfolio":
        return cls(starting_balance=starting_balance, cash=starting_balance)

    def reset(self) -> None:
        self.cash = self.starting_balance
        self.realized_pnl = 0.0
        self.open.clear()
        self.ledger.clear()
        self.events.clear()
        self.trades_count = self.wins = self.losses = 0
        self.day_anchor_equity = None
        self.day_anchor_day = ""

    def _record(
        self, action: TradeAction, t: PaperTrade, price: float, qty: float,
        cash_delta: float, pnl_delta: float = 0.0,
    ) -> None:
        self.events.append(
            TradeEvent(
                ts=_now_ms(), event_type=action, trade_id=t.id, session_id=t.session_id,
                symbol=t.symbol, market=t.market, direction=t.direction, price=price,
                quantity=qty, cash_delta=round(cash_delta, 6),
                realized_pnl_delta=round(pnl_delta, 6), balance_after=round(self.cash, 6),
            )
        )

    # ---- sizing base -------------------------------------------------------
    def account_value(self) -> float:
        """Stable base for position sizing (realized account value)."""
        return self.starting_balance + self.realized_pnl

    # ---- mutations ---------------------------------------------------------
    def apply_decision(
        self, *, symbol: str, market: MarketType, direction: TradeDirection,
        quantity: float, price: float, fee: float, confidence: float | None,
        session_id: str | None, reasoning: str | None,
    ) -> OpenResult:
        key = (symbol, market.value)
        existing = self.open.get(key)

        if existing is not None and existing.direction == direction:
            self._increase(existing, quantity, price, fee)
            return OpenResult(trade=existing, action=TradeAction.INCREASE)

        closed: PaperTrade | None = None
        action = TradeAction.OPEN
        if existing is not None:  # opposite direction -> flip
            closed = self._close(existing, price, fee)
            action = TradeAction.FLIP

        trade = PaperTrade(
            id=f"trade-{uuid.uuid4().hex[:12]}",
            session_id=session_id, symbol=symbol, market=market, direction=direction,
            quantity=quantity, entry_price=price, last_mark_price=price,
            status=TradeStatus.OPEN, confidence=confidence, reasoning=reasoning,
            fee=fee, opened_at=_now_ms(),
        )
        open_cost = (quantity * price + fee) if _cash_funded(market, direction) else fee
        self.cash -= open_cost
        self.open[key] = trade
        self.ledger.append(trade)
        self._record(TradeAction.OPEN, trade, price, quantity, cash_delta=-open_cost)
        return OpenResult(trade=trade, action=action, closed=closed)

    def _increase(self, t: PaperTrade, qty: float, price: float, fee: float) -> None:
        total = t.quantity + qty
        t.entry_price = (t.entry_price * t.quantity + price * qty) / total
        t.quantity = total
        t.fee += fee
        t.last_mark_price = price
        add_cost = (qty * price + fee) if _cash_funded(t.market, t.direction) else fee
        self.cash -= add_cost
        self._record(TradeAction.INCREASE, t, price, qty, cash_delta=-add_cost)

    def _close(self, t: PaperTrade, price: float, fee: float) -> PaperTrade:
        before = self.cash
        if t.direction is TradeDirection.LONG:
            gross = (price - t.entry_price) * t.quantity
        else:
            gross = (t.entry_price - price) * t.quantity
        if _cash_funded(t.market, t.direction):
            self.cash += t.quantity * price - fee   # spot long: sell the asset back
        else:
            self.cash += gross - fee                # margin-free: realize PnL only
        t.status = TradeStatus.CLOSED
        t.exit_price = price
        t.last_mark_price = price
        t.fee += fee
        t.realized_pnl = gross - fee
        t.unrealized_pnl = 0.0
        t.closed_at = _now_ms()
        self.realized_pnl += t.realized_pnl
        self.trades_count += 1
        if t.realized_pnl >= 0:
            self.wins += 1
        else:
            self.losses += 1
        self.open.pop((t.symbol, t.market.value), None)
        self._record(TradeAction.CLOSE, t, price, t.quantity, cash_delta=self.cash - before,
                     pnl_delta=t.realized_pnl)
        return t

    def close_position(self, symbol: str, market: MarketType, price: float, fee: float) -> PaperTrade | None:
        existing = self.open.get((symbol, market.value))
        return self._close(existing, price, fee) if existing else None

    # ---- marking & state ---------------------------------------------------
    def mark(self, marks: dict[tuple[str, str], float]) -> None:
        for key, t in self.open.items():
            price = marks.get(key, t.last_mark_price or t.entry_price)
            t.last_mark_price = price
            if t.direction is TradeDirection.LONG:
                t.unrealized_pnl = (price - t.entry_price) * t.quantity
            else:
                t.unrealized_pnl = (t.entry_price - price) * t.quantity
            t.current_value = t.quantity * price
            cost = t.quantity * t.entry_price
            t.pnl_pct = (t.unrealized_pnl / cost * 100.0) if cost else 0.0

    def unrealized(self) -> float:
        total = 0.0
        for t in self.open.values():
            mark = t.last_mark_price or t.entry_price
            total += (
                (mark - t.entry_price) * t.quantity
                if t.direction is TradeDirection.LONG
                else (t.entry_price - mark) * t.quantity
            )
        return total

    def equity(self) -> float:
        add = 0.0
        for t in self.open.values():
            mark = t.last_mark_price or t.entry_price
            if _cash_funded(t.market, t.direction):          # spot long: asset market value
                add += t.quantity * mark
            elif t.direction is TradeDirection.LONG:         # futures long: unrealized only
                add += (mark - t.entry_price) * t.quantity
            else:                                            # short (spot/futures): unrealized
                add += (t.entry_price - mark) * t.quantity
        return self.cash + add

    def daily_return_pct(self) -> float:
        """Return since the start of the current UTC day (or since the app first
        marked today). Anchors to current equity on the first call each day."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        eq = self.equity()
        if self.day_anchor_day != today or self.day_anchor_equity is None:
            self.day_anchor_day = today
            self.day_anchor_equity = eq
            return 0.0
        base = self.day_anchor_equity
        return (eq - base) / base * 100.0 if base else 0.0

    def avg_confidence(self) -> float:
        confs = [t.confidence for t in self.ledger if t.confidence is not None]
        return sum(confs) / len(confs) if confs else 0.0

    def state(self) -> PortfolioState:
        equity = self.equity()
        unrealized = self.unrealized()
        total_pnl = equity - self.starting_balance
        return PortfolioState(
            portfolio_id=self.portfolio_id, base_currency=self.base_currency,
            starting_balance=self.starting_balance, cash=round(self.cash, 4),
            equity=round(equity, 4), realized_pnl=round(self.realized_pnl, 4),
            unrealized_pnl=round(unrealized, 4), total_pnl=round(total_pnl, 4),
            total_return_pct=round(total_pnl / self.starting_balance * 100, 4)
            if self.starting_balance else 0.0,
            daily_return_pct=round(self.daily_return_pct(), 4),
            avg_confidence=round(self.avg_confidence(), 1),
            open_positions=list(self.open.values()),
            closed_positions=[t for t in self.ledger if t.status is TradeStatus.CLOSED],
            trades_count=self.trades_count, wins=self.wins, losses=self.losses,
            win_rate=round(self.wins / self.trades_count * 100, 1) if self.trades_count else 0.0,
        )
