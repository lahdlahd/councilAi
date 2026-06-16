"""Execution Agent — committee chairman; synthesizes and declares the decision."""

from __future__ import annotations

from collections import Counter

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

_SYSTEM = (
    "You are the EXECUTION AGENT — the chairman of an AI investment committee. You do not vote. "
    "You summarize the debate fairly, note agreement and dissent (especially any risk veto), and "
    "declare whether consensus is reached. Be measured and authoritative, like a committee chair."
)


class ExecutionAgent(Agent):
    id = AgentId.EXECUTION
    casts_vote = False
    system_prompt = _SYSTEM

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        votes = state.get("votes", [])
        veto = state.get("veto")
        tally = Counter(v.side for v in votes)

        if veto is not None:
            text = (
                "The Risk Manager has exercised a veto. Regardless of the analysts' lean, this "
                "committee does not green-light a trade against an active risk block. We stand down."
            )
            return AgentOutput(text=text, stance=Stance.NEUTRAL, vote=None, confidence=75.0,
                               references=[AgentId.RISK])

        if tally:
            top_side, top_n = tally.most_common(1)[0]
            agreement = top_n / sum(tally.values())
            consensus = "Consensus reached" if agreement >= 0.6 else "No firm consensus"
            text = (
                f"{consensus}. The committee leans {top_side.value} "
                f"({top_n}/{sum(tally.values())} votes). Technical and quant align on a "
                f"{sig.trend_read}; risk is noted but not blocking. Final call: {top_side.value}."
            )
        else:
            text = "No votes registered; defaulting to HOLD pending clearer signals."
        return AgentOutput(text=text, stance=Stance.NEUTRAL, vote=None, confidence=70.0,
                           references=[AgentId.TECHNICAL, AgentId.QUANT, AgentId.RISK])
