"""Journal tests: save → list → get round-trip against an in-memory Supabase fake.

Verifies the insert payload shapes and the row→domain-model reconstruction without
any network. A completed offline streaming round provides realistic data.
"""

from __future__ import annotations

import time

import httpx
import pytest

from app.config import Settings
from app.domain.enums import DataSource, Side
from app.domain.models import Ema, Indicators, Macd, MarketSnapshot
from app.services.council.graph import COMMITTEE_ORDER, default_agents
from app.services.council.session import LiveSession, run_streaming_round
from app.services.journal.service import JournalService
from app.services.llm.cadence import Cadence
from app.services.llm.client import LLMClient


class FakeSupabase:
    """Just enough PostgREST behavior for the journal's queries."""

    def __init__(self) -> None:
        self.tables: dict[str, list[dict]] = {
            "sessions": [],
            "messages": [],
            "votes": [],
            "recommendations": [],
        }

    async def insert(self, table, rows, *, upsert=False):
        rows = rows if isinstance(rows, list) else [rows]
        self.tables[table].extend(rows)

    async def select(self, table, params):
        rows = list(self.tables[table])
        for key in ("id", "session_id"):
            if key in params and params[key].startswith("eq."):
                want = params[key][3:]
                rows = [r for r in rows if str(r.get(key)) == want]
        if "order" in params and params["order"].startswith("ordinal"):
            rows.sort(key=lambda r: r.get("ordinal", 0))
        # Emulate the summary alias "session_id:id".
        if "select" in params and "session_id:id" in params["select"]:
            rows = [{**r, "session_id": r["id"]} for r in rows]
        if "limit" in params:
            rows = rows[: int(params["limit"])]
        return rows


def _snapshot() -> MarketSnapshot:
    return MarketSnapshot(
        symbol="BTCUSDT", price=67000, change24h=3.0, high24h=68340, low24h=65660,
        base_volume=1000, quote_volume=6.7e7, volatility=0.3,
        indicators=Indicators(rsi=60, macd=Macd(macd=50, signal=0, histogram=50),
                              ema=Ema(ema12=66800, ema26=66200, ema50=65500)),
        ts=int(time.time() * 1000), source=DataSource.BITGET,
    )


async def _completed_session() -> LiveSession:
    llm = LLMClient(httpx.AsyncClient(), Settings())
    session = LiveSession.new(_snapshot())

    async def emit(_):
        pass

    await run_streaming_round(
        session=session, agents=default_agents(), order=COMMITTEE_ORDER,
        llm=llm, cadence=Cadence(10_000),
        settings=Settings(cadence_tokens_per_sec=10_000, thinking_pause_sec=0.0), emit=emit,
    )
    return session


@pytest.mark.asyncio
async def test_disabled_journal_is_noop():
    j = JournalService(None)
    assert j.enabled is False
    assert await j.list() == []
    assert await j.get("whatever") is None


@pytest.mark.asyncio
async def test_save_then_list_and_get_roundtrip():
    fake = FakeSupabase()
    journal = JournalService(fake)
    session = await _completed_session()

    await journal.save(session.to_snapshot_event(), ended_at=int(time.time() * 1000))

    # Rows landed in every table.
    assert len(fake.tables["sessions"]) == 1
    assert len(fake.tables["messages"]) == 5
    assert len(fake.tables["votes"]) == 4
    assert len(fake.tables["recommendations"]) == 1

    # List summary.
    summaries = await journal.list()
    assert len(summaries) == 1
    assert summaries[0].session_id == session.session_id
    assert summaries[0].symbol == "BTCUSDT"

    # Full reconstruction.
    entry = await journal.get(session.session_id)
    assert entry is not None
    assert entry.symbol == "BTCUSDT"
    assert len(entry.messages) == 5
    assert [m.agent_id.value for m in entry.messages][0] == "technical"
    assert len(entry.votes) == 4
    assert entry.recommendation is not None
    assert entry.recommendation.side == Side.BUY
    assert entry.snapshot.symbol == "BTCUSDT"
    assert entry.confidence_breakdown is not None
    assert entry.confidence is not None


@pytest.mark.asyncio
async def test_message_ordinal_preserved_on_read():
    fake = FakeSupabase()
    journal = JournalService(fake)
    session = await _completed_session()
    await journal.save(session.to_snapshot_event(), ended_at=int(time.time() * 1000))

    entry = await journal.get(session.session_id)
    order = [m.agent_id.value for m in entry.messages]
    assert order == ["technical", "news", "quant", "risk", "execution"]
