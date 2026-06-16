"""Quant Analyst — cold, mathematical; speaks in probabilities."""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

_SYSTEM = (
    "You are the QUANT ANALYST on an AI investment committee. You are cold and mathematical. "
    "You translate the setup into probabilities and expected edge, citing the indicator "
    "confluence. No emotion, no narrative — just the numbers and the odds. React to peers."
)


class QuantAnalyst(Agent):
    id = AgentId.QUANT
    casts_vote = True
    system_prompt = _SYSTEM

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        # Map net bias magnitude to a directional success probability.
        prob = round(50 + sig.bias * 18, 1)  # ~32%..68%
        side = sig.side()
        directional = "upside" if side == Side.BUY else "downside" if side == Side.SELL else "neutral"
        text = (
            f"Confluence of RSI/MACD/trend yields a net bias of {sig.bias:+.2f}. I model the "
            f"{directional} scenario at ~{prob if side != Side.SELL else round(100 - prob, 1)}% "
            f"over the near term. Edge is {'thin' if abs(sig.bias) < 0.25 else 'meaningful'}."
        )
        stance = Stance.AGREE if abs(sig.bias) >= 0.25 else Stance.CHALLENGE
        return AgentOutput(
            text=text, stance=stance, vote=side,
            confidence=round(40 + abs(sig.bias) * 45, 1),
            references=[AgentId.TECHNICAL, AgentId.NEWS],
        )
