"""Persistence for the paper-trading engine (Supabase, best-effort).

Mirrors the in-memory Portfolio to the 0002 schema: paper_trades (positions),
trade_events (append-only ledger incl. balance changes), portfolio (account),
portfolio_snapshots (equity curve). When Supabase isn't configured this is a safe
no-op and the engine runs fully in memory — persistence never breaks a round.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.adapters.supabase.client import SupabaseClient
from app.domain.enums import TradeAction, TradeStatus
from app.domain.models import PaperTrade
from app.services.paper.portfolio import OpenResult, Portfolio
from app.utils.logging import get_logger

log = get_logger("paper.store")


def _iso(ms: int | None) -> str | None:
    if ms is None:
        return None
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()


def _trade_row(t: PaperTrade, portfolio_id: str) -> dict:
    return {
        "id": t.id,
        "portfolio_id": portfolio_id,
        "session_id": t.session_id,
        "symbol": t.symbol,
        "market": t.market.value,
        "direction": t.direction.value,
        "quantity": t.quantity,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "last_mark_price": t.last_mark_price,
        "status": t.status.value,
        "confidence": t.confidence,
        "reasoning": t.reasoning,
        "fee": t.fee,
        "realized_pnl": t.realized_pnl,
        "unrealized_pnl": t.unrealized_pnl,
        "opened_at": _iso(t.opened_at),
        "closed_at": _iso(t.closed_at),
    }


class PaperStore:
    def __init__(self, supabase: SupabaseClient | None, portfolio_id: str) -> None:
        self._sb = supabase
        self._pid = portfolio_id

    @property
    def enabled(self) -> bool:
        return self._sb is not None

    # ---- startup load ------------------------------------------------------
    async def load(self, starting_balance: float) -> Portfolio | None:
        """Rehydrate the portfolio + open positions from Supabase, if present."""
        if self._sb is None:
            return None
        try:
            rows = await self._sb.select(
                "portfolio", {"id": f"eq.{self._pid}", "select": "*", "limit": "1"}
            )
            if not rows:
                return None
            p = rows[0]
            portfolio = Portfolio(
                starting_balance=float(p.get("starting_balance") or starting_balance),
                cash=float(p.get("cash_balance") or starting_balance),
                realized_pnl=float(p.get("realized_pnl") or 0.0),
                base_currency=p.get("base_currency") or "USDT",
                portfolio_id=self._pid,
            )
            # Rehydrate the full ledger (open + closed) so the trade ledger and
            # stats survive a restart, not just open positions.
            trades = await self._sb.select(
                "paper_trades",
                {
                    "portfolio_id": f"eq.{self._pid}", "select": "*",
                    "order": "opened_at.asc", "limit": "500",
                },
            )
            open_count = 0
            for row in trades:
                t = _row_to_trade(row)
                portfolio.ledger.append(t)
                if t.status is TradeStatus.OPEN:
                    portfolio.open[(t.symbol, t.market.value)] = t
                    open_count += 1
                elif t.status is TradeStatus.CLOSED:
                    portfolio.trades_count += 1
                    if t.realized_pnl >= 0:
                        portfolio.wins += 1
                    else:
                        portfolio.losses += 1
            log.info("loaded portfolio %s (%d open, %d total)", self._pid, open_count, len(trades))
            return portfolio
        except Exception as exc:  # noqa: BLE001
            log.warning("portfolio load failed: %s", exc)
            return None

    # ---- writes (best-effort) ---------------------------------------------
    async def persist_open(self, portfolio: Portfolio, result: OpenResult) -> None:
        if self._sb is None:
            log.debug("persist skipped (supabase disabled) — trade %s in memory only", result.trade.id)
            return
        try:
            if result.closed is not None:
                await self._sb.update(
                    "paper_trades", {"id": f"eq.{result.closed.id}"}, _trade_row(result.closed, self._pid)
                )
                await self._record_event(portfolio, result.closed, TradeAction.CLOSE)

            if result.action is TradeAction.INCREASE:
                await self._sb.update(
                    "paper_trades", {"id": f"eq.{result.trade.id}"}, _trade_row(result.trade, self._pid)
                )
            else:  # OPEN or FLIP -> a brand-new position row
                await self._sb.insert("paper_trades", _trade_row(result.trade, self._pid), upsert=True)
            await self._record_event(portfolio, result.trade, result.action)
            await self.upsert_portfolio(portfolio)
            log.info(
                "DB persist OK — trade=%s action=%s session=%s",
                result.trade.id, result.action.value, result.trade.session_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("DB persist FAILED — trade=%s: %s", result.trade.id, exc)

    async def _record_event(self, portfolio: Portfolio, t: PaperTrade, action: TradeAction) -> None:
        if self._sb is None:
            return
        price = t.exit_price if action is TradeAction.CLOSE else t.entry_price
        cash_delta = (
            t.realized_pnl
            if action is TradeAction.CLOSE
            else -(t.quantity * t.entry_price + t.fee)
            if t.direction.value == "long"
            else -t.fee
        )
        await self._sb.insert(
            "trade_events",
            {
                "trade_id": t.id,
                "portfolio_id": self._pid,
                "session_id": t.session_id,
                "event_type": action.value,
                "symbol": t.symbol,
                "market": t.market.value,
                "direction": t.direction.value,
                "quantity": t.quantity,
                "price": price,
                "fee": t.fee,
                "cash_delta": round(cash_delta, 6),
                "realized_pnl_delta": t.realized_pnl if action is TradeAction.CLOSE else 0.0,
                "balance_after": round(portfolio.cash, 6),
                "note": t.reasoning,
            },
        )

    async def upsert_portfolio(self, portfolio: Portfolio) -> None:
        if self._sb is None:
            return
        await self._sb.update(
            "portfolio",
            {"id": f"eq.{self._pid}"},
            {"cash_balance": round(portfolio.cash, 6), "realized_pnl": round(portfolio.realized_pnl, 6)},
        )

    async def snapshot(self, portfolio: Portfolio) -> None:
        if self._sb is None:
            return
        st = portfolio.state()
        await self._sb.insert(
            "portfolio_snapshots",
            {
                "portfolio_id": self._pid,
                "ts": int(__import__("time").time() * 1000),
                "cash": st.cash,
                "equity": st.equity,
                "unrealized_pnl": st.unrealized_pnl,
                "realized_pnl_cum": st.realized_pnl,
                "open_positions": len(st.open_positions),
            },
        )

    async def list_trades(self, limit: int = 50) -> list[PaperTrade]:
        if self._sb is None:
            return []
        rows = await self._sb.select(
            "paper_trades",
            {"portfolio_id": f"eq.{self._pid}", "select": "*", "order": "opened_at.desc", "limit": str(limit)},
        )
        return [_row_to_trade(r) for r in rows]


def _row_to_trade(row: dict) -> PaperTrade:
    def _ms(v) -> int | None:
        if not v:
            return None
        try:
            return int(datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp() * 1000)
        except ValueError:
            return None

    return PaperTrade(
        id=row["id"],
        session_id=row.get("session_id"),
        symbol=row["symbol"],
        market=row.get("market") or "spot",
        direction=row["direction"],
        quantity=float(row["quantity"]),
        entry_price=float(row["entry_price"]),
        exit_price=float(row["exit_price"]) if row.get("exit_price") is not None else None,
        last_mark_price=float(row["last_mark_price"]) if row.get("last_mark_price") is not None else None,
        status=row.get("status") or "open",
        confidence=float(row["confidence"]) if row.get("confidence") is not None else None,
        reasoning=row.get("reasoning"),
        fee=float(row.get("fee") or 0.0),
        realized_pnl=float(row.get("realized_pnl") or 0.0),
        unrealized_pnl=float(row["unrealized_pnl"]) if row.get("unrealized_pnl") is not None else None,
        opened_at=_ms(row.get("opened_at")) or 0,
        closed_at=_ms(row.get("closed_at")),
    )
