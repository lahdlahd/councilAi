# Council — Frontend (Step 4)

The Council Chamber: a Next.js 15 control-room UI that connects to the backend over
WebSockets and renders the live debate, agent roster, market ticker, confidence dial,
votes, recommendation, and the dramatic risk-veto overlay.

## Design

- **Palette** (from the brief): bg `#0F1113`, surface `#181C20`, gold `#C9A227`,
  bronze `#A16B3B`, positive `#2B8A6E`, negative `#A54B4B`, text `#F4F1EA`.
- **Type**: IBM Plex superfamily — Sans (UI), Mono (all numerics/labels), Serif
  (wordmark + headers). An engineered, institutional system, not crypto-flashy.
- **Layout**: three-column terminal — committee roster · chamber · instruments.
- **Signature**: the live streaming chamber + the 270° radial Confidence Dial.
- No blue, no purple, no cyberpunk. Agent accents are semantic (Risk = warning red).

## Run

```bash
cd apps/web
npm install
cp .env.local.example .env.local   # point NEXT_PUBLIC_WS_URL at your backend
npm run dev                        # http://localhost:3000
```

The page connects to `${NEXT_PUBLIC_WS_URL}/ws/council` and `/ws/market`. Start the
backend first (`uvicorn app.main:app` in `apps/api`) so the ambient session is live —
the UI hydrates from the in-progress `session.snapshot` on connect (no empty state).

## Design preview (no build, no backend)

Open `preview.html` directly in a browser to see the exact look with a simulated
council session (including a veto round). Useful for design sign-off.

## Structure

```
src/
  app/            layout (fonts), globals.css, page.tsx (the dashboard)
                  journal/ (list + [sessionId] detail), replay/[sessionId]
  lib/            types.ts (wire contract), agents.ts, ws/client.ts, api.ts, replay.ts
  stores/         sessionStore (council events), marketStore (ticks) — Zustand
  hooks/          useStreams (live), useReplay (recorded playback)
  components/     TopBar, chamber/, agents/, market/, confidence/, voting/,
                  recommendation/, veto/, replay/
```

State flow: the WS client decodes typed `WsEvent`s → `store.apply()` mutates Zustand →
components subscribe. `agent.token` deltas accumulate onto a streaming message; the
blinking caret marks the message still being spoken.

## Notes

- shadcn/ui is listed in the brief; primitives here are hand-rolled in Tailwind to keep
  the app runnable with no generator step. Drop shadcn in later if desired.
- TradingView Lightweight Charts (price chart) is deferred — this step is the chamber.

## Journal & Replay

- `/journal` lists past decisions (from `GET /journal`); `/journal/[id]` shows the full
  recorded decision.
- `/replay/[id]` plays a recorded decision back through the **same chamber components**
  as the live session — `lib/replay.ts` expands a journal entry into the original event
  sequence and `useReplay` drives the session store on a local clock (play/pause/scrub,
  1×/2×/4×). No backend changes needed; replay reads `GET /journal/{id}`.

## Charts & symbol selection (final)

- `PriceChart` (TradingView Lightweight Charts) renders the active subject's candles and
  nudges the last bar with live ticks.
- The market panel is a **symbol selector** — tapping a coin POSTs `/council/symbol`, and
  the council convenes on it on the next round. The active subject is highlighted.
