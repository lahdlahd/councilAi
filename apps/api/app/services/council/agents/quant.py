"""Quant Analyst — cold, mathematical; fades extremes, speaks in probabilities."""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.debate import name, prior_sides, react, specialty_side
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

_SYSTEM = (
    "You are the QUANT ANALYST on an AI investment committee. You are cold and mathematical: you "
    "translate the setup into probabilities and expected edge, citing indicator confluence. You "
    "are a mean-reversion thinker — you FADE stretched RSI even when the trend looks strong, so "
    "you will sometimes contradict the Technical or News read. Name the colleague whose odds you "
    "dispute, and quantify why."
)


class QuantAnalyst(Agent):
    id = AgentId.QUANT
    casts_vote = True
    system_prompt = _SYSTEM

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        snap = state["snapshot"]
        ind = snap.indicators
        my_side = specialty_side(AgentId.QUANT, sig, snap)
        r = react(my_side, prior_sides(state))

        prob = round(50 + abs(sig.bias) * 18, 1)  # conviction proxy
        fading = ind is not None and (ind.rsi >= 70 or ind.rsi <= 30)
        edge = "thin" if abs(sig.bias) < 0.25 and not fading else "meaningful"
        fade_note = (
            f" RSI {ind.rsi} is stretched, so I fade it — mean reversion, not momentum."
            if fading and ind is not None else ""
        )

        if r.stance in (Stance.DISAGREE, Stance.CHALLENGE) and r.addressee is not None:
            text = (
                f"The {name(r.addressee)} leans "
                f"{r.addressee_side.value if r.addressee_side else 'neutral'}, but the numbers "
                f"disagree: net bias {sig.bias:+.2f}, ~{prob}% conviction.{fade_note} The odds say "
                f"{my_side.value}; edge is {edge}."
            )
        elif r.stance is Stance.AGREE and r.addressee is not None:
            text = (
                f"The math aligns with the {name(r.addressee)}: net bias {sig.bias:+.2f}, ~{prob}% "
                f"conviction.{fade_note} {my_side.value}, edge {edge}."
            )
        else:
            text = (
                f"Net bias {sig.bias:+.2f}, ~{prob}% conviction.{fade_note} I read {my_side.value}, "
                f"edge {edge}."
            )

        return AgentOutput(
            text=text, stance=r.stance, vote=my_side,
            confidence=round(40 + abs(sig.bias) * 45, 1),
            references=r.references or [AgentId.TECHNICAL, AgentId.NEWS],
        )
