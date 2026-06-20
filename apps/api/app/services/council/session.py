"""On-demand council sessions + streaming debate runner.

The council is IDLE until a user convenes it (no auto-run). `SessionManager.start`
runs exactly one streaming round for a chosen symbol + market, guarded so only one
runs at a time, broadcasting events every connected client receives.

`run_streaming_round` drives the five agents in committee order. Each agent's full
reasoning comes from `agent.deliberate()` — which uses the real LLM when a key is
configured (driving the message AND the vote/stance/veto), or the deterministic
offline reasoner otherwise. The resulting message text is streamed word-by-word
through the Cadence controller so it reads as live thinking.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.config import Settings
from app.domain.enums import AgentId, MarketType, Stance
from app.domain.events import (
    AgentMessageEvent,
    AgentThinkingEvent,
    AgentTokenEvent,
    CouncilConfidenceEvent,
    CouncilPhaseEvent,
    CouncilRecommendationEvent,
    CouncilVetoEvent,
    DebateReferenceEvent,
    SessionSnapshotEvent,
    SessionStartedEvent,
    VoteCastEvent,
    WsEvent,
)
from app.domain.models import (
    AgentMessage,
    ConfidenceBreakdown,
    JournalEntry,
    MarketSnapshot,
    Recommendation,
    VetoInfo,
    Vote,
)
from app.services.council.agents.base import AGENT_PROFILES, Agent
from app.services.council.graph import Council
from app.services.council.state import CouncilState
from app.services.council.voting import tally
from app.services.hub.broadcaster import Broadcaster
from app.services.llm.cadence import Cadence
from app.services.market.service import MarketService
from app.utils.logging import get_logger

log = get_logger("council.session")

Emit = Callable[[WsEvent], Awaitable[None]]


@dataclass
class LiveSession:
    session_id: str
    symbol: str
    market: MarketType
    snapshot: MarketSnapshot
    started_at: int
    phase: str = "debating"
    messages: list[AgentMessage] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)
    veto: VetoInfo | None = None
    risk_score: float | None = None
    sentiment: float | None = None
    confidence: float | None = None
    confidence_breakdown: ConfidenceBreakdown | None = None
    recommendation: Recommendation | None = None

    @classmethod
    def new(cls, snapshot: MarketSnapshot) -> "LiveSession":
        return cls(
            session_id=f"sess-{uuid.uuid4().hex[:10]}",
            symbol=snapshot.symbol,
            market=snapshot.market,
            snapshot=snapshot,
            started_at=int(time.time() * 1000),
        )

    def council_state(self) -> CouncilState:
        return CouncilState(
            session_id=self.session_id, symbol=self.symbol, snapshot=self.snapshot,
            messages=list(self.messages), votes=list(self.votes), veto=self.veto,
            risk_score=self.risk_score, sentiment=self.sentiment,
            confidence=self.confidence, confidence_breakdown=self.confidence_breakdown,
            recommendation=self.recommendation,
        )

    def to_snapshot_event(self) -> SessionSnapshotEvent:
        return SessionSnapshotEvent(
            session_id=self.session_id, symbol=self.symbol, snapshot=self.snapshot,
            started_at=self.started_at, phase=self.phase,
            agents=list(AGENT_PROFILES.values()), messages=list(self.messages),
            votes=list(self.votes), veto=self.veto, confidence=self.confidence,
            confidence_breakdown=self.confidence_breakdown, recommendation=self.recommendation,
        )


async def _emit_statement(
    agent_id: AgentId, agent: Agent, out, session: LiveSession,
    cadence: Cadence, emit: Emit, *, allow_vote: bool,
) -> None:
    """Stream one agent statement and fold its outcome into the session."""
    message_id = f"{agent_id.value}-{uuid.uuid4().hex[:8]}"
    acc = ""
    async for delta in cadence.stream_text(out.text):
        acc += delta
        await emit(AgentTokenEvent(agent_id=agent_id, message_id=message_id, delta=delta))
    final_text = acc.strip() or out.text

    message = AgentMessage(
        message_id=message_id, agent_id=agent_id, text=final_text,
        stance=out.stance, references=out.references, confidence=out.confidence,
        ts=int(time.time() * 1000),
    )
    session.messages.append(message)
    await emit(AgentMessageEvent(message=message))

    if out.references:
        await emit(DebateReferenceEvent(
            from_agent=agent_id, to_agents=out.references, stance=out.stance))
    if out.risk_score is not None:
        session.risk_score = out.risk_score
    if out.sentiment is not None:
        session.sentiment = out.sentiment
    if out.veto and session.veto is None:
        session.veto = VetoInfo(
            by_agent=agent_id, reason=out.veto_reason or final_text,
            risk_score=out.risk_score or 0.0, factors=out.veto_factors,
        )
        await emit(CouncilVetoEvent(veto=session.veto))
    if allow_vote and agent.casts_vote and out.vote is not None:
        # Record the vote now (so later speakers can react to it), but the visible
        # roll-call is deferred to the dedicated voting phase after the debate.
        session.votes.append(Vote(agent_id=agent_id, side=out.vote, rationale=final_text[:200]))


def _challenges(session: LiveSession, agents: dict[AgentId, Agent]) -> dict[AgentId, AgentId]:
    """Map each challenged (voting) agent -> the first colleague who disagreed with them."""
    out: dict[AgentId, AgentId] = {}
    for m in session.messages:
        if m.stance in (Stance.DISAGREE, Stance.CHALLENGE):
            for ref in m.references:
                a = agents.get(ref)
                if ref != m.agent_id and a is not None and a.casts_vote:
                    out.setdefault(ref, m.agent_id)
    return out


async def run_streaming_round(
    session: LiveSession, agents: dict[AgentId, Agent], order: list[AgentId],
    llm, cadence: Cadence, settings: Settings, emit: Emit,
) -> None:
    await emit(SessionStartedEvent(
        session_id=session.session_id, symbol=session.symbol, snapshot=session.snapshot,
        started_at=session.started_at, agents=list(AGENT_PROFILES.values()),
    ))
    session.phase = "debating"
    await emit(CouncilPhaseEvent(phase=session.phase))

    opening = [a for a in order if agents[a].casts_vote]
    chairs = [a for a in order if not agents[a].casts_vote]

    async def think(agent_id: AgentId) -> None:
        await emit(AgentThinkingEvent(agent_id=agent_id))
        await asyncio.sleep(settings.thinking_pause_sec)

    # 1) Opening statements — each forms a specialty lean and reacts to those before it.
    for agent_id in opening:
        await think(agent_id)
        out = await agents[agent_id].deliberate(session.council_state(), llm)
        await _emit_statement(agent_id, agents[agent_id], out, session, cadence, emit, allow_vote=True)

    # 2) Rebuttal pass — challenged agents defend their position (true back-and-forth).
    challenged = _challenges(session, agents)
    for agent_id in [a for a in opening if a in challenged][: settings.max_rebuttals]:
        await think(agent_id)
        out = await agents[agent_id].rebut(session.council_state(), llm, challenged[agent_id])
        await _emit_statement(agent_id, agents[agent_id], out, session, cadence, emit, allow_vote=False)

    # 3) VOTING PHASE — debate is over; each analyst now formally casts BUY/SELL/HOLD.
    session.phase = "voting"
    await emit(CouncilPhaseEvent(phase=session.phase))
    for vote in session.votes:
        await emit(VoteCastEvent(vote=vote))
        await asyncio.sleep(settings.vote_reveal_pause_sec)

    # 4) Council result (confidence + consensus) is computed before the chairman speaks.
    result = tally(session.council_state())
    session.recommendation = result["recommendation"]
    session.confidence = result["confidence"]
    session.confidence_breakdown = result["confidence_breakdown"]
    session.phase = result["phase"]

    # 5) Chairman synthesizes: summary + confidence + recommendation + rationale.
    for agent_id in chairs:
        await think(agent_id)
        out = await agents[agent_id].deliberate(session.council_state(), llm)
        await _emit_statement(agent_id, agents[agent_id], out, session, cadence, emit, allow_vote=False)

    # 6) Reveal the dials/cards after the chairman's verdict.
    await emit(CouncilConfidenceEvent(score=session.confidence, breakdown=session.confidence_breakdown))
    await emit(CouncilRecommendationEvent(recommendation=session.recommendation))
    await emit(CouncilPhaseEvent(phase=session.phase))


class SessionManager:
    """Runs council rounds ON DEMAND and exposes the current/last session snapshot."""

    def __init__(
        self, settings: Settings, broadcaster: Broadcaster, market_service: MarketService,
        council: Council, cadence: Cadence, journal=None, paper_engine=None,
    ) -> None:
        self._settings = settings
        self._hub = broadcaster
        self._market = market_service
        self._council = council
        self._cadence = cadence
        self._journal = journal
        self._paper_engine = paper_engine
        self._live: LiveSession | None = None
        self._lock = asyncio.Lock()
        # Recent finished sessions, kept in memory so Trade Details works even
        # without Supabase (capped ring).
        self._recent: "OrderedDict[str, SessionSnapshotEvent]" = OrderedDict()

    @property
    def current(self) -> LiveSession | None:
        return self._live

    @property
    def running(self) -> bool:
        return self._lock.locked()

    def snapshot_event(self) -> SessionSnapshotEvent | None:
        return self._live.to_snapshot_event() if self._live else None

    def session_detail(self, session_id: str) -> JournalEntry | None:
        """Build a JournalEntry from the in-memory cache (offline fallback for
        the Trade Details page when Supabase isn't configured)."""
        ev = self._recent.get(session_id)
        return self._to_entry(ev) if ev is not None else None

    def recent_sessions(self) -> list[JournalEntry]:
        """All cached finished sessions (newest last) — used by analytics."""
        return [self._to_entry(ev) for ev in self._recent.values()]

    @staticmethod
    def _to_entry(ev: SessionSnapshotEvent) -> JournalEntry:
        return JournalEntry(
            session_id=ev.session_id, symbol=ev.symbol, started_at=ev.started_at,
            ended_at=None, phase=ev.phase, snapshot=ev.snapshot, messages=ev.messages,
            votes=ev.votes, veto=ev.veto, confidence=ev.confidence,
            confidence_breakdown=ev.confidence_breakdown, recommendation=ev.recommendation,
        )

    async def start(self, symbol: str, market: MarketType, trade_config=None) -> dict:
        """Convene the council on a symbol+market. One round; rejects if already running."""
        if self._lock.locked():
            return {"status": "busy", "session": self._live.session_id if self._live else None}
        # Kick off in the background so the HTTP request returns immediately.
        asyncio.create_task(self._run(symbol, market, trade_config))
        return {"status": "started", "symbol": symbol, "market": market.value}

    async def _run(self, symbol: str, market: MarketType, trade_config=None) -> None:
        from app.services.council.graph import COMMITTEE_ORDER

        async with self._lock:
            try:
                snapshot = await self._market.get_snapshot(symbol, market)
                self._live = LiveSession.new(snapshot)
                await run_streaming_round(
                    session=self._live, agents=self._council.agents, order=COMMITTEE_ORDER,
                    llm=self._council.llm, cadence=self._cadence, settings=self._settings,
                    emit=self._hub.publish,
                )
                if self._journal is not None and self._journal.enabled:
                    await self._journal.save(
                        self._live.to_snapshot_event(), ended_at=int(time.time() * 1000))

                # Paper Trade Execution (Prompt 3): the final decision becomes a
                # simulated trade — BUY -> long, SELL -> short, HOLD/veto -> none.
                if self._paper_engine is not None:
                    await self._paper_engine.on_recommendation(
                        self._live.recommendation, self._live.snapshot, self._live.session_id,
                        trade_config=trade_config,
                    )

                # Retain the finished session for the Trade Details page (offline-safe).
                self._recent[self._live.session_id] = self._live.to_snapshot_event()
                while len(self._recent) > 50:
                    self._recent.popitem(last=False)
            except Exception as exc:  # noqa: BLE001
                log.warning("council round failed for %s/%s: %s", symbol, market.value, exc)
