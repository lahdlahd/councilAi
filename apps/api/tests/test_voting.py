"""Voting-layer tests: votes are cast AFTER the debate, with confidence + consensus."""

from __future__ import annotations

import time

import httpx
import pytest

from app.config import Settings
from app.domain.enums import AgentId, DataSource, Side
from app.domain.models import Ema, Indicators, Macd, MarketSnapshot
from app.services.council.graph import COMMITTEE_ORDER, default_agents
from app.services.council.session import LiveSession, run_streaming_round
from app.services.llm.cadence import Cadence
from app.services.llm.client import LLMClient


def _fast() -> Settings:
    return Settings(cadence_tokens_per_sec=10_000, thinking_pause_sec=0.0, vote_reveal_pause_sec=0.0)


def _snap(**k) -> MarketSnapshot:
    p = k.get("price", 67000)
    return MarketSnapshot(
        symbol="BTCUSDT", price=p, change24h=k["change"], high24h=p * 1.02, low24h=p * 0.98,
        base_volume=1000.0, quote_volume=p * 1000, volatility=k["vol"],
        indicators=Indicators(rsi=k["rsi"], macd=Macd(macd=k["hist"], signal=0, histogram=k["hist"]),
                              ema=Ema(ema12=k["e12"], ema26=k["e26"], ema50=k["e50"])),
        ts=int(time.time() * 1000), source=DataSource.BITGET,
    )


async def _collect(snap):
    events = []

    async def emit(e):
        events.append(e)

    llm = LLMClient(httpx.AsyncClient(), Settings())
    session = LiveSession.new(snap)
    await run_streaming_round(session=session, agents=default_agents(), order=COMMITTEE_ORDER,
                             llm=llm, cadence=Cadence(10_000), settings=_fast(), emit=emit)
    return events, session


@pytest.mark.asyncio
async def test_each_analyst_votes_after_debate():
    snap = _snap(change=3, rsi=60, hist=50, e12=66800, e26=66200, e50=65500, vol=0.3)
    events, session = await _collect(snap)

    votes = [e for e in events if e.type == "vote.cast"]
    # Exactly the four analysts vote; the chairman does not.
    assert len(votes) == 4
    voters = {e.vote.agent_id for e in votes}
    assert voters == {AgentId.TECHNICAL, AgentId.NEWS, AgentId.QUANT, AgentId.RISK}
    assert AgentId.EXECUTION not in voters
    for e in votes:
        assert e.vote.side in (Side.BUY, Side.SELL, Side.HOLD)

    # Voting happens AFTER the debate: every analyst's message precedes the first vote.
    first_vote_idx = next(i for i, e in enumerate(events) if e.type == "vote.cast")
    analyst_msg_idx = [
        i for i, e in enumerate(events)
        if e.type == "agent.message" and e.message.agent_id != AgentId.EXECUTION
    ]
    assert max(analyst_msg_idx) < first_vote_idx


@pytest.mark.asyncio
async def test_voting_layer_emits_confidence_and_consensus():
    snap = _snap(change=3, rsi=60, hist=50, e12=66800, e26=66200, e50=65500, vol=0.3)
    events, session = await _collect(snap)

    conf = [e for e in events if e.type == "council.confidence"]
    rec = [e for e in events if e.type == "council.recommendation"]
    assert conf and 0 <= conf[0].score <= 100              # confidence percentage
    assert rec and rec[0].recommendation.side == Side.BUY  # final recommendation
    # Consensus is reported (ratio + reached flag).
    assert 0.0 <= rec[0].recommendation.consensus_ratio <= 1.0
    assert rec[0].recommendation.consensus_reached is True  # unanimous bullish


@pytest.mark.asyncio
async def test_split_vote_reports_no_consensus():
    # Momentum up into a downtrend with stretched RSI -> a split room.
    snap = _snap(change=9, rsi=78, hist=-80, e12=51000, e26=52000, e50=53000, vol=0.5, price=50000)
    events, session = await _collect(snap)
    rec = [e for e in events if e.type == "council.recommendation"][0].recommendation
    sides = {e.vote.side for e in events if e.type == "vote.cast"}
    assert len(sides) >= 2               # genuinely split
    assert rec.consensus_reached is False
