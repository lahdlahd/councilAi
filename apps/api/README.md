# Council — Backend (Step 1)

FastAPI + Bitget market integration. Live REST snapshots for five symbols, technical
indicators (RSI / MACD / EMA / realized volatility), and a continuous WebSocket market
stream fed by Bitget's public WS — with a CoinGecko fallback and honest degraded-state
signaling.

## Layout (clean architecture — dependencies point inward)

```
app/
  domain/      models, enums, the WsEvent wire contract  (no I/O)
  services/    market (orchestration + indicators), hub (pub/sub broadcaster)
  adapters/    bitget (rest + public ws), coingecko (fallback)
  api/         routes (market, health) + ws (market_ws) + deps
  main.py      lifespan wiring + background Bitget WS consumer
```

## Endpoints

| Method | Path             | Description                                   |
|--------|------------------|-----------------------------------------------|
| GET    | `/health`        | status + market connection + WS subscriber count |
| GET    | `/market`        | snapshots for all supported symbols           |
| GET    | `/market/btc`    | BTCUSDT snapshot (also `/eth /sol /xrp /doge`) |
| GET    | `/market/{sym}`  | any supported symbol (`btc` or `BTCUSDT`)     |
| WS     | `/ws/market`     | initial snapshot burst, then live `market.tick` + `connection.status` |

All JSON is camelCase (matches the TypeScript `shared-types`).

## Run locally

```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate   # or: uv venv
pip install -e ".[dev]"                              # or: uv pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

Then:
```bash
curl localhost:8000/health
curl localhost:8000/market/btc | jq
# stream:  wscat -c ws://localhost:8000/ws/market
```

## Test

```bash
pytest -q          # indicator math + guards
```

## Council multi-agent layer (Step 2)

Five agents debate over a `MarketSnapshot`, vote, and produce a recommendation via
a LangGraph state machine.

```
START → technical → news → quant → risk → execution → tally → END
```

- **Agents** (`services/council/agents/`): Technical, News, Quant, Risk (can veto),
  Execution (chairman). Each has a persona + a deterministic offline reasoner.
- **LLM** (`services/llm/client.py`): Qwen primary → OpenAI fallback → offline.
  With no key set, agents reason over the **real** signal (RSI/MACD/EMA/volatility).
- **Confidence** (`services/council/confidence.py`): deterministic 0-100 from
  agreement, risk, volatility, sentiment — with a per-component breakdown.
- **Veto**: Risk Manager blocks the trade when realized volatility + signal conflict
  exceed threshold; recommendation becomes HOLD and phase `blocked`.

Run a debate (no keys needed):
```bash
python -m app.services.council.demo            # synthetic snapshot
python -m app.services.council.demo --live btc # real Bitget data (needs network)
```

Token streaming over WebSockets and the always-on ambient session arrive in Step 3.

## Live streaming + ambient session (Step 3)

The council now runs **continuously** server-side and streams word-by-word over
WebSockets, so any client that connects drops into a session already in progress.

- **`/ws/council`** — on connect, sends a `session.snapshot` of the in-progress
  round (full transcript + votes + phase), then streams live events.
- **Ambient loop** (`services/council/session.py`): `SessionManager` runs rounds
  back-to-back forever on `COUNCIL_SYMBOL`, feeding the broadcaster.
- **Cadence controller** (`services/llm/cadence.py`): re-chunks LLM/offline text
  into evenly-paced word tokens (`CADENCE_TOKENS_PER_SEC`) so the debate reads as
  deliberate thinking, not a paste — losslessly (tokens reassemble to the message).
- **Event stream**: `session.started` · `agent.thinking` · `agent.token` ·
  `agent.message` · `debate.reference` · `vote.cast` · `council.confidence` ·
  `council.veto` · `council.recommendation` · `council.phase`.

In LLM mode the streamed prose is generated live; votes/confidence/veto stay
deterministic from the real signal — human-sounding, but grounded decisions.

## Trade Journal (Step 7)

Every completed round is auto-saved to Supabase (debate, votes, confidence,
recommendation, market snapshot, veto detail). Without Supabase keys the journal is
a safe no-op and the rest of the app runs normally.

- Schema: `infra/supabase/migrations/0001_init.sql` (run it in the Supabase SQL editor).
- Set `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` in `.env`.
- Endpoints: `GET /journal` (recent summaries), `GET /journal/{session_id}` (full,
  replayable decision). The frontend reads these via `/journal` pages.

Storage is normalized (sessions · messages · votes · recommendations) with structured
sub-objects as jsonb so rows round-trip exactly back to the domain models.

## Notes for later steps

- The `Broadcaster` hub is the single fan-out point — the council debate stream (Step 3)
  publishes onto the same hub, so the frontend uses one transport pattern for everything.
- `MarketService.get_snapshot()` is what the agents (Step 2) call to seed `CouncilState`.
- `WsEvent` is a discriminated union; new event types append without breaking decoders.
- Deploy on Render as a **single web service** (one process) — the WS consumer and hub
  assume one event loop. See `Dockerfile`.

## Charts & symbol selection (final)

- `GET /market/{symbol}/candles?limit=150` — OHLC bars for the TradingView chart.
- `GET /council` — current subject + supported symbols.
- `POST /council/symbol {"symbol":"ETHUSDT"}` — switch the council's subject
  (applies on the next round). The frontend's market panel calls this when a symbol is tapped.
