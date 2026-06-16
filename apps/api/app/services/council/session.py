"""Ambient session manager + streaming debate runner.

This is the heartbeat of the live experience:

  * `LiveSession`     — in-memory state of the current round, so a client that
                        connects mid-debate gets an accurate `session.snapshot`.
  * `run_streaming_round` — drives the five agents in committee order, emitting
                        thinking → token → message → vote events, then tally →
                        confidence → veto → recommendation. Token text is streamed
                        through the Cadence controller.
  * `SessionManager`  — runs rounds back-to-back forever (the "already running"
                        session), feeding the broadcaster every client subscribes to.

Design note: the streamed PROSE comes from the LLM (so the debate sounds human),
but each agent's vote/stance/veto/sentiment is derived deterministically from the
real market signal — decisions stay grounded and explainable, never hallucinated.
The same agent objects, voting, and confidence engine from Step 2 are reused; only
the traversal is unrolled here to allow per-token streaming the linear graph can't.
"""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from app.config import Settings
from app.domain.enums import AgentId
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
    MarketSnapshot,
    Recommendation,
    Vote,
    VetoInfo,
)
from app.services.council.agents.base import AGENT_PROFILES, Agent
from app.services.council.graph import Council
from app.services.council.signal import read_signal
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
    """Mutable snapshot of the round currently in progress (for late joiners)."""

    session_id: str
    symbol: str
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
    def new(cls, snapshot: MarketSnapshot) -> LiveSession:
        return cls(
            session_id=f"sess-{uuid.uuid4().hex[:10]}",
            symbol=snapshot.symbol,
            snapshot=snapshot,
            started_at=int(time.time() * 1000),
        )

    def council_state(self) -> CouncilState:
        return CouncilState(
            session_id=self.session_id,
            symbol=self.symbol,
            snapshot=self.snapshot,
            messages=list(self.messages),
            votes=list(self.votes),
            veto=self.veto,
            risk_score=self.risk_score,
            sentiment=self.sentiment,
        )

    def to_snapshot_event(self) -> SessionSnapshotEvent:
        return SessionSnapshotEvent(
            session_id=self.session_id,
            symbol=self.symbol,
            snapshot=self.snapshot,
            started_at=self.started_at,
            phase=self.phase,
            agents=list(AGENT_PROFILES.values()),
            messages=list(self.messages),
            votes=list(self.votes),
            veto=self.veto,
            confidence=self.confidence,
            confidence_breakdown=self.confidence_breakdown,
            recommendation=self.recommendation,
        )


async def run_streaming_round(
    session: LiveSession,
    agents: dict[AgentId, Agent],
    order: list[AgentId],
    llm,
    cadence: Cadence,
    settings: Settings,
    emit: Emit,
) -> None:
    snap = session.snapshot
    sig = read_signal(snap)

    await emit(
        SessionStartedEvent(
            session_id=session.session_id,
            symbol=session.symbol,
            snapshot=snap,
            started_at=session.started_at,
            agents=list(AGENT_PROFILES.values()),
        )
    )
    session.phase = "debating"
    await emit(CouncilPhaseEvent(phase=session.phase))

    for agent_id in order:
        agent = agents[agent_id]
        # Deterministic structured read (vote/stance/refs/veto/sentiment + fallback text).
        structured = agent._offline(session.council_state(), sig)
        message_id = f"{agent_id.value}-{uuid.uuid4().hex[:8]}"

        await emit(AgentThinkingEvent(agent_id=agent_id))
        await asyncio.sleep(settings.thinking_pause_sec)

        # Stream the prose: LLM tokens if available, else the deterministic text.
        if llm.is_offline:
            token_source = cadence.stream_text(structured.text)
        else:
            sys_p, usr_p = agent.prose_prompt(session.council_state())
            try:
                token_source = cadence.pace(llm.astream(system=sys_p, user=usr_p))
            except Exception as exc:  # noqa: BLE001
                log.warning("stream failed for %s (%s); using offline text", agent_id.value, exc)
                token_source = cadence.stream_text(structured.text)

        acc = ""
        async for delta in token_source:
            acc += delta
            await emit(AgentTokenEvent(agent_id=agent_id, message_id=message_id, delta=delta))

        final_text = acc.strip() or structured.text
        message = AgentMessage(
            message_id=message_id,
            agent_id=agent_id,
            text=final_text,
            stance=structured.stance,
            references=structured.references,
            confidence=structured.confidence,
            ts=int(time.time() * 1000),
        )
        session.messages.append(message)
        await emit(AgentMessageEvent(message=message))

        if structured.references:
            await emit(
                DebateReferenceEvent(
                    from_agent=agent_id,
                    to_agents=structured.references,
                    stance=structured.stance,
                )
            )

        # Record deterministic readings into the live session.
        if structured.risk_score is not None:
            session.risk_score = structured.risk_score
        if structured.sentiment is not None:
            session.sentiment = structured.sentiment
        if structured.veto:
            session.veto = VetoInfo(
                by_agent=agent_id,
                reason=structured.veto_reason or final_text,
                risk_score=structured.risk_score or 0.0,
                factors=structured.veto_factors,
            )
            await emit(CouncilVetoEvent(veto=session.veto))

        if agent.casts_vote and structured.vote is not None:
            vote = Vote(agent_id=agent_id, side=structured.vote, rationale=final_text[:200])
            session.votes.append(vote)
            await emit(VoteCastEvent(vote=vote))

    # ---- Tally / finalize ---------------------------------------------------
    session.phase = "voting"
    await emit(CouncilPhaseEvent(phase=session.phase))
    await asyncio.sleep(0.4)

    result = tally(session.council_state())
    session.recommendation = result["recommendation"]
    session.confidence = result["confidence"]
    session.confidence_breakdown = result["confidence_breakdown"]
    session.phase = result["phase"]

    await emit(
        CouncilConfidenceEvent(score=session.confidence, breakdown=session.confidence_breakdown)
    )
    await emit(CouncilRecommendationEvent(recommendation=session.recommendation))
    await emit(CouncilPhaseEvent(phase=session.phase))


class SessionManager:
    """Runs council rounds continuously and exposes the current session snapshot."""

    def __init__(
        self,
        settings: Settings,
        broadcaster: Broadcaster,
        market_service: MarketService,
        council: Council,
        cadence: Cadence,
        journal=None,
    ) -> None:
        self._settings = settings
        self._hub = broadcaster
        self._market = market_service
        self._council = council
        self._cadence = cadence
        self._journal = journal
        self._stop = asyncio.Event()
        self._live: LiveSession | None = None
        self._symbol = settings.council_symbol  # the active subject (user-selectable)

    @property
    def symbol(self) -> str:
        return self._symbol

    def set_symbol(self, symbol: str) -> None:
        """Switch the council's subject. Takes effect on the next round."""
        self._symbol = symbol
        log.info("council subject set to %s (applies next round)", symbol)

    @property
    def current(self) -> LiveSession | None:
        return self._live

    def snapshot_event(self) -> SessionSnapshotEvent | None:
        return self._live.to_snapshot_event() if self._live else None

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        from app.services.council.graph import COMMITTEE_ORDER

        log.info("ambient council session loop starting on %s", self._settings.council_symbol)
        while not self._stop.is_set():
            try:
                snapshot = await self._market.get_snapshot(self._symbol)
                self._live = LiveSession.new(snapshot)
                await run_streaming_round(
                    session=self._live,
                    agents=self._council.agents,
                    order=COMMITTEE_ORDER,
                    llm=self._council.llm,
                    cadence=self._cadence,
                    settings=self._settings,
                    emit=self._hub.publish,
                )
                # Auto-save the completed round (vetoed rounds included).
                if self._journal is not None and self._journal.enabled:
                    await self._journal.save(
                        self._live.to_snapshot_event(), ended_at=int(time.time() * 1000)
                    )
                await asyncio.sleep(self._settings.council_round_interval_sec)
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # noqa: BLE001 - keep the loop alive across failures
                log.warning("council round failed: %s — retrying soon", exc)
                await asyncio.sleep(3.0)
