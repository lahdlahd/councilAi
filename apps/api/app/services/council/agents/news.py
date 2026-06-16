"""News Analyst — fast-moving information hunter; reads sentiment & momentum.

Note: this agent does NOT fabricate headlines. With no live news feed wired yet,
it reasons about market-implied sentiment from real momentum/trend, and is honest
that it's reading the tape rather than citing specific articles. A real news/ETF
feed can be slotted in later behind the same interface.
"""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

_SYSTEM = (
    "You are the NEWS ANALYST on an AI investment committee. You hunt for what the market is "
    "feeling: sentiment, ETF flows, macro tone. You move fast and react to the technical read "
    "just given. You have no specific live headlines right now, so reason from market-implied "
    "sentiment and momentum — and be honest about that. Reference the Technical Analyst."
)


class NewsAnalyst(Agent):
    id = AgentId.NEWS
    casts_vote = True
    system_prompt = _SYSTEM

    def _extra_schema(self) -> str:
        return ' Also include "sentiment" (-1..1).'

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        snap = state["snapshot"]
        tone = "risk-on" if sig.sentiment > 0.15 else "risk-off" if sig.sentiment < -0.15 else "mixed"
        side = Side.BUY if sig.sentiment > 0.2 else Side.SELL if sig.sentiment < -0.2 else Side.HOLD
        text = (
            f"No fresh headlines crossing, but the tape on {snap.symbol} feels {tone}: "
            f"{snap.change24h:+.2f}% on the day and a {sig.momentum_read} momentum read. "
            f"That backs the technical picture — I lean {side.value}."
        )
        return AgentOutput(
            text=text, stance=Stance.AGREE if side != Side.HOLD else Stance.NEUTRAL,
            vote=side, confidence=round(45 + abs(sig.sentiment) * 40, 1),
            references=[AgentId.TECHNICAL], sentiment=sig.sentiment,
        )
