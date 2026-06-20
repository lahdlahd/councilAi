"""Council Performance Analytics.

Trade-based metrics (win rate, average return, best/worst, Sharpe, profit factor)
are derived from closed paper trades. Vote-based metrics (agent accuracy, Risk
Manager veto success) are derived from the council sessions that produced them.

The core is pure functions (fully unit-testable); `build_analytics` is a thin async
orchestrator that gathers sessions and live prices.

Notes:
  * Sharpe is a simplified per-trade ratio (risk-free 0, not annualized).
  * Agent accuracy measures whether an agent's directional vote matched the market's
    actual move after the decision (HOLD/abstentions excluded).
  * Veto success asks: had the vetoed trade been taken, would it have lost? Evaluated
    against the current live price; vetoes we can't price are skipped.
"""

from __future__ import annotations

import statistics
from collections.abc import Awaitable, Callable

from app.domain.enums import AgentId, Side, TradeDirection
from app.domain.models import (
    AgentAccuracy,
    JournalEntry,
    PaperTrade,
    PerformanceAnalytics,
    TradeRef,
    Vote,
)
from app.services.market.service import MarketService
from app.utils.logging import get_logger

log = get_logger("paper.analytics")

VOTING_AGENTS = [AgentId.TECHNICAL, AgentId.NEWS, AgentId.QUANT, AgentId.RISK]


def trade_return_pct(t: PaperTrade) -> float:
    cost = t.quantity * t.entry_price
    return (t.realized_pnl / cost * 100.0) if cost else 0.0


def _ref(t: PaperTrade) -> TradeRef:
    return TradeRef(
        trade_id=t.id, symbol=t.symbol, direction=t.direction,
        return_pct=round(trade_return_pct(t), 4), pnl_usd=round(t.realized_pnl, 6),
        session_id=t.session_id,
    )


def trade_metrics(closed: list[PaperTrade]) -> dict:
    n = len(closed)
    if n == 0:
        return {
            "sample_size": 0, "win_rate": 0.0, "avg_return_pct": 0.0,
            "best": None, "worst": None, "sharpe": None, "profit_factor": None,
        }
    rets = [trade_return_pct(t) for t in closed]
    wins = sum(1 for t in closed if t.realized_pnl > 0)
    gross_profit = sum(t.realized_pnl for t in closed if t.realized_pnl > 0)
    gross_loss = abs(sum(t.realized_pnl for t in closed if t.realized_pnl < 0))

    sharpe = None
    if n >= 2:
        sd = statistics.stdev(rets)
        if sd > 0:
            sharpe = statistics.mean(rets) / sd

    return {
        "sample_size": n,
        "win_rate": round(wins / n * 100, 1),
        "avg_return_pct": round(sum(rets) / n, 4),
        "best": _ref(max(closed, key=trade_return_pct)),
        "worst": _ref(min(closed, key=trade_return_pct)),
        "sharpe": round(sharpe, 3) if sharpe is not None else None,
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
    }


def winning_side(t: PaperTrade) -> Side | None:
    """Which directional call the market rewarded between entry and exit."""
    if t.exit_price is None or t.exit_price == t.entry_price:
        return None
    return Side.BUY if t.exit_price > t.entry_price else Side.SELL


def agent_accuracy(pairs: list[tuple[list[Vote], Side | None]]) -> list[AgentAccuracy]:
    agg: dict[AgentId, list[int]] = {a: [0, 0] for a in VOTING_AGENTS}  # [correct, total]
    for votes, win in pairs:
        if win is None:
            continue
        for v in votes:
            if v.agent_id not in agg or v.side is Side.HOLD:
                continue
            agg[v.agent_id][1] += 1
            if v.side is win:
                agg[v.agent_id][0] += 1
    return [
        AgentAccuracy(
            agent_id=a, correct=c, total=tot,
            accuracy=round(c / tot * 100, 1) if tot else 0.0,
        )
        for a, (c, tot) in agg.items()
    ]


def majority_side(votes: list[Vote]) -> Side | None:
    counts: dict[Side, int] = {}
    for v in votes:
        if v.side is Side.HOLD:
            continue
        counts[v.side] = counts.get(v.side, 0) + 1
    return max(counts, key=lambda s: counts[s]) if counts else None


def veto_was_successful(would_be: Side, entry: float, current: float) -> bool:
    """True if the blocked trade would have lost (so the veto saved money)."""
    if would_be is Side.BUY:        # would-be long: loses if price didn't rise
        return current <= entry
    return current >= entry          # would-be short: loses if price didn't fall


async def build_analytics(
    closed_trades: list[PaperTrade],
    sessions_lookup: Callable[[str], Awaitable[JournalEntry | None]],
    vetoed_sessions: list[JournalEntry],
    market_service: MarketService | None,
) -> PerformanceAnalytics:
    tm = trade_metrics(closed_trades)

    # Agent accuracy — pair each resolved trade's session votes with the market move.
    pairs: list[tuple[list[Vote], Side | None]] = []
    for t in closed_trades:
        if not t.session_id:
            continue
        s = await sessions_lookup(t.session_id)
        if s is not None:
            pairs.append((s.votes, winning_side(t)))
    accs = agent_accuracy(pairs)

    # Risk Manager veto success — would the blocked trade have lost?
    results: list[bool] = []
    veto_count = 0
    for s in vetoed_sessions:
        if s.veto is None:
            continue
        veto_count += 1
        would_be = majority_side(s.votes)
        if would_be is None or market_service is None:
            continue
        try:
            snap = await market_service.get_snapshot(s.symbol, s.snapshot.market)
        except Exception as exc:  # noqa: BLE001 - can't price -> skip this veto
            log.debug("veto eval skipped for %s: %s", s.symbol, exc)
            continue
        results.append(veto_was_successful(would_be, s.snapshot.price, snap.price))

    rate = (sum(results) / len(results) * 100) if results else None

    return PerformanceAnalytics(
        sample_size=tm["sample_size"], win_rate=tm["win_rate"],
        avg_return_pct=tm["avg_return_pct"], best_trade=tm["best"], worst_trade=tm["worst"],
        sharpe_ratio=tm["sharpe"], profit_factor=tm["profit_factor"],
        agent_accuracy=accs, veto_success_rate=round(rate, 1) if rate is not None else None,
        veto_count=veto_count, veto_evaluated=len(results),
    )
