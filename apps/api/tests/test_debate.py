"""Debate-dynamics tests: genuine disagreement, cross-references, and defense.

All offline/deterministic. Validates the committee actually argues rather than
filing five independent reports.
"""

from __future__ import annotations

import random
import time

import httpx
import pytest

from app.config import Settings
from app.domain.enums import AgentId, DataSource, Stance
from app.domain.models import Ema, Indicators, Macd, MarketSnapshot
from app.services.council.graph import COMMITTEE_ORDER, default_agents
from app.services.council.session import LiveSession, run_streaming_round
from app.services.llm.cadence import Cadence
from app.services.llm.client import LLMClient


def _fast() -> Settings:
    return Settings(cadence_tokens_per_sec=10_000, thinking_pause_sec=0.0, vote_reveal_pause_sec=0.0)


async def _run(snap: MarketSnapshot) -> LiveSession:
    llm = LLMClient(httpx.AsyncClient(), Settings())
    assert llm.is_offline
    session = LiveSession.new(snap)

    async def emit(_e):  # discard events; we inspect the session
        return None

    await run_streaming_round(
        session=session, agents=default_agents(), order=COMMITTEE_ORDER,
        llm=llm, cadence=Cadence(10_000), settings=_fast(), emit=emit,
    )
    return session


def _rand_snapshot(rng: random.Random) -> MarketSnapshot:
    price = rng.uniform(100, 70_000)
    return MarketSnapshot(
        symbol="TESTUSDT", price=price, change24h=rng.uniform(-10, 10),
        high24h=price * 1.05, low24h=price * 0.95, base_volume=1000.0,
        quote_volume=price * 1000, volatility=rng.uniform(0.0, 2.0),
        indicators=Indicators(
            rsi=rng.uniform(10, 90),
            macd=Macd(macd=rng.uniform(-100, 100), signal=0.0, histogram=rng.uniform(-100, 100)),
            ema=Ema(
                ema12=price * (1 + rng.uniform(-0.03, 0.03)),
                ema26=price * (1 + rng.uniform(-0.03, 0.03)),
                ema50=price * (1 + rng.uniform(-0.03, 0.03)),
            ),
        ),
        ts=int(time.time() * 1000), source=DataSource.BITGET,
    )


def _has_disagreement(session: LiveSession) -> bool:
    sides = {v.side for v in session.votes}
    return len(sides) >= 2 or session.veto is not None


@pytest.mark.asyncio
async def test_disagreement_rate_at_least_30_percent():
    # Uses the non-streaming graph path (same votes, no cadence) so the statistical
    # check over many sessions stays fast.
    from app.services.council.graph import Council

    council = Council(LLMClient(httpx.AsyncClient(), Settings()))
    rng = random.Random(7)
    n = 200
    disagreed = 0
    for _ in range(n):
        result = await council.run_round(_rand_snapshot(rng))
        sides = {v.side for v in result["votes"]}
        if len(sides) >= 2 or result["veto"] is not None:
            disagreed += 1
    rate = disagreed / n
    assert rate >= 0.30, f"disagreement rate {rate:.0%} is below the 30% requirement"


def _divergent() -> MarketSnapshot:
    # Momentum spiking up into a confirmed downtrend with stretched RSI: the room splits.
    price = 50_000
    return MarketSnapshot(
        symbol="BTCUSDT", price=price, change24h=9.0, high24h=price * 1.05,
        low24h=price * 0.95, base_volume=1000.0, quote_volume=price * 1000, volatility=0.5,
        indicators=Indicators(
            rsi=78, macd=Macd(macd=-80, signal=0, histogram=-80),
            ema=Ema(ema12=51_000, ema26=52_000, ema50=53_000),
        ),
        ts=int(time.time() * 1000), source=DataSource.BITGET,
    )


@pytest.mark.asyncio
async def test_committee_argues_and_defends():
    session = await _run(_divergent())

    # Genuine disagreement happened.
    assert _has_disagreement(session)
    assert any(
        m.stance in (Stance.DISAGREE, Stance.CHALLENGE) for m in session.messages
    ), "expected at least one disagreeing/challenging statement"

    # Agents reference each other by id.
    assert any(m.references for m in session.messages[1:])

    # A rebuttal pass ran: at least one agent spoke more than once (opening + defense),
    # and that defense references the colleague who challenged them.
    spoke_twice = [
        a for a in {m.agent_id for m in session.messages}
        if sum(1 for m in session.messages if m.agent_id == a) > 1
    ]
    assert spoke_twice, "expected at least one agent to defend (speak twice)"
    for a in spoke_twice:
        defense = [m for m in session.messages if m.agent_id == a][-1]
        assert defense.references, "a defense should reference the challenger"
