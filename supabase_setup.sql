-- Industria-AI: tables for history and tester feedback.
-- Run once in Supabase: SQL Editor > New query > paste > Run.

create table if not exists public.analyses (
  id            uuid primary key default gen_random_uuid(),
  created_at    timestamptz not null default now(),
  user_email    text not null,
  report_id     text,
  industry      text,
  problem       text,
  problem_label text,
  mode          text,
  decision      text,
  summary       text,
  report        jsonb
);
create index if not exists analyses_user_idx on public.analyses (user_email, created_at desc);

create table if not exists public.feedback (
  id                   uuid primary key default gen_random_uuid(),
  created_at           timestamptz not null default now(),
  user_email           text,
  report_id            text,
  industry             text,
  mode                 text,
  decision             text,
  rating               int check (rating between 1 and 5),
  root_cause_plausible text,
  mode_right           text,
  quick_check_clear    text,
  comment              text
);

-- Lock both tables. With Row Level Security on and no policies, the public
-- (publishable/anon) key cannot read or write them. The app uses the secret
-- key, which stays on the server in Streamlit Secrets.
alter table public.analyses enable row level security;
alter table public.feedback enable row level security;
