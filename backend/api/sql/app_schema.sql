-- User data (004 Plan). Idempotent; the API runs it at start-up. The schema name `app` is substituted
-- (tests use `app_test`). plan_versions also stores the request each version was planned from.

CREATE SCHEMA IF NOT EXISTS app;

CREATE TABLE IF NOT EXISTS app.users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email text UNIQUE NOT NULL,
  password_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS app.profiles (
  user_id uuid PRIMARY KEY REFERENCES app.users ON DELETE CASCADE,
  prefs jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS app.trips (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id uuid NOT NULL REFERENCES app.users ON DELETE CASCADE,
  name text NOT NULL,
  request jsonb NOT NULL,
  result jsonb NOT NULL,
  selected_variant text,
  tradeoffs jsonb,
  start_date date NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS trips_user ON app.trips (user_id, start_date);

CREATE TABLE IF NOT EXISTS app.plan_versions (
  trip_id uuid REFERENCES app.trips ON DELETE CASCADE,
  version int,
  plan jsonb NOT NULL,
  request jsonb NOT NULL,
  source text NOT NULL CHECK (source IN ('select', 'replan', 'chat', 'restore')),
  changes jsonb,
  note text,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (trip_id, version));

CREATE TABLE IF NOT EXISTS app.chat_messages (
  id bigserial PRIMARY KEY,
  trip_id uuid NOT NULL REFERENCES app.trips ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user', 'assistant')),
  text text NOT NULL,
  actions jsonb,
  version int,
  created_at timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS chat_trip ON app.chat_messages (trip_id, id);

-- Read-only share links (API-FR-14). One per trip; deleting the row turns the link off.
CREATE TABLE IF NOT EXISTS app.trip_shares (
  trip_id uuid PRIMARY KEY REFERENCES app.trips ON DELETE CASCADE,
  token text UNIQUE NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now());
