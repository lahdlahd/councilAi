"""Portfolio / paper-trading read routes (Portfolio Manager, Prompt 4).

  GET  /portfolio            -> full account: cash, equity, realized/unrealized PnL,
                                open & closed positions, stats (live-marked)
  GET  /portfolio/positions   -> open positions only (live-marked)
  GET  /portfolio/closed      -> closed positions only
  GET  /portfolio/trades      -> recent trades (ledger)
  POST /portfolio/reset       -> reset to starting balance (demo convenience)

Trades are NEVER created here — the engine creates them automatically from council
decisions. These endpoints are read/admin only.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response

from app.domain.models import (
    ComplianceReport,
    LedgerPage,
    PaperTrade,
    PerformanceAnalytics,
    PnlSnapshot,
    PortfolioState,
    TradeDetail,
)
from app.services.paper.analytics import build_analytics
from app.services.paper.manager import PortfolioManager
from app.utils.logging import get_logger

log = get_logger("api.portfolio")

router = APIRouter(prefix="/portfolio", tags=["portfolio"])


def _mgr(request: Request) -> PortfolioManager:
    return request.app.state.portfolio_manager


@router.get("", response_model=PortfolioState)
async def get_portfolio(request: Request) -> PortfolioState:
    mgr = _mgr(request)
    await mgr.mark_to_market()
    return mgr.state()


@router.get("/positions", response_model=list[PaperTrade])
async def get_positions(request: Request) -> list[PaperTrade]:
    mgr = _mgr(request)
    await mgr.mark_to_market()
    return mgr.open_positions()


@router.get("/closed", response_model=list[PaperTrade])
async def get_closed(request: Request) -> list[PaperTrade]:
    return _mgr(request).closed_positions()


@router.get("/pnl", response_model=PnlSnapshot)
async def get_pnl(request: Request) -> PnlSnapshot:
    """Live marked-to-market PnL: current value, unrealized PnL, and PnL % per
    open position, plus account totals. The WebSocket streams the same payload."""
    mgr = _mgr(request)
    await mgr.mark_to_market()
    return mgr.pnl_snapshot()


@router.get("/ledger", response_model=LedgerPage)
async def get_ledger(
    request: Request,
    limit: int = Query(default=10, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> LedgerPage:
    """Paginated trade ledger — every paper trade with live current price and PnL."""
    page = await _mgr(request).ledger_page(limit, offset)
    log.info("GET /portfolio/ledger -> %d items (total=%d offset=%d)", len(page.items), page.total, offset)
    return page


@router.get("/compliance", response_model=ComplianceReport)
async def get_compliance(request: Request) -> ComplianceReport:
    """Public paper-trading record for hackathon submission: every fill with
    timestamp, pair, direction, price, quantity, balance change, and PnL."""
    mgr = _mgr(request)
    await mgr.mark_to_market()
    return mgr.compliance_report()


@router.get("/compliance.csv")
async def get_compliance_csv(request: Request) -> Response:
    mgr = _mgr(request)
    await mgr.mark_to_market()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "timestamp_ms", "datetime_utc", "pair", "market", "direction", "event",
        "price", "quantity", "balance_change", "pnl", "balance_after", "session_id", "trade_id",
    ])
    for e in mgr.event_log():
        w.writerow([
            e.ts, datetime.fromtimestamp(e.ts / 1000, tz=timezone.utc).isoformat(),
            e.symbol, e.market.value, e.direction.value, e.event_type.value,
            e.price, e.quantity, e.cash_delta, e.realized_pnl_delta, e.balance_after,
            e.session_id or "", e.trade_id,
        ])
    return Response(
        content=buf.getvalue(), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=council_paper_trading_log.csv"},
    )


@router.get("/analytics", response_model=PerformanceAnalytics)
async def get_analytics(request: Request) -> PerformanceAnalytics:
    """Council performance: win rate, average return, best/worst trade, Sharpe,
    profit factor, per-agent accuracy, and Risk Manager veto success rate."""
    mgr = _mgr(request)
    await mgr.mark_to_market()
    sm = request.app.state.session_manager
    journal = request.app.state.journal

    async def lookup(session_id: str):
        if journal.enabled:
            entry = await journal.get(session_id)
            if entry is not None:
                return entry
        return sm.session_detail(session_id)

    vetoed = [s for s in sm.recent_sessions() if s.veto is not None]
    return await build_analytics(
        mgr.closed_positions(), lookup, vetoed, request.app.state.market_service
    )


@router.get("/trades/{trade_id}", response_model=TradeDetail)
async def get_trade_detail(request: Request, trade_id: str) -> TradeDetail:
    """Full explanation of one trade: outcome + PnL, plus the council session that
    produced it (market snapshot, debate, votes, confidence, decision)."""
    mgr = _mgr(request)
    await mgr.mark_to_market()
    t = mgr.get_trade(trade_id)
    if t is None:
        raise HTTPException(status_code=404, detail="trade not found")

    session = None
    if t.session_id:
        journal = request.app.state.journal
        if journal.enabled:
            session = await journal.get(t.session_id)
        if session is None:  # offline fallback: in-memory recent sessions
            session = request.app.state.session_manager.session_detail(t.session_id)

    return TradeDetail(trade=mgr.to_ledger_entry(t), session=session)


@router.get("/trades", response_model=list[PaperTrade])
async def get_trades(
    request: Request, limit: int = Query(default=50, ge=1, le=200)
) -> list[PaperTrade]:
    return await _mgr(request).list_trades(limit)


@router.post("/reset")
async def reset_portfolio(request: Request) -> dict:
    await request.app.state.paper_engine.reset()  # via engine so the update is broadcast
    return {"status": "reset", "startingBalance": _mgr(request).starting_balance}
