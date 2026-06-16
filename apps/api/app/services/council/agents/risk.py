"""Risk Manager — paranoid, skeptical; can VETO trades on excessive risk."""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

# Veto when realized volatility makes the setup uninvestable on a risk-adjusted basis.
_VETO_RISK_THRESHOLD = 0.8

_SYSTEM = (
    "You are the RISK MANAGER on an AI investment committee. You are paranoid and skeptical and "
    "your job is to protect capital: drawdown, volatility, exposure, liquidity. You challenge "
    "optimism from the other agents. You CAN VETO a trade if risk is unacceptable. Only veto "
    "when genuinely warranted (extreme volatility or dangerous conflict in signals)."
)


class RiskManager(Agent):
    id = AgentId.RISK
    casts_vote = True
    system_prompt = _SYSTEM

    def _extra_schema(self) -> str:
        return (
            ' Also include "risk_score" (0..1, higher = more dangerous), '
            '"veto" (true/false), and "veto_reason" (string or null).'
        )

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        snap = state["snapshot"]
        veto = sig.risk_score >= _VETO_RISK_THRESHOLD
        if veto:
            factors = [
                f"Realized volatility {snap.volatility:.2f}% ({sig.volatility_level})",
                f"Risk score {sig.risk_score:.2f} exceeds the {_VETO_RISK_THRESHOLD:.2f} block threshold",
            ]
            # Name the specific signal conflict, when present.
            if sig.momentum_read == "rising" and sig.trend_read == "downtrend":
                factors.append("Conflict: momentum rising into a confirmed downtrend")
            elif sig.momentum_read == "falling" and sig.trend_read == "uptrend":
                factors.append("Conflict: momentum falling against an uptrend")
            if snap.indicators and snap.indicators.rsi >= 75:
                factors.append(f"RSI {snap.indicators.rsi} is overbought")
            elif snap.indicators and snap.indicators.rsi <= 25:
                factors.append(f"RSI {snap.indicators.rsi} is oversold and unstable")

            text = (
                f"I'm vetoing. Realized volatility on {snap.symbol} is {snap.volatility:.2f}% "
                f"({sig.volatility_level}) and the signals are in conflict — risk score "
                f"{sig.risk_score:.2f}. That is not a risk-adjusted entry. Capital preservation first."
            )
            return AgentOutput(
                text=text, stance=Stance.CHALLENGE, vote=Side.HOLD, confidence=80.0,
                references=[AgentId.TECHNICAL, AgentId.QUANT],
                veto=True, veto_reason=text, veto_factors=factors, risk_score=sig.risk_score,
            )
        # No veto, but temper conviction.
        cautious = Side.HOLD if abs(sig.bias) < 0.3 else sig.side()
        text = (
            f"Volatility is {sig.volatility_level} ({snap.volatility:.2f}%), risk score "
            f"{sig.risk_score:.2f}. I won't block it, but size it down — I'd only commit to "
            f"{cautious.value} with tight invalidation."
        )
        return AgentOutput(
            text=text, stance=Stance.DISAGREE if cautious == Side.HOLD else Stance.NEUTRAL,
            vote=cautious, confidence=round(55 + (1 - sig.risk_score) * 25, 1),
            references=[AgentId.QUANT], risk_score=sig.risk_score,
        )
