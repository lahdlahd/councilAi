"""CouncilState — the LangGraph state object threaded through every node.

List fields use additive reducers so each agent node simply returns the new
items it produced; LangGraph merges them onto the accumulating debate. Scalar
fields (recommendation, confidence, veto, phase) are overwritten by the node
that owns them (tally / risk).
"""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.domain.models import (
    AgentMessage,
    ConfidenceBreakdown,
    MarketSnapshot,
    Recommendation,
    Vote,
    VetoInfo,
)


class CouncilState(TypedDict, total=False):
    # Seeded at session start
    session_id: str
    symbol: str
    snapshot: MarketSnapshot

    # Accumulated through the debate (additive reducers)
    messages: Annotated[list[AgentMessage], operator.add]
    votes: Annotated[list[Vote], operator.add]

    # Owned/overwritten by specific nodes
    veto: VetoInfo | None
    risk_score: float | None       # emitted by Risk Manager
    sentiment: float | None        # emitted by News Analyst
    confidence: float | None
    confidence_breakdown: ConfidenceBreakdown | None
    recommendation: Recommendation | None
    phase: str


def initial_state(session_id: str, snapshot: MarketSnapshot) -> CouncilState:
    return CouncilState(
        session_id=session_id,
        symbol=snapshot.symbol,
        snapshot=snapshot,
        messages=[],
        votes=[],
        veto=None,
        confidence=None,
        confidence_breakdown=None,
        recommendation=None,
        phase="debating",
    )


def transcript(state: CouncilState) -> str:
    """Render the debate so far for prompt context (lets agents reference peers)."""
    msgs = state.get("messages", [])
    if not msgs:
        return "(no prior statements — you open the session)"
    lines = []
    for m in msgs:
        lines.append(f"[{m.agent_id.value.upper()}] ({m.stance.value}): {m.text}")
    return "\n".join(lines)
