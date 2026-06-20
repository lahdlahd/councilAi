"""News Analyst — momentum/sentiment chaser; reacts to the technical read.

Does NOT fabricate headlines: with no live news feed wired yet, it reasons from
market-implied sentiment (real momentum/trend) and is honest about that. Because it
weighs momentum heavily, it can openly disagree with a structure-driven read.
"""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.debate import name, prior_sides, react, specialty_side
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

_SYSTEM = (
    "You are the NEWS ANALYST on an AI investment committee. You hunt for what the market is "
    "FEELING: sentiment, ETF flows, macro tone, momentum. You move fast. You have no specific "
    "live headlines right now, so reason from market-implied sentiment — and be honest about it. "
    "React to whoever spoke before you BY NAME: agree if the tape supports them, but push back "
    "openly when momentum tells a different story than their chart."
)


class NewsAnalyst(Agent):
    id = AgentId.NEWS
    casts_vote = True
    system_prompt = _SYSTEM

    def _extra_schema(self) -> str:
        return ' Also include "sentiment" (-1..1).'

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        snap = state["snapshot"]
        my_side = specialty_side(AgentId.NEWS, sig, snap)
        r = react(my_side, prior_sides(state))
        tone = "risk-on" if sig.sentiment > 0.15 else "risk-off" if sig.sentiment < -0.15 else "mixed"

        if r.stance in (Stance.DISAGREE, Stance.CHALLENGE) and r.addressee is not None:
            text = (
                f"I have to push back on the {name(r.addressee)}, who reads "
                f"{r.addressee_side.value if r.addressee_side else 'neutral'}. The tape on "
                f"{snap.symbol} feels {tone} — {snap.change24h:+.2f}% with {sig.momentum_read} "
                f"momentum. Sentiment leads price here; I lean {my_side.value}."
            )
        elif r.stance is Stance.AGREE and r.addressee is not None:
            text = (
                f"That backs the {name(r.addressee)}: the tape is {tone}, {snap.change24h:+.2f}% on "
                f"the day with {sig.momentum_read} momentum. I'm with it — {my_side.value}."
            )
        else:
            text = (
                f"No fresh headlines, but {snap.symbol} feels {tone}: {snap.change24h:+.2f}% and "
                f"{sig.momentum_read} momentum. I lean {my_side.value}."
            )

        return AgentOutput(
            text=text, stance=r.stance, vote=my_side,
            confidence=round(45 + abs(sig.sentiment) * 40, 1),
            references=r.references or [AgentId.TECHNICAL], sentiment=sig.sentiment,
        )
