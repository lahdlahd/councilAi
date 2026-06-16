"""Trade Journal routes.

  GET /journal              -> recent decisions (summaries)
  GET /journal/{session_id} -> one full decision (replayable in Step 8)

If Supabase isn't configured the list is empty and detail is 404 — the API stays
up either way.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.domain.models import JournalEntry, JournalSummary
from app.services.journal.service import JournalService

router = APIRouter(prefix="/journal", tags=["journal"])


def get_journal(request: Request) -> JournalService:
    return request.app.state.journal


@router.get("", response_model=list[JournalSummary])
async def list_journal(
    limit: int = Query(default=50, ge=1, le=200),
    journal: JournalService = Depends(get_journal),
) -> list[JournalSummary]:
    return await journal.list(limit)


@router.get("/{session_id}", response_model=JournalEntry)
async def get_journal_entry(
    session_id: str,
    journal: JournalService = Depends(get_journal),
) -> JournalEntry:
    entry = await journal.get(session_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="decision not found")
    return entry
