-- ============================================================================
-- Council Paper Trading Engine — Supabase / PostgreSQL schema
-- ----------------------------------------------------------------------------
-- Flow this schema persists:
--   Live Bitget Data -> Council Debate -> Council Vote -> Paper Trade Created
--   -> Portfolio Updated -> PnL Tracked -> Trade Ledger Stored -> Replay
--
-- Notes
--  * PAPER TRADING ONLY. Fills are simulated against live Bitget prices; no order
--    ever reaches an exchange.
--  * `council_sessions` / `agent_messages` / `agent_votes` are the evolved journal
--    tables (superseding sessions/messages/votes from 0001_init.sql); the final
--    decision now lives on the session row rather than a separate table.
--  * Structured sub-objects (market snapshot, confidence breakdown, references,
--    veto factors) are jsonb so they round-trip exactly to the domain models.
--  * Timestamps: bigint columns are ms-epoch (matching the wire/domain models);
--    created_at/updated_at are timestamptz for human/db convenience.
-- ============================================================================

create extension if not exists pgcrypto;  -- gen_random_uuid()

-- ---------------------------------------------------------------------------
-- updated_at helper
-- ---------------------------------------------------------------------------
create or replace function set_updated_at() returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- ===========================================================================
-- 1. council_sessions  — one row per convened council decision
-- ===========================================================================
create table if not exists council_sessions (
  id                    text primary key,                       -- e.g. "sess-1a2b3c"
  symbol                text not null,
  market                text not null default 'spot'
                          check (market in ('spot','futures')),
  started_at            bigint not null,                        -- ms epoch
  ended_at              bigint,
  phase                 text not null
                          check (phase in ('debating','voting','decided','blocked')),
  side                  text check (side in ('BUY','SELL','HOLD')),  -- final direction
  confidence            numeric,                                -- 0..100
  summary               text,                                   -- chairman reasoning
  consensus_ratio       numeric,
  consensus_reached     boolean default false,
  vetoed                boolean default false,
  veto_by               text,
  veto_reason           text,
  veto_risk_score       numeric,
  veto_factors          jsonb default '[]'::jsonb,
  market_snapshot       jsonb not null,                         -- price, indicators, etc.
  confidence_breakdown  jsonb,                                  -- agreement/risk/vol/sentiment
  created_at            timestamptz default now()
);
create index if not exists idx_council_sessions_created
  on council_sessions(created_at desc);
create index if not exists idx_council_sessions_symbol
  on council_sessions(symbol, market);

-- ===========================================================================
-- 2. agent_messages  — the debate transcript (reasoning), in speaking order
-- ===========================================================================
create table if not exists agent_messages (
  message_id  text primary key,
  session_id  text not null references council_sessions(id) on delete cascade,
  ordinal     int  not null,                                    -- speaking order
  agent_id    text not null,                                    -- technical|news|quant|risk|execution
  text        text not null,                                    -- the agent's reasoning
  stance      text not null,                                    -- opening|agree|disagree|challenge|neutral
  refs        jsonb default '[]'::jsonb,                        -- agents referenced ("references" is reserved)
  confidence  numeric,
  ts          bigint not null                                   -- ms epoch
);
create index if not exists idx_agent_messages_session
  on agent_messages(session_id, ordinal);

-- ===========================================================================
-- 3. agent_votes  — each analyst's BUY/SELL/HOLD after the debate
-- ===========================================================================
create table if not exists agent_votes (
  id          uuid primary key default gen_random_uuid(),
  session_id  text not null references council_sessions(id) on delete cascade,
  agent_id    text not null,
  side        text not null check (side in ('BUY','SELL','HOLD')),  -- direction
  rationale   text,
  confidence  numeric,
  created_at  timestamptz default now()
);
create index if not exists idx_agent_votes_session on agent_votes(session_id);

-- ===========================================================================
-- 4. portfolio  — the simulated account (one "house" portfolio for the demo)
-- ===========================================================================
create table if not exists portfolio (
  id                uuid primary key default gen_random_uuid(),
  name              text not null default 'House Paper Portfolio',
  base_currency     text not null default 'USDT',
  starting_balance  numeric not null default 100000,
  cash_balance      numeric not null default 100000,             -- free cash
  realized_pnl      numeric not null default 0,                 -- cumulative booked PnL
  created_at        timestamptz default now(),
  updated_at        timestamptz default now()
);
create or replace trigger trg_portfolio_updated
  before update on portfolio
  for each row execute function set_updated_at();

-- Deterministic default portfolio so the engine can reference a known id.
insert into portfolio (id, name)
values ('00000000-0000-0000-0000-000000000001', 'House Paper Portfolio')
on conflict (id) do nothing;

-- ===========================================================================
-- 5. paper_trades  — a position from open to close (status + PnL live here)
-- ===========================================================================
create table if not exists paper_trades (
  id              uuid primary key default gen_random_uuid(),
  portfolio_id    uuid not null references portfolio(id) on delete cascade,
  session_id      text references council_sessions(id) on delete set null,  -- decision that opened it
  symbol          text not null,
  market          text not null default 'spot'
                    check (market in ('spot','futures')),
  direction       text not null check (direction in ('long','short')),
  quantity        numeric not null,                             -- current base quantity
  entry_price     numeric not null,                             -- average entry
  exit_price      numeric,                                      -- set on close
  last_mark_price numeric,                                      -- latest mark
  status          text not null default 'open'
                    check (status in ('open','closed','cancelled')),
  confidence      numeric,                                      -- council confidence at open
  reasoning       text,                                         -- why the trade was taken
  fee             numeric not null default 0,                   -- cumulative simulated fees
  realized_pnl    numeric not null default 0,                   -- booked on reduce/close
  unrealized_pnl  numeric,                                      -- last mark-to-market
  opened_at       timestamptz default now(),
  closed_at       timestamptz
);
create index if not exists idx_paper_trades_portfolio
  on paper_trades(portfolio_id, status);
create index if not exists idx_paper_trades_session  on paper_trades(session_id);
create index if not exists idx_paper_trades_symbol   on paper_trades(symbol, market);
create index if not exists idx_paper_trades_open
  on paper_trades(portfolio_id) where status = 'open';

-- ===========================================================================
-- 6. trade_events  — append-only ledger of every action + balance change
-- ===========================================================================
create table if not exists trade_events (
  id                  uuid primary key default gen_random_uuid(),
  trade_id            uuid references paper_trades(id) on delete cascade,
  portfolio_id        uuid not null references portfolio(id) on delete cascade,
  session_id          text references council_sessions(id) on delete set null,
  event_type          text not null
                        check (event_type in ('open','increase','reduce','close','flip','mark')),
  symbol              text not null,
  market              text not null default 'spot',
  direction           text check (direction in ('long','short')),
  quantity            numeric,                                  -- quantity affected
  price               numeric,                                  -- fill / mark price
  fee                 numeric default 0,
  slippage            numeric default 0,
  cash_delta          numeric default 0,                        -- balance change (+/-)
  realized_pnl_delta  numeric default 0,                        -- PnL booked by this event
  balance_after       numeric,                                  -- cash balance after the event
  note                text,
  created_at          timestamptz default now()
);
create index if not exists idx_trade_events_portfolio
  on trade_events(portfolio_id, created_at desc);
create index if not exists idx_trade_events_trade   on trade_events(trade_id);
create index if not exists idx_trade_events_session on trade_events(session_id);

-- ===========================================================================
-- 7. portfolio_snapshots  — equity-curve time series (powers the PnL chart)
-- ===========================================================================
create table if not exists portfolio_snapshots (
  id                uuid primary key default gen_random_uuid(),
  portfolio_id      uuid not null references portfolio(id) on delete cascade,
  ts                bigint not null,                            -- ms epoch
  cash              numeric not null,
  equity            numeric not null,                           -- cash + position value
  unrealized_pnl    numeric not null default 0,
  realized_pnl_cum  numeric not null default 0,
  open_positions    int not null default 0,
  created_at        timestamptz default now()
);
create index if not exists idx_portfolio_snapshots
  on portfolio_snapshots(portfolio_id, ts);

-- ===========================================================================
-- Row Level Security
-- The backend uses the service-role key (bypasses RLS). The frontend reads
-- through the API, never directly, so no anon policies are required.
-- ===========================================================================
alter table council_sessions    enable row level security;
alter table agent_messages      enable row level security;
alter table agent_votes         enable row level security;
alter table portfolio           enable row level security;
alter table paper_trades        enable row level security;
alter table trade_events        enable row level security;
alter table portfolio_snapshots enable row level security;
