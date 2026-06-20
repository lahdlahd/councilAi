"""Execution Agent — chairman of the committee.

Speaks LAST, after the council result is computed. Its job is the synthesis the
spec calls for:
  1. summarize the debate (agreement, dissent, any veto)
  2. report the Council Confidence Score
  3. declare the final recommendation
  4. explain WHY that recommendation was selected (which factors drove it)

It does not vote. The numbers come from the deterministic tally/confidence engine,
so the chairman's explanation is always consistent with the dials the UI shows.
"""

from __future__ import annotations

from collections import Counter

from app.domain.enums import AgentId, Side, Stance
from app.services.council.agents.base import Agent, AgentOutput
from app.services.council.signal import Signal
from app.services.council.state import CouncilState, transcript

_SYSTEM = (
    "You are the EXECUTION AGENT — the CHAIRMAN of an AI investment committee. You speak last, "
    "after the vote. You do NOT vote yourself. Your job: (1) summarize the debate fairly, naming "
    "agreement and dissent and any risk veto; (2) state the council confidence score; (3) declare "
    "the final recommendation; (4) explain WHY it was selected — which factors carried it and "
    "which held it back. Be measured and authoritative, like a chair closing a contested vote."
)

# Friendly labels for the four confidence drivers (higher component = more supportive).
_DRIVERS = {
    "agreement": "vote agreement",
    "risk": "risk control",
    "volatility": "calm volatility",
    "sentiment": "sentiment conviction",
}


class ExecutionAgent(Agent):
    id = AgentId.EXECUTION
    casts_vote = False
    system_prompt = _SYSTEM

    # --- LLM mode: hand the chairman the computed result to explain ---------
    def _user_prompt(self, state: CouncilState) -> str:
        rec = state.get("recommendation")
        conf = state.get("confidence")
        br = state.get("confidence_breakdown")
        result_lines = ["COUNCIL RESULT (already computed — explain it, don't recompute):"]
        if conf is not None:
            result_lines.append(f"Confidence score: {conf:.0f}/100")
        if rec is not None:
            result_lines.append(
                f"Recommendation: {rec.side.value} "
                f"(consensus {rec.consensus_ratio:.0%}, vetoed={rec.vetoed})"
            )
        if br is not None:
            result_lines.append(
                f"Confidence drivers — agreement {br.agreement:.0f}, risk {br.risk:.0f}, "
                f"volatility {br.volatility:.0f}, sentiment {br.sentiment:.0f} (higher = more supportive)"
            )
        return (
            f"LIVE MARKET DATA:\n{self._evidence(state)}\n\n"
            f"DEBATE SO FAR:\n{transcript(state)}\n\n"
            + "\n".join(result_lines)
            + "\n\nAs chairman, deliver your closing synthesis in 2-4 sentences: summarize the "
            "debate, state the confidence score, declare the recommendation, and explain which "
            "drivers carried it and which held it back. Reply with STRICT JSON: "
            '"message", "stance" (neutral), "vote" (null), "confidence" (the council score), '
            '"references" (array of agent ids you cite).'
        )

    # --- Offline mode: deterministic chairman synthesis --------------------
    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:
        votes = state.get("votes", [])
        veto = state.get("veto")
        rec = state.get("recommendation")
        conf = state.get("confidence")
        br = state.get("confidence_breakdown")
        tally = Counter(v.side for v in votes)
        contested = len(set(v.side for v in votes)) > 1
        conf_txt = f"{conf:.0f}%" if conf is not None else "—"

        if veto is not None:
            reason = veto.reason.split("—")[-1].strip().rstrip(".") if veto.reason else "unacceptable risk"
            text = (
                f"As chairman, I'm standing the committee down. The Risk Manager vetoed — {reason}. "
                f"That caps council confidence at {conf_txt}. Final recommendation: HOLD — we do not "
                f"act against an active risk block, whatever the analysts' lean."
            )
            return AgentOutput(text=text, stance=Stance.NEUTRAL, vote=None,
                               confidence=conf or 20.0, references=[AgentId.RISK])

        side = rec.side.value if rec is not None else (
            tally.most_common(1)[0][0].value if tally else Side.HOLD.value
        )
        counts = ", ".join(f"{n}×{s.value}" for s, n in tally.most_common())
        debate_line = (
            f"after a contested debate ({counts}), the dissent heard and the majority defended its read"
            if contested else f"with the committee unanimous ({counts})"
        )

        why = ""
        if br is not None:
            comps = {
                "agreement": br.agreement, "risk": br.risk,
                "volatility": br.volatility, "sentiment": br.sentiment,
            }
            top = max(comps, key=comps.get)
            low = min(comps, key=comps.get)
            why = (
                f" Confidence was carried by {_DRIVERS[top]} ({comps[top]:.0f}) and held back by "
                f"{_DRIVERS[low]} ({comps[low]:.0f})."
            )

        text = (
            f"Summing up: {debate_line}. Council confidence lands at {conf_txt}.{why} "
            f"Final recommendation: {side} — selected as the committee's leading position."
        )
        return AgentOutput(text=text, stance=Stance.NEUTRAL, vote=None,
                           confidence=conf or 70.0,
                           references=[AgentId.TECHNICAL, AgentId.QUANT, AgentId.RISK])
