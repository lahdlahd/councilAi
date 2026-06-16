"""Minimal async Supabase client over the PostgREST REST API.

We talk to `{SUPABASE_URL}/rest/v1` directly with the shared httpx.AsyncClient and
the service-role key, rather than pulling in the sync supabase-py SDK (which would
block the event loop). Only the few verbs the journal needs are implemented.
"""

from __future__ import annotations

import httpx

from app.utils.logging import get_logger
from app.utils.retry import with_retry

log = get_logger("supabase")


class SupabaseClient:
    def __init__(self, client: httpx.AsyncClient, url: str, service_key: str) -> None:
        self._http = client
        self._base = f"{url.rstrip('/')}/rest/v1"
        self._auth = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
        }

    async def insert(self, table: str, rows: dict | list[dict], *, upsert: bool = False) -> None:
        if isinstance(rows, list) and not rows:
            return
        prefer = "return=minimal"
        if upsert:
            prefer += ",resolution=merge-duplicates"
        headers = {**self._auth, "Content-Type": "application/json", "Prefer": prefer}

        async def _call() -> None:
            r = await self._http.post(f"{self._base}/{table}", headers=headers, json=rows)
            r.raise_for_status()

        await with_retry(_call, label=f"supabase insert {table}", attempts=2)

    async def select(self, table: str, params: dict[str, str]) -> list[dict]:
        async def _call() -> list[dict]:
            r = await self._http.get(f"{self._base}/{table}", headers=self._auth, params=params)
            r.raise_for_status()
            return r.json()

        return await with_retry(_call, label=f"supabase select {table}", attempts=2)
