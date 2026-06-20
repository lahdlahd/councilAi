"""Debate dynamics — the logic that turns five reports into a committee argument.

Two ideas:

1. **Specialty leans.** Each agent reads the SAME signal through its own lens, so
   they genuinely diverge: the Technical Analyst follows structure/trend, the News
   Analyst chases momentum/sentiment, the Quant fades RSI extremes (mean reversion),
   and the Risk Manager de-risks when volatility is up. A momentum spike into a
   downtrend, for instance, splits the room.

2. **Reaction.** Given who has already spoken (and how they voted), an agent picks
   whom to address and whether it agrees, disagrees, or directly challenges them —
   so messages reference each other instead of standing alone.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.enums import AgentId, Side, Stance
from app.domain.models import MarketSnapshot
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

AGENT_NAME: dict[AgentId, str] = {
    AgentId.TECHNICAL: "Technical Analyst",
    AgentId.NEWS: "News Analyst",
    AgentId.QUANT: "Quant Analyst",
    AgentId.RISK: "Risk Manager",
    AgentId.EXECUTION: "Execution Agent",
}


def _side(score: float, thresh: float = 0.2) -> Side:
    if score > thresh:
        return Side.BUY
    if score < -thresh:
        return Side.SELL
    return Side.HOLD


def specialty_side(agent_id: AgentId, sig: Signal, snap: MarketSnapshot) -> Side:
    """Each agent's directional lean, viewed through its specialty (they can differ)."""
    ind = snap.indicators

    if agent_id is AgentId.TECHNICAL:
        # Structure & trend dominate; momentum is a minor tilt.
        score = 0.0
        if ind is not None:
            score += {"uptrend": 0.6, "downtrend": -0.6, "ranging": 0.0}[sig.trend_read]
            score += {"bullish": 0.4, "bearish": -0.4, "flat": 0.0}[sig.macd_read]
        score += max(-0.3, min(0.3, snap.change24h / 20))
        return _side(score, 0.2)

    if agent_id is AgentId.NEWS:
        # Momentum / sentiment chaser — can diverge from structure.
        return _side(sig.sentiment, 0.15)

    if agent_id is AgentId.QUANT:
        # Mean reversion: fade RSI extremes; otherwise follow the net bias.
        if ind is not None and ind.rsi >= 70:
            return Side.SELL
        if ind is not None and ind.rsi <= 30:
            return Side.BUY
        return _side(sig.bias, 0.2)

    if agent_id is AgentId.RISK:
        # De-risk when volatility/risk is elevated, regardless of direction.
        if sig.risk_score >= 0.55 or sig.volatility_level == "high":
            return Side.HOLD
        if abs(sig.bias) >= 0.3:
            return _side(sig.bias, 0.2)
        return Side.HOLD

    return Side.HOLD


def prior_sides(state: CouncilState) -> list[tuple[AgentId, Side]]:
    """Who has voted so far, and which way (order preserved)."""
    return [(v.agent_id, v.side) for v in state.get("votes", [])]


@dataclass
class Reaction:
    stance: Stance
    references: list[AgentId] = field(default_factory=list)
    addressee: AgentId | None = None
    addressee_side: Side | None = None


def react(my_side: Side, priors: list[tuple[AgentId, Side]]) -> Reaction:
    """Decide how to relate to the debate so far: open, agree, disagree, or challenge."""
    if not priors:
        return Reaction(Stance.OPENING)

    disagree = [(a, s) for a, s in priors if s != my_side]
    agree = [(a, s) for a, s in priors if s == my_side]

    if disagree:
        a, s = disagree[-1]  # address the most recent dissenter
        stance = Stance.CHALLENGE if {my_side, s} == {Side.BUY, Side.SELL} else Stance.DISAGREE
        refs = [a] + ([agree[-1][0]] if agree else [])
        return Reaction(stance, refs, a, s)

    a, s = agree[-1]
    return Reaction(Stance.AGREE, [a], a, s)


def name(agent_id: AgentId) -> str:
    return AGENT_NAME.get(agent_id, agent_id.value)
