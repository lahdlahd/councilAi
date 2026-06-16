# Council — Autonomous AI Investment Committee

Five AI agents analyze live crypto markets (Bitget), **debate in real time**, vote, and
produce a transparent recommendation — with a Risk Manager that can veto the trade. Built
to feel like a hedge-fund control room: watch the committee think, disagree, and decide.

```
        ┌──────────────────────────┐   WSS (council + market)   ┌────────────────────────┐
Browser │  Next.js 15 (Vercel)     │ ◀────────────────────────▶ │  FastAPI (Render)      │
        │  Council Chamber UI       │   HTTPS (journal/candles)   │  • ambient session loop │
        └──────────────────────────┘                             │  • LangGraph 5 agents   │
                                                                  │  • WS broadcaster hub   │
                                                                  └───────┬────────┬────────┘
                                                          Bitget REST/WS  │  Qwen/  │ Supabase
                                                          CoinGecko (fb)  │ OpenAI  │ (journal)
```

## What's inside

- **Backend** (`apps/api`) — FastAPI + Python 3.12. Bitget market data (REST + public WS),
  a LangGraph five-agent council, WebSocket streaming with an always-on ambient session,
  the debate/voting/confidence/veto engines, and a Supabase trade journal. Runs with **no
  API keys** in a data-driven offline mode; add a key for real LLM inference.
- **Frontend** (`apps/web`) — Next.js 15 + TypeScript + Tailwind + Zustand + Framer Motion
  + TradingView Lightweight Charts. The Council Chamber, agent roster, market ticker +
  symbol selector, price chart, confidence dial, voting, veto overlay, journal, and replay.
- **infra/** — Supabase schema migration; `render.yaml` (backend) lives at the repo root.

## Run locally

Two terminals.

**Backend**
```bash
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # optional: add QWEN/OPENAI/SUPABASE keys
uvicorn app.main:app --reload --port 8000
```

**Frontend**
```bash
cd apps/web
npm install
cp .env.local.example .env.local   # defaults already point at localhost:8000
npm run dev                         # http://localhost:3000
```

Open http://localhost:3000 — you drop straight into a live council session (offline mode
needs no keys). Tap a symbol in the market panel to convene the council on it. Past
decisions are under **Trade Journal**, and any decision can be **replayed**.

Run the backend tests: `cd apps/api && pytest -q`.

## Deploy live

**1. Backend → Render**
- Push this repo to GitHub.
- Render → New → **Blueprint** → select the repo (it reads `render.yaml`).
- After the first deploy, set the dashboard secrets: `ALLOWED_ORIGINS` (your Vercel URL,
  comma-separated), and optionally `QWEN_API_KEY` / `OPENAI_API_KEY` /
  `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY`.
- Use a paid instance so the always-on session doesn't idle. Health check: `/health`.

**2. Database → Supabase** (optional, for the journal)
- Create a project, open the SQL editor, run `infra/supabase/migrations/0001_init.sql`.
- Put the project URL + **service-role** key into the Render env vars above.

**3. Frontend → Vercel**
- New Project → import the repo → set **Root Directory** to `apps/web`.
- Env vars: `NEXT_PUBLIC_API_URL=https://<your-render-host>` and
  `NEXT_PUBLIC_WS_URL=wss://<your-render-host>`.
- Deploy. Then add the Vercel URL to the backend's `ALLOWED_ORIGINS` and redeploy the API.

## Environment matrix

| Variable | Where | Purpose |
|---|---|---|
| `ALLOWED_ORIGINS` | backend | CORS — your frontend origin(s) |
| `COUNCIL_SYMBOL` | backend | initial session subject (default BTCUSDT) |
| `QWEN_API_KEY` / `OPENAI_API_KEY` | backend | LLM (omit → offline mode) |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | backend | journal (omit → no-op) |
| `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` | frontend | backend endpoints |

## Notes

- Market data is always live (Bitget, CoinGecko fallback); only the agents' prose falls back
  to deterministic offline reasoning when no LLM key is set. Votes/confidence/veto are always
  derived from the real signal, so decisions stay explainable.
- The News Analyst reads market-implied sentiment (no live news feed wired yet).
