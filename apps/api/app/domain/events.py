"""WebSocket event envelope — the wire contract.

A discriminated union keyed on `type`, mirrored in `shared-types/src/events.ts`.
Step 1 added market/connection events; Step 3 adds the full council + session set.
"""

from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import Field

from app.domain.enums import AgentId, ConnectionState, Stance
from app.domain.models import (
    AgentMessage,
    AgentProfile,
    ConfidenceBreakdown,
    MarketSnapshot,
    Recommendation,
    Vote,
    VetoInfo,
    _Base,
)


# ---- Market / connection (Step 1) ------------------------------------------
class MarketTickEvent(_Base):
    type: Literal["market.tick"] = "market.tick"
    snapshot: MarketSnapshot


class ConnectionStatusEvent(_Base):
    type: Literal["connection.status"] = "connection.status"
    state: ConnectionState
    detail: str | None = None


# ---- Session lifecycle (Step 3) --------------------------------------------
class SessionStartedEvent(_Base):
    type: Literal["session.started"] = "session.started"
    session_id: str
    symbol: str
    snapshot: MarketSnapshot
    started_at: int
    agents: list[AgentProfile]


class SessionSnapshotEvent(_Base):
    """Full current-session state sent to a client the moment it connects.
    This is what makes the session feel 'already running' with no empty state."""

    type: Literal["session.snapshot"] = "session.snapshot"
    session_id: str
    symbol: str
    snapshot: MarketSnapshot
    started_at: int
    phase: str
    agents: list[AgentProfile]
    messages: list[AgentMessage]
    votes: list[Vote]
    veto: VetoInfo | None = None
    confidence: float | None = None
    confidence_breakdown: ConfidenceBreakdown | None = None
    recommendation: Recommendation | None = None


class CouncilPhaseEvent(_Base):
    type: Literal["council.phase"] = "council.phase"
    phase: str


# ---- Agent activity (Step 3) -----------------------------------------------
class AgentThinkingEvent(_Base):
    type: Literal["agent.thinking"] = "agent.thinking"
    agent_id: AgentId


class AgentTokenEvent(_Base):
    type: Literal["agent.token"] = "agent.token"
    agent_id: AgentId
    message_id: str
    delta: str


class AgentMessageEvent(_Base):
    type: Literal["agent.message"] = "agent.message"
    message: AgentMessage


class DebateReferenceEvent(_Base):
    type: Literal["debate.reference"] = "debate.reference"
    from_agent: AgentId
    to_agents: list[AgentId]
    stance: Stance


# ---- Voting / decision (Step 3) --------------------------------------------
class VoteCastEvent(_Base):
    type: Literal["vote.cast"] = "vote.cast"
    vote: Vote


class CouncilConfidenceEvent(_Base):
    type: Literal["council.confidence"] = "council.confidence"
    score: float
    breakdown: ConfidenceBreakdown


class CouncilVetoEvent(_Base):
    type: Literal["council.veto"] = "council.veto"
    veto: VetoInfo


class CouncilRecommendationEvent(_Base):
    type: Literal["council.recommendation"] = "council.recommendation"
    recommendation: Recommendation


# The discriminated union. New event types append without breaking decoders.
WsEvent = Annotated[
    Union[
        MarketTickEvent,
        ConnectionStatusEvent,
        SessionStartedEvent,
        SessionSnapshotEvent,
        CouncilPhaseEvent,
        AgentThinkingEvent,
        AgentTokenEvent,
        AgentMessageEvent,
        DebateReferenceEvent,
        VoteCastEvent,
        CouncilConfidenceEvent,
        CouncilRecommendationEvent,
        CouncilVetoEvent,
    ],
    Field(discriminator="type"),
]
