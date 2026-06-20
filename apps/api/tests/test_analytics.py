"""Council Performance Analytics — trade metrics, agent accuracy, veto success."""

from __future__ import annotations

import pytest

from app.domain.enums import AgentId, MarketType, Side, TradeDirection, TradeStatus
from app.domain.models import PaperTrade, Vote
from app.services.paper.analytics import (
    agent_accuracy, majority_side, trade_metrics, trade_return_pct,
    veto_was_successful, winning_side,
)


def _closed(entry, exit_, qty=1.0, direction=TradeDirection.LONG, symbol="BTCUSDT"):
    realized = (exit_ - entry) * qty if direction is TradeDirection.LONG else (entry - exit_) * qty
    return PaperTrade(
        id=f"t-{symbol}-{entry}-{exit_}", session_id="s", symbol=symbol, market=MarketType.SPOT,
        direction=direction, quantity=qty, entry_price=entry, exit_price=exit_,
        status=TradeStatus.CLOSED, realized_pnl=realized, opened_at=1, closed_at=2,
    )


def test_trade_return_pct():
    t = _closed(100, 110, qty=1)  # +10 on 100 cost
    assert trade_return_pct(t) == pytest.approx(10.0)


def test_metrics_win_rate_avg_best_worst_profit_factor():
    closed = [_closed(100, 110), _closed(100, 90), _closed(100, 130)]  # +10%, -10%, +30%
    m = trade_metrics(closed)
    assert m["sample_size"] == 3
    assert m["win_rate"] == pytest.approx(round(2 / 3 * 100, 1))
    assert m["avg_return_pct"] == pytest.approx(10.0)        # (10-10+30)/3
    assert m["best"].return_pct == pytest.approx(30.0)
    assert m["worst"].return_pct == pytest.approx(-10.0)
    # profit factor = (10+30)/10 = 4
    assert m["profit_factor"] == pytest.approx(4.0)


def test_sharpe_none_with_one_trade_value_with_many():
    assert trade_metrics([_closed(100, 110)])["sharpe"] is None
    m = trade_metrics([_closed(100, 110), _closed(100, 90), _closed(100, 120)])
    assert m["sharpe"] is not None


def test_profit_factor_none_without_losses():
    assert trade_metrics([_closed(100, 110), _closed(100, 120)])["profit_factor"] is None


def test_winning_side():
    assert winning_side(_closed(100, 110)) is Side.BUY
    assert winning_side(_closed(100, 90)) is Side.SELL


def test_agent_accuracy_directional_only():
    votes = [
        Vote(agent_id=AgentId.TECHNICAL, side=Side.BUY, rationale=""),
        Vote(agent_id=AgentId.NEWS, side=Side.SELL, rationale=""),
        Vote(agent_id=AgentId.QUANT, side=Side.HOLD, rationale=""),  # excluded
    ]
    # market rose -> BUY was correct
    accs = {a.agent_id: a for a in agent_accuracy([(votes, Side.BUY)])}
    assert accs[AgentId.TECHNICAL].accuracy == 100.0
    assert accs[AgentId.NEWS].accuracy == 0.0
    assert accs[AgentId.QUANT].total == 0          # HOLD excluded from denominator


def test_majority_side_ignores_hold():
    votes = [
        Vote(agent_id=AgentId.TECHNICAL, side=Side.SELL, rationale=""),
        Vote(agent_id=AgentId.NEWS, side=Side.SELL, rationale=""),
        Vote(agent_id=AgentId.QUANT, side=Side.BUY, rationale=""),
        Vote(agent_id=AgentId.RISK, side=Side.HOLD, rationale=""),
    ]
    assert majority_side(votes) is Side.SELL


def test_veto_success_logic():
    # would-be long, price fell -> veto saved a loss -> success
    assert veto_was_successful(Side.BUY, entry=100, current=95) is True
    # would-be long, price rose -> veto cost us -> not success
    assert veto_was_successful(Side.BUY, entry=100, current=105) is False
    # would-be short, price rose -> veto saved a loss -> success
    assert veto_was_successful(Side.SELL, entry=100, current=105) is True
