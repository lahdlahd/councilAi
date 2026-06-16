"""Base agent: prompt construction, LLM parsing, and deterministic offline path.

Each concrete agent supplies a persona (system prompt) and an `_offline()` method
that produces a data-driven AgentOutput from the real signal when no LLM is set.
The base handles prompt assembly, JSON parsing, and message-id minting so the
subclasses stay focused on personality.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field

from app.domain.enums import AgentId, Side, Stance
from app.domain.models import AgentMessage, AgentProfile
from app.services.council.signal import Signal, read_signal
from app.services.council.state import CouncilState, transcript
from app.services.llm.client import LLMClient
from app.utils.logging import get_logger

log = get_logger("agent")


@dataclass
class AgentOutput:
    text: str
    stance: Stance = Stance.NEUTRAL
    vote: Side | None = None
    confidence: float = 50.0
    references: list[AgentId] = field(default_factory=list)
    # Risk-only
    veto: bool = False
    veto_reason: str | None = None
    veto_factors: list[str] = field(default_factory=list)
    risk_score: float | None = None
    # News-only
    sentiment: float | None = None


# --- Static profiles surfaced to the UI -------------------------------------
AGENT_PROFILES: dict[AgentId, AgentProfile] = {
    AgentId.TECHNICAL: AgentProfile(
        id=AgentId.TECHNICAL, name="Technical Analyst", specialty="RSI · MACD · EMA · S/R",
        personality="chart-obsessed", avatar="📈", casts_vote=True,
    ),
    AgentId.NEWS: AgentProfile(
        id=AgentId.NEWS, name="News Analyst", specialty="sentiment · ETF · macro",
        personality="fast-moving information hunter", avatar="📰", casts_vote=True,
    ),
    AgentId.QUANT: AgentProfile(
        id=AgentId.QUANT, name="Quant Analyst", specialty="probability · statistics",
        personality="cold and mathematical", avatar="🧮", casts_vote=True,
    ),
    AgentId.RISK: AgentProfile(
        id=AgentId.RISK, name="Risk Manager", specialty="drawdown · volatility · exposure",
        personality="paranoid and skeptical", avatar="🛡️", casts_vote=True,
    ),
    AgentId.EXECUTION: AgentProfile(
        id=AgentId.EXECUTION, name="Execution Agent", specialty="synthesis · final decision",
        personality="committee chairman", avatar="⚖️", casts_vote=False,
    ),
}


class Agent:
    id: AgentId
    casts_vote: bool = True
    system_prompt: str = ""

    @property
    def profile(self) -> AgentProfile:
        return AGENT_PROFILES[self.id]

    # ---- public entrypoint --------------------------------------------------
    async def deliberate(self, state: CouncilState, llm: LLMClient) -> AgentOutput:
        if llm.is_offline:
            return self._offline(state, read_signal(state["snapshot"]))
        try:
            raw = await llm.complete(
                system=self.system_prompt,
                user=self._user_prompt(state),
                json_mode=True,
            )
            return self._parse(raw)
        except Exception as exc:  # noqa: BLE001 - never let one agent crash the round
            log.warning("%s LLM path failed (%s); using offline reasoning", self.id.value, exc)
            return self._offline(state, read_signal(state["snapshot"]))

    def to_message(self, out: AgentOutput) -> AgentMessage:
        return AgentMessage(
            message_id=f"{self.id.value}-{uuid.uuid4().hex[:8]}",
            agent_id=self.id,
            text=out.text,
            stance=out.stance,
            references=out.references,
            confidence=out.confidence,
            ts=int(time.time() * 1000),
        )

    # ---- prompt assembly ----------------------------------------------------
    def _evidence(self, state: CouncilState) -> str:
        snap = state["snapshot"]
        sig = read_signal(snap)
        ind = snap.indicators
        lines = [
            f"Symbol: {snap.symbol}",
            f"Price: {snap.price}",
            f"24h change: {snap.change24h:+.2f}%",
            f"24h high/low: {snap.high24h} / {snap.low24h}",
            f"Quote volume (24h): {snap.quote_volume:,.0f}",
            f"Realized volatility: {snap.volatility:.3f}% ({sig.volatility_level})",
        ]
        if ind is not None:
            lines += [
                f"RSI(14): {ind.rsi} ({sig.rsi_read})",
                f"MACD hist: {ind.macd.histogram} ({sig.macd_read})",
                f"EMA12/26/50: {ind.ema.ema12} / {ind.ema.ema26} / {ind.ema.ema50} ({sig.trend_read})",
            ]
        else:
            lines.append("Indicators: unavailable (fallback data source)")
        return "\n".join(lines)

    def _user_prompt(self, state: CouncilState) -> str:
        vote_clause = (
            'Include "vote" as one of BUY/SELL/HOLD. '
            if self.casts_vote
            else 'Set "vote" to null (you are the chairman; you do not vote). '
        )
        return (
            f"LIVE MARKET DATA:\n{self._evidence(state)}\n\n"
            f"DEBATE SO FAR:\n{transcript(state)}\n\n"
            "Respond as your character. Reference and react to colleagues where relevant. "
            "Reply with a STRICT JSON object only, no prose, with keys: "
            '"message" (1-3 sentences, in-character), '
            '"stance" (opening|agree|disagree|challenge|neutral), '
            f'"vote" (BUY|SELL|HOLD or null — {vote_clause.strip()}), '
            '"confidence" (0-100), '
            '"references" (array of agent ids you respond to: technical|news|quant|risk|execution).'
            + self._extra_schema()
        )

    def _extra_schema(self) -> str:
        return ""

    def prose_prompt(self, state: CouncilState) -> tuple[str, str]:
        """System+user prompts for STREAMING prose (Step 3).

        Unlike the JSON deliberation prompt, this asks for natural in-character
        speech only. Votes/stance/confidence are derived deterministically from the
        real signal, so the LLM is free to focus on sounding human — while the
        committee's actual decisions stay grounded and explainable."""
        user = (
            f"LIVE MARKET DATA:\n{self._evidence(state)}\n\n"
            f"DEBATE SO FAR:\n{transcript(state)}\n\n"
            "Speak now, in character, in 1-3 sentences. React to colleagues by name "
            "where it's natural. Plain prose only — no JSON, no preamble, no quotes."
        )
        return self.system_prompt, user

    # ---- parsing ------------------------------------------------------------
    def _parse(self, raw: str) -> AgentOutput:
        data = _loads_lenient(raw)
        return AgentOutput(
            text=str(data.get("message", "")).strip() or "(no statement)",
            stance=_to_stance(data.get("stance")),
            vote=_to_side(data.get("vote")) if self.casts_vote else None,
            confidence=_clamp(data.get("confidence", 50.0), 0, 100),
            references=_to_refs(data.get("references")),
            veto=bool(data.get("veto", False)),
            veto_reason=data.get("veto_reason"),
            risk_score=_opt_float(data.get("risk_score")),
            sentiment=_opt_float(data.get("sentiment")),
        )

    # ---- offline (data-driven) — overridden per agent -----------------------
    def _offline(self, state: CouncilState, sig: Signal) -> AgentOutput:  # pragma: no cover
        raise NotImplementedError


# --- parsing helpers --------------------------------------------------------
def _loads_lenient(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1] if raw.count("```") >= 2 else raw.strip("`")
        raw = raw.removeprefix("json").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        start, end = raw.find("{"), raw.rfind("}")
        if start != -1 and end != -1:
            try:
                return json.loads(raw[start : end + 1])
            except json.JSONDecodeError:
                pass
    return {"message": raw[:300]}


def _to_stance(v) -> Stance:
    try:
        return Stance(str(v).lower())
    except ValueError:
        return Stance.NEUTRAL


def _to_side(v) -> Side | None:
    if v is None:
        return None
    try:
        return Side(str(v).upper())
    except ValueError:
        return None


def _to_refs(v) -> list[AgentId]:
    if not isinstance(v, list):
        return []
    out = []
    for item in v:
        try:
            out.append(AgentId(str(item).lower()))
        except ValueError:
            continue
    return out


def _clamp(v, lo, hi) -> float:
    try:
        return max(lo, min(hi, float(v)))
    except (TypeError, ValueError):
        return 50.0


def _opt_float(v) -> float | None:
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None
