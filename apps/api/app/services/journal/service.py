"""Trade Journal — persists every completed round and reads decisions back.

Storage is normalized across sessions / messages / votes / recommendations, with
structured sub-objects kept as jsonb so they round-trip exactly to the domain
models. If Supabase isn't configured the service is a safe no-op (the app still
runs in dev) — reads return empty/None, writes are skipped.

`save()` takes a SessionSnapshotEvent (built from the live session) so this module
has no dependency on the session runtime — avoiding a circular import.
"""

from __future__ import annotations

from app.adapters.supabase.client import SupabaseClient
from app.domain.enums import Side
from app.domain.events import SessionSnapshotEvent
from app.domain.models import (
    AgentMessage,
    ConfidenceBreakdown,
    JournalEntry,
    JournalSummary,
    MarketSnapshot,
    Recommendation,
    VetoInfo,
    Vote,
)
from app.utils.logging import get_logger

log = get_logger("journal")

_SUMMARY_COLS = "session_id:id,symbol,started_at,ended_at,side,confidence,consensus_reached,vetoed"


class JournalService:
    def __init__(self, supabase: SupabaseClient | None) -> None:
        self._sb = supabase

    @property
    def enabled(self) -> bool:
        return self._sb is not None

    # ---- write -------------------------------------------------------------
    async def save(self, snap: SessionSnapshotEvent, ended_at: int) -> None:
        if self._sb is None:
            return
        rec = snap.recommendation
        veto = snap.veto
        try:
            await self._sb.insert(
                "sessions",
                {
                    "id": snap.session_id,
                    "symbol": snap.symbol,
                    "started_at": snap.started_at,
                    "ended_at": ended_at,
                    "phase": snap.phase,
                    "side": rec.side.value if rec else None,
                    "confidence": snap.confidence,
                    "consensus_ratio": rec.consensus_ratio if rec else None,
                    "consensus_reached": rec.consensus_reached if rec else False,
                    "vetoed": bool(veto),
                    "veto_by": veto.by_agent.value if veto else None,
                    "veto_reason": veto.reason if veto else None,
                    "veto_risk_score": veto.risk_score if veto else None,
                    "veto_factors": veto.factors if veto else [],
                    "market_snapshot": snap.snapshot.model_dump(),
                    "confidence_breakdown": snap.confidence_breakdown.model_dump()
                    if snap.confidence_breakdown
                    else None,
                },
                upsert=True,
            )
            await self._sb.insert(
                "messages",
                [
                    {
                        "message_id": m.message_id,
                        "session_id": snap.session_id,
                        "ordinal": i,
                        "agent_id": m.agent_id.value,
                        "text": m.text,
                        "stance": m.stance.value,
                        "refs": [r.value for r in m.references],
                        "confidence": m.confidence,
                        "ts": m.ts,
                    }
                    for i, m in enumerate(snap.messages)
                ],
                upsert=True,
            )
            await self._sb.insert(
                "votes",
                [
                    {
                        "session_id": snap.session_id,
                        "agent_id": v.agent_id.value,
                        "side": v.side.value,
                        "rationale": v.rationale,
                    }
                    for v in snap.votes
                ],
            )
            if rec:
                await self._sb.insert(
                    "recommendations",
                    {
                        "session_id": snap.session_id,
                        "side": rec.side.value,
                        "confidence": rec.confidence,
                        "summary": rec.summary,
                        "consensus_ratio": rec.consensus_ratio,
                        "consensus_reached": rec.consensus_reached,
                        "vetoed": rec.vetoed,
                        "veto_reason": rec.veto_reason,
                    },
                    upsert=True,
                )
            log.info("journaled session %s (%s)", snap.session_id, snap.symbol)
        except Exception as exc:  # noqa: BLE001 - persistence must never break the loop
            log.warning("failed to journal %s: %s", snap.session_id, exc)

    # ---- read --------------------------------------------------------------
    async def list(self, limit: int = 50) -> list[JournalSummary]:
        if self._sb is None:
            return []
        rows = await self._sb.select(
            "sessions",
            {"select": _SUMMARY_COLS, "order": "created_at.desc", "limit": str(limit)},
        )
        return [JournalSummary.model_validate(r) for r in rows]

    async def get(self, session_id: str) -> JournalEntry | None:
        if self._sb is None:
            return None
        sessions = await self._sb.select(
            "sessions", {"id": f"eq.{session_id}", "select": "*", "limit": "1"}
        )
        if not sessions:
            return None
        s = sessions[0]

        messages = await self._sb.select(
            "messages",
            {"session_id": f"eq.{session_id}", "select": "*", "order": "ordinal.asc"},
        )
        votes = await self._sb.select(
            "votes", {"session_id": f"eq.{session_id}", "select": "*"}
        )
        recs = await self._sb.select(
            "recommendations", {"session_id": f"eq.{session_id}", "select": "*", "limit": "1"}
        )

        veto = (
            VetoInfo(
                by_agent=s["veto_by"],
                reason=s.get("veto_reason") or "",
                risk_score=float(s.get("veto_risk_score") or 0.0),
                factors=s.get("veto_factors") or [],
            )
            if s.get("vetoed")
            else None
        )
        recommendation = None
        if recs:
            r = recs[0]
            recommendation = Recommendation(
                session_id=session_id,
                symbol=s["symbol"],
                side=Side(r["side"]),
                confidence=float(r["confidence"]),
                summary=r.get("summary") or "",
                consensus_ratio=float(r.get("consensus_ratio") or 0.0),
                consensus_reached=bool(r.get("consensus_reached")),
                vetoed=bool(r.get("vetoed")),
                veto_reason=r.get("veto_reason"),
                ts=int(s.get("ended_at") or s["started_at"]),
            )

        return JournalEntry(
            session_id=session_id,
            symbol=s["symbol"],
            started_at=int(s["started_at"]),
            ended_at=int(s["ended_at"]) if s.get("ended_at") else None,
            phase=s["phase"],
            snapshot=MarketSnapshot.model_validate(s["market_snapshot"]),
            messages=[
                AgentMessage(
                    message_id=m["message_id"],
                    agent_id=m["agent_id"],
                    text=m["text"],
                    stance=m["stance"],
                    references=m.get("refs") or [],
                    confidence=float(m.get("confidence") or 50.0),
                    ts=int(m["ts"]),
                )
                for m in messages
            ],
            votes=[
                Vote(agent_id=v["agent_id"], side=Side(v["side"]), rationale=v.get("rationale") or "")
                for v in votes
            ],
            veto=veto,
            confidence=float(s["confidence"]) if s.get("confidence") is not None else None,
            confidence_breakdown=ConfidenceBreakdown.model_validate(s["confidence_breakdown"])
            if s.get("confidence_breakdown")
            else None,
            recommendation=recommendation,
        )
