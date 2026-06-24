# Council — Autonomous AI Investment Committee

Five specialized AI agents analyze live crypto markets (Bitget), **debate in real time**,
vote, and reach a transparent investment decision — with a Risk Manager that can veto the
trade. Every decision that isn't a HOLD or veto is **executed as a paper trade** against the
live market price, building a tracked portfolio with live PnL, a full trade ledger, and a
public compliance log. Built to feel like a hedge-fund control room: watch the committee
think, disagree, decide, and trade.

- **Live app:** https://council-ai-5o5x.vercel.app
- **Paper Trading Log (public):** https://council-ai-5o5x.vercel.app/compliance

> Paper trading only — fills are simulated against live Bitget prices. No real orders are
> ever placed.

```
        ┌──────────────────────────┐   WSS (council + trades)    ┌──────────────────────────┐
Browser │  Next.js 15 (Vercel)     │ ◀────────────────────────▶ │  FastAPI (Render)         │
        │  Command center + journal │   HTTPS (portfolio/journal) │  • 5-agent LangGraph council│
        └──────────────────────────┘                             │  • debate/vote/confidence   │
                                                                  │  • Risk Manager veto        │
                                                                  │  • Paper Trading engine     │
                                                                  │  • live PnL + trade ledger  │
                                                                  │  • WS broadcaster hub       │
                                                                  └────┬─────────┬─────────┬────┘
                                                       Bitget REST/WS  │  Qwen/  │  Supabase │
                                                       CoinGecko (fb)  │ OpenAI  │ (optional)│
```

## How a session works

```
Convene → Market Scan → Debate → Voting → Risk Review → Execution
```

You explicitly **convene** the council on an asset (no auto-session). The five agents scan
the live market, debate in turn, cast votes, and the Risk Manager reviews. The Execution
Agent synthesizes a final **BUY / SELL / HOLD** with a confidence score. A BUY/SELL that
isn't vetoed becomes a **paper trade**, sized within your configured limits; HOLD and vetoes
produce no trade. The decision is recorded to the journal and the trade to the ledger.

## The committee

| Agent | Role |
| --- | --- |
| **Technical Analyst** | Reads price structure, trend, and key levels — opens the case. |
| **News Analyst** | Weighs market-implied sentiment and momentum. |
| **Quant Analyst** | Applies probability/statistics and risk-adjusted sizing. |
| **Risk Manager** | Guards capital — flags volatility/risk and holds the **veto**. |
| **Execution Agent** | Chairs the committee, weighs the debate, and calls the verdict. |

## Paper trading

- Portfolio starts at **100,000 USDT**. BUY → long, SELL → short (spot and futures).
- **You control sizing** before each session via the Trade Configuration panel:
  - Position size as a **% of portfolio** (slider) or a **fixed USDT** amount.
  - **Risk level**: Conservative / Moderate / Aggressive.
- Sizing pipeline: `suggested = equity × 10% × confidence → × risk-level → × volatility factor
  → min(your cap, …)`. Your cap is a **hard ceiling** — the Risk Manager can reduce the size
  or veto, but never raise it above your limit. Every trade stores the requested,
  risk-adjusted, and final executed sizes.
- **Live PnL** marks open positions against live Bitget prices on a background loop.
- **Trade ledger** updates in real time over WebSocket (a `paper.trade` event prepends the
  new trade instantly).
- **Analytics**: win rate, average return, best/worst trade, Sharpe, profit factor, per-agent
  directional accuracy, and veto success rate.
- **Compliance / Paper Trading Log** at `/compliance` — a public, exportable (CSV/JSON) record
  of every simulated trade, with an honesty note that fills are simulated against live prices.

## Pages

| Route | What it is |
| --- | --- |
| `/` | Landing + command center — hero, live market overview, the committee, how it works, and the session launcher. |
| `/console` | Live decision-first command center — session header, committee status, **Decision Summary**, **Council Vote**, **Risk Review**, **Paper Trade**, **Explainable Confidence**, and the **Debate Timeline**. |
| `/dashboard` | Portfolio dashboard — equity, returns, open/closed positions, and analytics. |
| `/room` | **Performance Room** — big-screen demo view of portfolio, confidence, agent accuracy, live debate, and recent decisions. |
| `/compliance` | **Paper Trading Log** — public compliance record with CSV/JSON export. |
| `/journal` | Trade Journal — past council decisions (debate, votes, confidence, verdict). |
| `/trade/[id]` | Trade detail — the decision behind a trade, with a replay link. |
| `/replay/trade/[id]` | Replays the decision that produced a trade. |

## What's inside

- **Backend** (`apps/api`) — FastAPI + Python 3.12. Bitget market data (REST + public WS) with
  a CoinGecko fallback, a **LangGraph** five-agent council, WebSocket streaming, the
  debate/voting/confidence/veto engines, the **paper trading engine** (portfolio, live PnL,
  ledger, analytics, compliance), and a session journal. Runs with **no API keys** in a
  data-driven offline mode (deterministic agent prose; market data, votes, confidence, and
  veto are always derived from the real signal). Add an LLM key for real inference and
  Supabase for persistence.
- **Frontend** (`apps/web`) — Next.js 15 + TypeScript + Tailwind + Zustand + Framer Motion +
  TradingView Lightweight Charts. The landing/command center, the decision-first console, the
  Performance Room, the portfolio dashboard, the trade ledger dock, and the journal/replay,
  all in a black-and-gold control-room aesthetic.
- **infra/** — Supabase schema migrations; `render.yaml` (backend) lives at the repo root.

## Run locally

Two terminals.

**Backend**

```
cd apps/api
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # optional: add QWEN/OPENAI/SUPABASE keys
uvicorn app.main:app --reload --port 8000
```

**Frontend**

```
cd apps/web
npm install
cp .env.local.example .env.local   # defaults already point at localhost:8000
npm run dev                         # http://localhost:3000
```

Open <http://localhost:3000>. You land on the command-center home; use the **Trade
Configuration** panel to pick an asset, market, position size, and risk level, then
**Convene Council**. Watch the live console, then find the decision under **Trade Journal**
and the trade in the **Paper Trading Log** — any decision can be **replayed**.

Run the backend tests: `cd apps/api && pytest -q`.

## Deploy live

**1. Backend → Render**

- Push this repo to GitHub.
- Render → New → **Blueprint** → select the repo (it reads `render.yaml`).
- After the first deploy, set the dashboard secrets: `ALLOWED_ORIGINS` (your Vercel URL,
  comma-separated — **required** or the browser's API/POST calls are CORS-blocked), and
  optionally `QWEN_API_KEY` / `OPENAI_API_KEY` / `SUPABASE_URL` /
  `SUPABASE_SERVICE_ROLE_KEY`. Health check: `/health`.
- The free tier cold-starts after ~15 min idle, which resets in-memory state (portfolio,
  ledger, journal). Use a paid instance or Supabase if you need persistence across restarts.

**2. Database → Supabase** (optional, for persistence)

- Create a project, open the SQL editor, and run both migrations in order:
  `infra/supabase/migrations/0001_init.sql` (council + journal) and
  `0002_paper_trading.sql` (paper trading tables).
- Put the project URL + **service-role** key into the Render env vars above.
- Without Supabase the app is fully functional but in-memory — the journal and ledger fall
  back to an in-memory cache and reset on restart.

**3. Frontend → Vercel**

- New Project → import the repo → set **Root Directory** to `apps/web`.
- Env vars: `NEXT_PUBLIC_API_URL=https://<your-render-host>` and
  `NEXT_PUBLIC_WS_URL=wss://<your-render-host>`.
- Deploy. Then add the Vercel URL to the backend's `ALLOWED_ORIGINS` and redeploy the API.

## Environment matrix

| Variable | Where | Purpose |
| --- | --- | --- |
| `ALLOWED_ORIGINS` | backend | CORS — your frontend origin(s). Required for the browser to convene sessions and read the portfolio. |
| `QWEN_API_KEY` / `OPENAI_API_KEY` | backend | LLM inference (omit → deterministic offline mode) |
| `SUPABASE_URL` / `SUPABASE_SERVICE_ROLE_KEY` | backend | persistence for journal + trades (omit → in-memory) |
| `NEXT_PUBLIC_API_URL` / `NEXT_PUBLIC_WS_URL` | frontend | backend HTTPS + WSS endpoints |

## Notes

- Market data is always live (Bitget, CoinGecko fallback); only the agents' prose falls back
  to deterministic offline reasoning when no LLM key is set. Votes, confidence, veto, and
  trade sizing are always derived from the real signal, so decisions stay explainable.
- The News Analyst reads market-implied sentiment (no live news feed wired yet).
- All trading is simulated (paper) against live prices — no real orders are placed.
