"""Tests for the council orchestration: graph flow, voting, confidence, veto.

All run in OFFLINE mode (no API keys), so they're deterministic and network-free.
"""

from __future__ import annotations

import time

import httpx
import pytest

from app.config import get_settings
from app.domain.enums import AgentId, DataSource, Side
from app.domain.models import Ema, Indicators, Macd, MarketSnapshot
from app.services.council.confidence import compute_confidence
from app.services.council.graph import Council
from app.services.llm.client import LLMClient


def _snapshot(*, price, change, rsi, hist, ema12, ema26, ema50, vol) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTCUSDT", price=price, change24h=change, high24h=price * 1.02,
        low24h=price * 0.98, base_volume=1000.0, quote_volume=price * 1000,
        volatility=vol,
        indicators=Indicators(
            rsi=rsi, macd=Macd(macd=hist, signal=0.0, histogram=hist),
            ema=Ema(ema12=ema12, ema26=ema26, ema50=ema50),
        ),
        ts=int(time.time() * 1000), source=DataSource.BITGET,
    )


def _bullish() -> MarketSnapshot:
    return _snapshot(price=67000, change=3.0, rsi=60, hist=50,
                     ema12=66800, ema26=66200, ema50=65500, vol=0.3)


def _dangerous() -> MarketSnapshot:
    # High volatility + conflict (price up hard but trend stack down) -> risk veto.
    return _snapshot(price=50000, change=9.0, rsi=78, hist=-80,
                     ema12=51000, ema26=52000, ema50=53000, vol=1.6)


async def _council() -> Council:
    settings = get_settings()
    http = httpx.AsyncClient()
    llm = LLMClient(http, settings)
    assert llm.is_offline  # tests must not hit a network LLM
    return Council(llm)


@pytest.mark.asyncio
async def test_full_round_produces_complete_debate():
    council = await _council()
    result = await council.run_round(_bullish())

    # One message per agent, in committee order.
    assert len(result["messages"]) == 5
    assert [m.agent_id for m in result["messages"]] == [
        AgentId.TECHNICAL, AgentId.NEWS, AgentId.QUANT, AgentId.RISK, AgentId.EXECUTION
    ]
    # Four analysts vote; chairman does not.
    assert len(result["votes"]) == 4
    assert AgentId.EXECUTION not in {v.agent_id for v in result["votes"]}

    rec = result["recommendation"]
    assert rec.side == Side.BUY
    assert not rec.vetoed
    assert 0 <= rec.confidence <= 100
    assert result["phase"] == "decided"


@pytest.mark.asyncio
async def test_agents_reference_each_other():
    council = await _council()
    result = await council.run_round(_bullish())
    # At least one non-opening message references a prior agent.
    assert any(m.references for m in result["messages"][1:])


@pytest.mark.asyncio
async def test_risk_veto_blocks_trade():
    council = await _council()
    result = await council.run_round(_dangerous())

    assert result["veto"] is not None
    assert result["veto"].by_agent == AgentId.RISK
    assert result["veto"].risk_score >= 0.8
    assert len(result["veto"].factors) >= 2  # detailed, structured reasoning
    assert any("volatility" in f.lower() for f in result["veto"].factors)
    rec = result["recommendation"]
    assert rec.vetoed is True
    assert rec.side == Side.HOLD
    assert result["phase"] == "blocked"


def test_confidence_unanimous_beats_split():
    from app.domain.models import Vote

    snap = _bullish()
    unanimous = [Vote(agent_id=a, side=Side.BUY, rationale="")
                 for a in (AgentId.TECHNICAL, AgentId.NEWS, AgentId.QUANT)]
    split = [
        Vote(agent_id=AgentId.TECHNICAL, side=Side.BUY, rationale=""),
        Vote(agent_id=AgentId.NEWS, side=Side.SELL, rationale=""),
        Vote(agent_id=AgentId.QUANT, side=Side.HOLD, rationale=""),
    ]
    c_unanimous, _ = compute_confidence(snap, unanimous, 0.2, 0.5, False)
    c_split, _ = compute_confidence(snap, split, 0.2, 0.5, False)
    assert c_unanimous > c_split


def test_confidence_veto_caps_score():
    from app.domain.models import Vote

    snap = _bullish()
    votes = [Vote(agent_id=AgentId.TECHNICAL, side=Side.BUY, rationale="")]
    no_veto, _ = compute_confidence(snap, votes, 0.2, 0.5, False)
    with_veto, _ = compute_confidence(snap, votes, 0.2, 0.5, True)
    assert with_veto < no_veto


# ---- Voting engine: consensus tally ----------------------------------------
def test_vote_tally_consensus_and_split():
    from app.domain.models import Vote
    from app.services.council.voting import compute_tally

    unanimous = compute_tally([Vote(agent_id=a, side=Side.BUY, rationale="")
                               for a in (AgentId.TECHNICAL, AgentId.NEWS, AgentId.QUANT, AgentId.RISK)])
    assert unanimous.leading == Side.BUY
    assert unanimous.ratio == 1.0
    assert unanimous.reached is True
    assert unanimous.label == "consensus"

    split = compute_tally([
        Vote(agent_id=AgentId.TECHNICAL, side=Side.BUY, rationale=""),
        Vote(agent_id=AgentId.NEWS, side=Side.SELL, rationale=""),
        Vote(agent_id=AgentId.QUANT, side=Side.HOLD, rationale=""),
    ])
    assert split.reached is False
    assert split.label == "split"


def test_vote_tally_empty_defaults_hold():
    from app.services.council.voting import compute_tally

    vt = compute_tally([])
    assert vt.total == 0 and vt.leading == Side.HOLD and not vt.reached


@pytest.mark.asyncio
async def test_recommendation_carries_consensus():
    council = await _council()
    result = await council.run_round(_bullish())
    rec = result["recommendation"]
    assert 0.0 <= rec.consensus_ratio <= 1.0
    # Bullish snapshot -> all four analysts BUY -> consensus reached.
    assert rec.consensus_reached is True
    assert rec.consensus_ratio == 1.0


def test_veto_overrides_unanimous_votes():
    """Risk Manager overrides ALL agents: even a unanimous BUY is blocked to HOLD."""
    from app.domain.models import Vote, VetoInfo
    from app.services.council.state import CouncilState
    from app.services.council.voting import tally

    snap = _bullish()
    votes = [Vote(agent_id=a, side=Side.BUY, rationale="")
             for a in (AgentId.TECHNICAL, AgentId.NEWS, AgentId.QUANT, AgentId.RISK)]
    state = CouncilState(
        session_id="s", symbol="BTCUSDT", snapshot=snap, votes=votes,
        veto=VetoInfo(by_agent=AgentId.RISK, reason="too dangerous", risk_score=0.9,
                      factors=["extreme volatility"]),
    )
    result = tally(state)
    assert result["recommendation"].side == Side.HOLD     # overridden despite 4×BUY
    assert result["recommendation"].vetoed is True
    assert result["phase"] == "blocked"


@pytest.mark.asyncio
async def test_risk_manager_vetoes_a_trap():
    """A bull trap (rising momentum into a downtrend, overbought RSI) is vetoed even
    without extreme volatility — the Risk Manager is dangerous."""
    council = await _council()
    trap = _snapshot(price=50000, change=8.0, rsi=80, hist=-60,
                     ema12=51000, ema26=52000, ema50=53000, vol=0.5)  # elevated, not extreme
    result = await council.run_round(trap)
    assert result["veto"] is not None
    assert any("trap" in f.lower() for f in result["veto"].factors)
    assert result["recommendation"].side == Side.HOLD
    assert result["phase"] == "blocked"
