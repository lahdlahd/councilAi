"""Trade Journal routes.

  GET /journal              -> recent decisions (summaries)
  GET /journal/{session_id} -> one full decision (replayable in Step 8)

If Supabase isn't configured the list is empty and detail is 404 — the API stays
up either way.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.domain.models import JournalEntry, JournalSummary
from app.services.council.session import SessionManager
from app.services.journal.service import JournalService

router = APIRouter(prefix="/journal", tags=["journal"])


def get_journal(request: Request) -> JournalService:
    return request.app.state.journal


def _sessions(request: Request) -> SessionManager:
    return request.app.state.session_manager


def _to_summary(e: JournalEntry) -> JournalSummary:
    rec = e.recommendation
    return JournalSummary(
        session_id=e.session_id, symbol=e.symbol, started_at=e.started_at, ended_at=e.ended_at,
        side=rec.side if rec else None,
        confidence=e.confidence,
        consensus_reached=rec.consensus_reached if rec else False,
        vetoed=(e.veto is not None) or (rec.vetoed if rec else False),
    )


@router.get("", response_model=list[JournalSummary])
async def list_journal(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    journal: JournalService = Depends(get_journal),
) -> list[JournalSummary]:
    rows = await journal.list(limit)
    if rows:
        return rows
    # In-memory fallback (no Supabase): recent finished sessions, newest first.
    sessions = list(reversed(_sessions(request).recent_sessions()))
    return [_to_summary(e) for e in sessions][:limit]


@router.get("/{session_id}", response_model=JournalEntry)
async def get_journal_entry(
    request: Request,
    session_id: str,
    journal: JournalService = Depends(get_journal),
) -> JournalEntry:
    entry = await journal.get(session_id)
    if entry is None:
        entry = _sessions(request).session_detail(session_id)  # in-memory fallback
    if entry is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return entry
