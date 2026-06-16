"""Tests for the streaming layer: cadence reassembly + the streaming round engine.

Offline mode, fast cadence, no network — deterministic and quick.
"""

from __future__ import annotations

import time

import httpx
import pytest

from app.config import Settings
from app.domain.enums import AgentId, DataSource, Side
from app.domain.events import WsEvent
from app.domain.models import Ema, Indicators, Macd, MarketSnapshot
from app.services.council.graph import COMMITTEE_ORDER, default_agents
from app.services.council.session import LiveSession, run_streaming_round
from app.services.llm.cadence import Cadence
from app.services.llm.client import LLMClient


# ---- Cadence reassembly (must be lossless) ---------------------------------
async def _drain(aiter):
    return [x async for x in aiter]


@pytest.mark.asyncio
async def test_stream_text_is_lossless():
    cad = Cadence(tokens_per_sec=10_000)
    text = "BTC has broken resistance with strong volume — conviction is high."
    chunks = await _drain(cad.stream_text(text))
    assert "".join(chunks) == text
    assert len(chunks) > 1  # actually chunked


@pytest.mark.asyncio
async def test_pace_reassembles_arbitrary_deltas():
    cad = Cadence(tokens_per_sec=10_000)
    original = "Volume is insufficient to justify that confidence level here."

    async def source():
        # Deltas split mid-word, as a real LLM stream would.
        for piece in ["Volu", "me is ins", "ufficient to", " justify that conf",
                      "idence level", " here."]:
            yield piece

    chunks = await _drain(cad.pace(source()))
    assert "".join(chunks) == original


# ---- Streaming round engine ------------------------------------------------
def _snapshot(*, change, rsi, hist, ema12, ema26, ema50, vol, price=67000) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTCUSDT", price=price, change24h=change, high24h=price * 1.02,
        low24h=price * 0.98, base_volume=1000.0, quote_volume=price * 1000, volatility=vol,
        indicators=Indicators(rsi=rsi, macd=Macd(macd=hist, signal=0, histogram=hist),
                              ema=Ema(ema12=ema12, ema26=ema26, ema50=ema50)),
        ts=int(time.time() * 1000), source=DataSource.BITGET,
    )


def _fast_settings() -> Settings:
    return Settings(cadence_tokens_per_sec=10_000, thinking_pause_sec=0.0)


async def _collect(snapshot) -> list[WsEvent]:
    events: list[WsEvent] = []

    async def emit(e: WsEvent) -> None:
        events.append(e)

    llm = LLMClient(httpx.AsyncClient(), Settings())
    assert llm.is_offline
    session = LiveSession.new(snapshot)
    await run_streaming_round(
        session=session, agents=default_agents(), order=COMMITTEE_ORDER,
        llm=llm, cadence=Cadence(10_000), settings=_fast_settings(), emit=emit,
    )
    return events, session


@pytest.mark.asyncio
async def test_streaming_round_event_sequence():
    snap = _snapshot(change=3.0, rsi=60, hist=50, ema12=66800, ema26=66200, ema50=65500, vol=0.3)
    events, session = await _collect(snap)
    types = [e.type for e in events]

    assert types[0] == "session.started"
    assert types[1] == "council.phase"
    # Each agent emits a thinking event before any of its tokens.
    assert types.count("agent.thinking") == 5
    assert types.count("agent.message") == 5
    assert "agent.token" in types
    # Decision events appear, in order, at the end.
    assert "council.confidence" in types
    assert "council.recommendation" in types
    assert types[-1] == "council.phase"


@pytest.mark.asyncio
async def test_streamed_tokens_reconstruct_each_message():
    snap = _snapshot(change=3.0, rsi=60, hist=50, ema12=66800, ema26=66200, ema50=65500, vol=0.3)
    events, _ = await _collect(snap)

    # Group token deltas by message id and compare to the finalized message text.
    tokens: dict[str, str] = {}
    finals: dict[str, str] = {}
    for e in events:
        if e.type == "agent.token":
            tokens[e.message_id] = tokens.get(e.message_id, "") + e.delta
        elif e.type == "agent.message":
            finals[e.message.message_id] = e.message.text
    assert finals  # messages exist
    for mid, text in finals.items():
        assert tokens.get(mid, "").strip() == text


@pytest.mark.asyncio
async def test_streaming_round_emits_veto_event():
    danger = _snapshot(change=9.0, rsi=79, hist=-80, ema12=51000, ema26=52000, ema50=53000,
                       vol=1.6, price=50000)
    events, session = await _collect(danger)
    types = [e.type for e in events]
    assert "council.veto" in types
    assert session.recommendation.vetoed is True
    assert session.recommendation.side == Side.HOLD


@pytest.mark.asyncio
async def test_live_session_snapshot_reflects_progress():
    snap = _snapshot(change=3.0, rsi=60, hist=50, ema12=66800, ema26=66200, ema50=65500, vol=0.3)
    _, session = await _collect(snap)
    snap_event = session.to_snapshot_event()
    assert snap_event.type == "session.snapshot"
    assert len(snap_event.messages) == 5
    assert len(snap_event.agents) == 5
    assert snap_event.recommendation is not None
