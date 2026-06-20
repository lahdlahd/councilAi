"""Technical Analyst — chart-obsessed; opens the debate on price structure."""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.debate import specialty_side
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

_SYSTEM = (
    "You are the TECHNICAL ANALYST on an AI investment committee. You are obsessed with "
    "charts and price structure: RSI, MACD, EMA stacks, volume, support/resistance. You "
    "speak in precise technical terms and always ground claims in the indicators provided. "
    "You open the debate, so state a clear directional thesis others can react to or contest. "
    "If a colleague later challenges you, you defend your read with the chart."
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
        side = specialty_side(AgentId.TECHNICAL, sig, snap)
        text = (
            f"Opening read on {snap.symbol}: RSI(14) {ind.rsi} ({sig.rsi_read}), MACD histogram "
            f"{ind.macd.histogram} ({sig.macd_read}), price {snap.price} vs EMA50 {ind.ema.ema50} "
            f"— that's a {sig.trend_read}. Structure points {side.value}; I'll defend that."
        )
        conf = 55 + abs(sig.bias) * 35
        return AgentOutput(text=text, stance=Stance.OPENING, vote=side, confidence=round(conf, 1))
