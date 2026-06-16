"""Technical Analyst — chart-obsessed; speaks in RSI/MACD/EMA/levels."""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

_SYSTEM = (
    "You are the TECHNICAL ANALYST on an AI investment committee. You are obsessed with "
    "charts and price structure: RSI, MACD, EMA stacks, volume, support/resistance. You "
    "speak in precise technical terms and always ground claims in the indicators provided. "
    "You open the debate. Be confident but specific."
)


class TechnicalAnalyst(Agent):
    id = AgentId.TECHNICAL
    casts_vote = True
    system_prompt = _SYSTEM

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        snap = state["snapshot"]
        ind = snap.indicators
        if ind is None:
            return AgentOutput(
                text=f"No clean indicator read on {snap.symbol}; price {snap.price} on "
                f"{snap.change24h:+.2f}% — I want candles before committing.",
                stance=Stance.OPENING, vote=Side.HOLD, confidence=35.0,
            )
        side = sig.side()
        text = (
            f"RSI(14) at {ind.rsi} reads {sig.rsi_read}; MACD histogram {ind.macd.histogram} is "
            f"{sig.macd_read}. Price {snap.price} vs EMA50 {ind.ema.ema50} confirms a "
            f"{sig.trend_read}. The structure points {side.value}."
        )
        conf = 55 + abs(sig.bias) * 35
        return AgentOutput(
            text=text, stance=Stance.OPENING, vote=side, confidence=round(conf, 1),
        )
