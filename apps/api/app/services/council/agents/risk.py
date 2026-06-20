"""Risk Manager — paranoid, skeptical; challenges optimism and can VETO."""

from __future__ import annotations

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.debate import name, prior_sides, react, specialty_side
from app.services.council.signal import Signal
from app.services.council.state import CouncilState

# Veto when realized volatility makes the setup uninvestable on a risk-adjusted basis.
_VETO_RISK_THRESHOLD = 0.8

_SYSTEM = (
    "You are the RISK MANAGER on an AI investment committee. You are paranoid and skeptical; your "
    "job is to protect capital — drawdown, volatility, exposure, liquidity. You actively CHALLENGE "
    "optimism from the other agents by name. You CAN VETO a trade when risk is unacceptable "
    "(extreme volatility or dangerous signal conflict). Only veto when genuinely warranted."
)


class RiskManager(Agent):
    id = AgentId.RISK
    casts_vote = True
    system_prompt = _SYSTEM

    def _extra_schema(self) -> str:
        return (
            ' Also include "risk_score" (0..1, higher = more dangerous), '
            '"veto" (true/false), "veto_reason" (string or null), and '
            '"veto_factors" (array of short strings naming the specific risks, or []).'
        )

    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        snap = state["snapshot"]
        priors = prior_sides(state)
        ind = snap.indicators
        rsi = ind.rsi if ind is not None else 50.0

        # The Risk Manager is dangerous: it vetoes on extreme risk OR on classic
        # trap setups — momentum luring the committee against a confirmed trend.
        bull_trap = sig.momentum_read == "rising" and sig.trend_read == "downtrend" and rsi >= 68
        bear_trap = sig.momentum_read == "falling" and sig.trend_read == "uptrend" and rsi <= 32
        severe_conflict = (bull_trap or bear_trap) and sig.volatility_level != "low"

        if sig.risk_score >= _VETO_RISK_THRESHOLD or severe_conflict:
            factors = [f"Realized volatility {snap.volatility:.2f}% ({sig.volatility_level})"]
            if sig.risk_score >= _VETO_RISK_THRESHOLD:
                factors.append(
                    f"Risk score {sig.risk_score:.2f} exceeds the {_VETO_RISK_THRESHOLD:.2f} block threshold"
                )
            if bull_trap:
                factors.append(f"Bull trap: rising momentum into a confirmed downtrend, RSI {rsi:.0f} overbought")
            if bear_trap:
                factors.append(f"Bear trap: falling momentum against an uptrend, RSI {rsi:.0f} oversold")
            if not bull_trap and not bear_trap:
                if snap.indicators and rsi >= 75:
                    factors.append(f"RSI {rsi:.0f} is overbought")
                elif snap.indicators and rsi <= 25:
                    factors.append(f"RSI {rsi:.0f} is oversold and unstable")

            bulls = [name(a) for a, s in priors if s != Side.HOLD] or ["the committee"]
            trap = " This is a textbook trap." if (bull_trap or bear_trap) else ""
            text = (
                f"I'm overruling {', '.join(bulls)}. Realized volatility on {snap.symbol} is "
                f"{snap.volatility:.2f}% ({sig.volatility_level}); risk score {sig.risk_score:.2f}.{trap} "
                f"This is not a risk-adjusted entry. I VETO — capital preservation first."
            )
            refs = [a for a, s in priors if s != Side.HOLD] or [AgentId.TECHNICAL, AgentId.QUANT]
            return AgentOutput(
                text=text, stance=Stance.CHALLENGE, vote=Side.HOLD, confidence=84.0,
                references=refs, veto=True, veto_reason=text, veto_factors=factors,
                risk_score=sig.risk_score,
            )

        my_side = specialty_side(AgentId.RISK, sig, snap)
        r = react(my_side, priors)
        if r.stance in (Stance.DISAGREE, Stance.CHALLENGE) and r.addressee is not None:
            text = (
                f"I'm not as comfortable as the {name(r.addressee)}. Volatility is "
                f"{sig.volatility_level} ({snap.volatility:.2f}%), risk score {sig.risk_score:.2f}. "
                f"I won't block it, but I'd {'stand aside' if my_side is Side.HOLD else 'size down to ' + my_side.value} "
                f"with tight invalidation."
            )
        else:
            text = (
                f"Risk is contained — volatility {sig.volatility_level} ({snap.volatility:.2f}%), "
                f"score {sig.risk_score:.2f}. I'll allow {my_side.value}, sized with tight invalidation."
            )
        return AgentOutput(
            text=text, stance=r.stance, vote=my_side,
            confidence=round(55 + (1 - sig.risk_score) * 25, 1),
            references=r.references or [AgentId.QUANT], risk_score=sig.risk_score,
        )
