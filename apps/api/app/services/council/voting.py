"""Vote tally + final recommendation assembly (the graph's terminal node logic).

Counts analyst votes into a structured tally, derives the consensus (leading side,
its vote share, and whether it meets quorum), respects an active risk veto, computes
the Council Confidence Score, and produces the Recommendation.
"""

from __future__ import annotations

import time
from collections import Counter
from dataclasses import dataclass

from app.domain.enums import Side
from app.domain.models import Recommendation, VetoInfo, Vote
from app.services.council.confidence import compute_confidence
from app.services.council.state import CouncilState

# A side needs at least this share of votes to count as a true consensus.
QUORUM = 0.6


@dataclass
class VoteTally:
    counts: dict[Side, int]
    total: int
    leading: Side
    ratio: float          # leading side's share of all votes, 0-1
    reached: bool         # ratio >= QUORUM

    @property
    def label(self) -> str:
        if self.total == 0:
            return "no votes"
        return "consensus" if self.reached else "split"


def compute_tally(votes: list[Vote]) -> VoteTally:
    counts: dict[Side, int] = {s: 0 for s in Side}
    for v in votes:
        counts[v.side] += 1
    total = len(votes)
    if total == 0:
        return VoteTally(counts=counts, total=0, leading=Side.HOLD, ratio=0.0, reached=False)
    leading, top = max(counts.items(), key=lambda kv: kv[1])
    ratio = top / total
    return VoteTally(counts=counts, total=total, leading=leading, ratio=ratio, reached=ratio >= QUORUM)


def tally(state: CouncilState) -> dict:
    snapshot = state["snapshot"]
    votes: list[Vote] = state.get("votes", [])
    veto: VetoInfo | None = state.get("veto")

    risk_score = state.get("risk_score")
    sentiment = state.get("sentiment")

    vt = compute_tally(votes)
    vetoed = veto is not None
    side = Side.HOLD if vetoed else vt.leading

    confidence, breakdown = compute_confidence(snapshot, votes, risk_score, sentiment, vetoed)
    summary = _summary(side, vt, vetoed, veto)

    rec = Recommendation(
        session_id=state["session_id"],
        symbol=state["symbol"],
        side=side,
        confidence=confidence,
        summary=summary,
        consensus_ratio=round(vt.ratio, 3),
        consensus_reached=vt.reached and not vetoed,
        vetoed=vetoed,
        veto_reason=veto.reason if veto else None,
        ts=int(time.time() * 1000),
    )
    return {
        "recommendation": rec,
        "confidence": confidence,
        "confidence_breakdown": breakdown,
        "phase": "blocked" if vetoed else "decided",
    }


def _summary(side: Side, vt: VoteTally, vetoed: bool, veto: VetoInfo | None) -> str:
    if vetoed and veto:
        return f"BLOCKED by Risk Manager — {veto.reason}"
    counts = ", ".join(f"{s.value}:{n}" for s, n in vt.counts.items() if n)
    verb = "Consensus" if vt.reached else "Majority (no consensus)"
    return f"{verb} {side.value} at {vt.ratio:.0%} ({vt.total} votes). Tally — {counts or 'none'}."
