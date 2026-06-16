-- Council Trade Journal — schema
-- Normalized: a session owns its debate (messages), votes, and one recommendation.
-- Structured sub-objects (market snapshot, confidence breakdown, references, veto
-- factors) are stored as jsonb so they round-trip exactly to the domain models.

create table if not exists sessions (
  id                    text primary key,            -- e.g. "sess-1a2b3c"
  symbol                text not null,
  started_at            bigint not null,             -- ms epoch
  ended_at              bigint,
  phase                 text not null,               -- decided | blocked
  side                  text,                        -- BUY | SELL | HOLD
  confidence            numeric,
  consensus_ratio       numeric,
  consensus_reached     boolean default false,
  vetoed                boolean default false,
  veto_by               text,
  veto_reason           text,
  veto_risk_score       numeric,
  veto_factors          jsonb default '[]'::jsonb,
  market_snapshot       jsonb not null,
  confidence_breakdown  jsonb,
  created_at            timestamptz default now()
);

create table if not exists messages (
  message_id  text primary key,
  session_id  text not null references sessions(id) on delete cascade,
  ordinal     int  not null,                         -- speaking order
  agent_id    text not null,
  text        text not null,
  stance      text not null,
  refs        jsonb default '[]'::jsonb,             -- "references" is reserved in SQL
  confidence  numeric,
  ts          bigint not null
);
create index if not exists idx_messages_session on messages(session_id, ordinal);

create table if not exists votes (
  id          uuid primary key default gen_random_uuid(),
  session_id  text not null references sessions(id) on delete cascade,
  agent_id    text not null,
  side        text not null,
  rationale   text
);
create index if not exists idx_votes_session on votes(session_id);

create table if not exists recommendations (
  session_id        text primary key references sessions(id) on delete cascade,
  side              text not null,
  confidence        numeric not null,
  summary           text,
  consensus_ratio   numeric,
  consensus_reached boolean,
  vetoed            boolean,
  veto_reason       text,
  created_at        timestamptz default now()
);

create index if not exists idx_sessions_created on sessions(created_at desc);

-- RLS on. The backend uses the service-role key (bypasses RLS); the frontend reads
-- the journal through the API, never directly, so no anon policies are required.
alter table sessions        enable row level security;
alter table messages        enable row level security;
alter table votes           enable row level security;
alter table recommendations enable row level security;
