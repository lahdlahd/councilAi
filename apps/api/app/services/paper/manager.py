"""Council Portfolio Manager.

The single owner of the simulated account. It wraps the in-memory Portfolio
aggregate (state + math), the PaperStore (persistence), and the MarketService
(live marks), and exposes the manager's responsibilities behind one clean API:

  * maintain cash balance
  * maintain open positions
  * maintain closed positions
  * calculate equity
  * calculate unrealized PnL
  * calculate realized PnL

All trade mutations flow through `apply_decision`, which mutates state and
persists atomically (best-effort). PAPER ONLY — nothing is ever sent to an
exchange.
"""

from __future__ import annotations

import time

from app.domain.enums import MarketType, TradeDirection, TradeStatus
from app.domain.models import (
    ComplianceReport,
    LedgerEntry,
    LedgerPage,
    LivePosition,
    PaperTrade,
    PnlSnapshot,
    PortfolioState,
    TradeEvent,
)
from app.services.market.service import MarketService
from app.services.paper.portfolio import OpenResult, Portfolio
from app.services.paper.store import PaperStore
from app.utils.logging import get_logger

log = get_logger("paper.manager")


class PortfolioManager:
    def __init__(
        self, portfolio: Portfolio, store: PaperStore, market_service: MarketService | None = None
    ) -> None:
        self._p = portfolio
        self._store = store
        self._market = market_service

    @property
    def portfolio(self) -> Portfolio:
        return self._p

    # ---- cash balance ------------------------------------------------------
    @property
    def cash(self) -> float:
        return self._p.cash

    @property
    def starting_balance(self) -> float:
        return self._p.starting_balance

    def account_value(self) -> float:
        """Realized account value — the stable base used for position sizing."""
        return self._p.account_value()

    # ---- positions ---------------------------------------------------------
    def open_positions(self) -> list[PaperTrade]:
        return list(self._p.open.values())

    def closed_positions(self) -> list[PaperTrade]:
        return [t for t in self._p.ledger if t.status is TradeStatus.CLOSED]

    # ---- pnl & equity ------------------------------------------------------
    def realized_pnl(self) -> float:
        return self._p.realized_pnl

    def unrealized_pnl(self) -> float:
        return self._p.unrealized()

    def equity(self) -> float:
        return self._p.equity()

    def has_open_positions(self) -> bool:
        return bool(self._p.open)

    # ---- live PnL views ----------------------------------------------------
    def live_positions(self) -> list[LivePosition]:
        """Marked-to-market view of every open position: value, PnL, PnL%."""
        out: list[LivePosition] = []
        for t in self._p.open.values():
            mark = t.last_mark_price or t.entry_price
            cost = t.quantity * t.entry_price
            unreal = (
                (mark - t.entry_price) * t.quantity
                if t.direction is TradeDirection.LONG
                else (t.entry_price - mark) * t.quantity
            )
            out.append(
                LivePosition(
                    id=t.id, symbol=t.symbol, market=t.market, direction=t.direction,
                    quantity=t.quantity, entry_price=t.entry_price, mark_price=mark,
                    current_value=round(t.quantity * mark, 6),
                    unrealized_pnl=round(unreal, 6),
                    pnl_pct=round(unreal / cost * 100.0, 4) if cost else 0.0,
                )
            )
        return out

    def pnl_snapshot(self) -> PnlSnapshot:
        st = self._p.state()
        return PnlSnapshot(
            ts=int(time.time() * 1000), cash=st.cash, equity=st.equity,
            unrealized_pnl=st.unrealized_pnl, realized_pnl=st.realized_pnl,
            total_pnl=st.total_pnl, total_return_pct=st.total_return_pct,
            positions=self.live_positions(),
        )

    # ---- live marking ------------------------------------------------------
    async def mark_to_market(self) -> float:
        """Refresh marks for every open position from live Bitget prices.

        The MarketService cache (3s TTL + single-flight) shields the API, so this
        is cheap to call on every read. Returns the refreshed unrealized PnL.
        """
        if self._market is not None and self._p.open:
            marks: dict[tuple[str, str], float] = {}
            for symbol, market in list(self._p.open.keys()):
                try:
                    snap = await self._market.get_snapshot(symbol, MarketType(market))
                    marks[(symbol, market)] = snap.price
                except Exception as exc:  # noqa: BLE001 - marking must never raise
                    log.debug("mark failed for %s/%s: %s", symbol, market, exc)
            self._p.mark(marks)
        return self._p.unrealized()

    # ---- mutation ----------------------------------------------------------
    async def apply_decision(self, **kwargs) -> OpenResult:
        """Apply a council decision to the portfolio and persist it."""
        result = self._p.apply_decision(**kwargs)
        await self._store.persist_open(self._p, result)
        return result

    async def list_trades(self, limit: int = 50) -> list[PaperTrade]:
        if self._store.enabled:
            return await self._store.list_trades(limit)
        return list(reversed(self._p.ledger))[:limit]

    def get_trade(self, trade_id: str) -> PaperTrade | None:
        for t in self._p.ledger:
            if t.id == trade_id:
                return t
        return None

    # ---- trade ledger (paginated) -----------------------------------------
    def to_ledger_entry(self, t: PaperTrade) -> LedgerEntry:
        cost = t.quantity * t.entry_price
        if t.status is TradeStatus.CLOSED:
            current = t.exit_price or t.last_mark_price or t.entry_price
            pnl_usd = t.realized_pnl
        else:
            current = t.last_mark_price or t.entry_price
            pnl_usd = (
                (current - t.entry_price) * t.quantity
                if t.direction is TradeDirection.LONG
                else (t.entry_price - current) * t.quantity
            )
        return LedgerEntry(
            trade_id=t.id, opened_at=t.opened_at, symbol=t.symbol, market=t.market,
            direction=t.direction, entry_price=t.entry_price, quantity=t.quantity,
            current_price=current, pnl_pct=round(pnl_usd / cost * 100.0, 4) if cost else 0.0,
            pnl_usd=round(pnl_usd, 6), status=t.status, confidence=t.confidence,
            session_id=t.session_id,
            quantity_requested=(t.user_requested_size / t.entry_price)
            if (t.user_requested_size and t.entry_price > 0) else None,
            risk_adjusted_quantity=(t.risk_adjusted_size / t.entry_price)
            if (t.risk_adjusted_size and t.entry_price > 0) else None,
            reasoning=t.reasoning,
        )

    async def ledger_page(self, limit: int = 25, offset: int = 0) -> LedgerPage:
        """Paginated, most-recent-first ledger. Open rows are live-marked first."""
        await self.mark_to_market()
        rows = list(reversed(self._p.ledger))  # newest first
        total = len(rows)
        page = rows[offset : offset + limit]
        return LedgerPage(
            items=[self.to_ledger_entry(t) for t in page],
            total=total, limit=limit, offset=offset, has_more=offset + limit < total,
        )

    async def snapshot(self) -> None:
        await self._store.snapshot(self._p)

    async def reset(self) -> None:
        self._p.reset()
        await self._store.upsert_portfolio(self._p)

    # ---- compliance / trading record --------------------------------------
    def event_log(self) -> list[TradeEvent]:
        """Chronological per-fill record (balance changes + realized PnL)."""
        return list(self._p.events)

    def compliance_report(self) -> ComplianceReport:
        st = self._p.state()
        return ComplianceReport(
            generated_at=int(time.time() * 1000), portfolio_id=self._p.portfolio_id,
            base_currency=self._p.base_currency, starting_balance=st.starting_balance,
            equity=st.equity, cash=st.cash, realized_pnl=st.realized_pnl,
            total_pnl=st.total_pnl, total_return_pct=st.total_return_pct,
            trades_count=st.trades_count, win_rate=st.win_rate, records=self.event_log(),
            note=(
                "Paper trading record. All fills are simulated against live Bitget "
                "market prices; no real orders were placed on any exchange."
            ),
        )

    # ---- snapshot for the wire --------------------------------------------
    def state(self) -> PortfolioState:
        return self._p.state()
