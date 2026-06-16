"""Council backend — FastAPI application entrypoint.

Lifespan wiring:
  - build shared httpx clients
  - construct MarketService (Bitget + CoinGecko + indicators)
  - construct the Broadcaster hub
  - launch the Bitget public WS consumer as a background task

The Bitget consumer is the heartbeat of the live market stream; it keeps the
in-process hub fed so every connected /ws/market client sees continuous ticks.
"""

from __future__ import annotations

import asyncio
import contextlib
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.adapters.bitget.rest import BitgetRestClient
from app.adapters.bitget.ws import BitgetWsConsumer
from app.adapters.coingecko.rest import CoinGeckoClient
from app.adapters.supabase.client import SupabaseClient
from app.api.routes import council as council_routes, health, journal as journal_routes, market
from app.api.ws import council_ws, market_ws
from app.config import get_settings
from app.services.council.graph import Council
from app.services.council.session import SessionManager
from app.services.hub.broadcaster import Broadcaster
from app.services.journal.service import JournalService
from app.services.llm.cadence import Cadence
from app.services.llm.client import LLMClient
from app.services.market.service import MarketService
from app.utils.logging import configure_logging, get_logger

configure_logging()
log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()

    http = httpx.AsyncClient(
        timeout=settings.http_timeout_sec,
        headers={"User-Agent": "council/1.0"},
    )

    bitget_rest = BitgetRestClient(http, settings.bitget_rest_base)
    coingecko = CoinGeckoClient(http, settings.coingecko_base, settings.coingecko_api_key)
    market_service = MarketService(bitget_rest, coingecko, settings)
    broadcaster = Broadcaster()
    ws_consumer = BitgetWsConsumer(settings, broadcaster, market_service)

    # Council orchestration layer (Step 2). The graph is compiled once.
    llm = LLMClient(http, settings)
    council = Council(llm)

    # Ambient session loop + streaming (Step 3): runs rounds continuously and feeds
    # the broadcaster, so any connecting client sees a session already in progress.
    cadence = Cadence(settings.cadence_tokens_per_sec)

    # Trade Journal (Step 7): persists every completed round. No-op without keys.
    supabase = (
        SupabaseClient(http, settings.supabase_url, settings.supabase_service_role_key)
        if settings.supabase_url and settings.supabase_service_role_key
        else None
    )
    journal = JournalService(supabase)
    if not journal.enabled:
        log.warning("Supabase not configured — Trade Journal disabled (no-op)")

    session_manager = SessionManager(
        settings, broadcaster, market_service, council, cadence, journal
    )

    # Expose to routes/ws via app.state.
    app.state.settings = settings
    app.state.http = http
    app.state.market_service = market_service
    app.state.broadcaster = broadcaster
    app.state.llm = llm
    app.state.council = council
    app.state.session_manager = session_manager
    app.state.journal = journal

    consumer_task = asyncio.create_task(ws_consumer.run(), name="bitget-ws-consumer")
    session_task = asyncio.create_task(session_manager.run(), name="council-session-loop")
    log.info("Council backend started (env=%s)", settings.app_env)

    try:
        yield
    finally:
        ws_consumer.stop()
        session_manager.stop()
        for task in (consumer_task, session_task):
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await http.aclose()
        log.info("Council backend stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Council API", version="1.0.0", lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(market.router)
    app.include_router(council_routes.router)
    app.include_router(journal_routes.router)
    app.include_router(market_ws.router)
    app.include_router(council_ws.router)
    return app


app = create_app()
