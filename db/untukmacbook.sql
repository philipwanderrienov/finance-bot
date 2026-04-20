-- Finance Bot PostgreSQL schema for macOS/local development
-- Intended to match the current application code in:
-- - shared/db.py
-- - shared/models.py
-- - services/ingestion/app.py
-- - services/orchestrator/app.py
-- - services/aggregation/app.py
-- - services/research/app.py
-- - services/telegram_notifier/app.py
--
-- Usage:
--   psql "$POSTGRES_DSN" -f db/untukmacbook.sql
-- or:
--   psql -h 127.0.0.1 -U postgres -d financebot -f db/untukmacbook.sql

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION touch_updated_at()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

-- Drop dependent tables first so this script can be re-run safely on a clean dev database.
DROP TABLE IF EXISTS telegram_messages CASCADE;
DROP TABLE IF EXISTS ingestion_runs CASCADE;
DROP TABLE IF EXISTS scheduler_jobs CASCADE;
DROP TABLE IF EXISTS market_snapshots CASCADE;
DROP TABLE IF EXISTS research_reports CASCADE;
DROP TABLE IF EXISTS news_items CASCADE;
DROP TABLE IF EXISTS markets CASCADE;
DROP TABLE IF EXISTS sources CASCADE;

CREATE TABLE IF NOT EXISTS sources (
    id BIGSERIAL PRIMARY KEY,
    source_type TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE,
    base_url TEXT NULL,
    domain TEXT NULL,
    category TEXT NOT NULL CHECK (category IN ('stocks', 'crypto')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT sources_source_type_non_empty CHECK (length(trim(source_type)) > 0),
    CONSTRAINT sources_name_non_empty CHECK (length(trim(name)) > 0),
    CONSTRAINT sources_category_non_empty CHECK (length(trim(category)) > 0)
);

CREATE INDEX idx_sources_source_type ON sources (source_type);
CREATE INDEX idx_sources_category ON sources (category);
CREATE INDEX idx_sources_is_active ON sources (is_active);

CREATE TRIGGER sources_set_updated_at
BEFORE UPDATE ON sources
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS markets (
    id BIGSERIAL PRIMARY KEY,
    external_id TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'stocks',
    url TEXT,
    score DOUBLE PRECISION NOT NULL DEFAULT 0,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_markets_category ON markets (category);
CREATE INDEX idx_markets_external_id ON markets (external_id);
CREATE INDEX idx_markets_updated_at ON markets (updated_at DESC);

CREATE TRIGGER markets_set_updated_at
BEFORE UPDATE ON markets
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS news_items (
    id BIGSERIAL PRIMARY KEY,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    market_id BIGINT NULL REFERENCES markets(id) ON DELETE SET NULL,
    external_id TEXT NULL,
    title TEXT NOT NULL,
    summary TEXT NULL,
    content TEXT NULL,
    url TEXT NOT NULL,
    domain TEXT NULL,
    category TEXT NOT NULL CHECK (category IN ('stocks', 'crypto')),
    published_at TIMESTAMPTZ NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NULL,
    CONSTRAINT news_items_url_unique UNIQUE (url),
    CONSTRAINT news_items_source_external_unique UNIQUE (source_id, external_id),
    CONSTRAINT news_items_title_non_empty CHECK (length(trim(title)) > 0),
    CONSTRAINT news_items_url_non_empty CHECK (length(trim(url)) > 0)
);

CREATE INDEX idx_news_items_source_id ON news_items (source_id);
CREATE INDEX idx_news_items_market_id ON news_items (market_id);
CREATE INDEX idx_news_items_category ON news_items (category);
CREATE INDEX idx_news_items_published_at ON news_items (published_at);
CREATE INDEX idx_news_items_domain ON news_items (domain);
CREATE INDEX idx_news_items_external_id ON news_items (external_id);

CREATE TABLE IF NOT EXISTS market_snapshots (
    id BIGSERIAL PRIMARY KEY,
    market_id BIGINT NOT NULL REFERENCES markets(id) ON DELETE CASCADE,
    snapshot_time TIMESTAMPTZ NOT NULL,
    source_id BIGINT NOT NULL REFERENCES sources(id) ON DELETE RESTRICT,
    price NUMERIC(18,8) NULL,
    best_bid NUMERIC(18,8) NULL,
    best_ask NUMERIC(18,8) NULL,
    volume_24h NUMERIC(18,8) NULL,
    liquidity NUMERIC(18,8) NULL,
    raw_payload JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_market_snapshots_market_id ON market_snapshots (market_id);
CREATE INDEX idx_market_snapshots_snapshot_time ON market_snapshots (snapshot_time DESC);
CREATE INDEX idx_market_snapshots_market_time ON market_snapshots (market_id, snapshot_time DESC);
CREATE INDEX idx_market_snapshots_source_id ON market_snapshots (source_id);

CREATE TABLE IF NOT EXISTS research_reports (
    id BIGSERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    summary TEXT NOT NULL,
    details TEXT NULL,
    category TEXT NOT NULL CHECK (category IN ('stocks', 'crypto')),
    market_id BIGINT NULL REFERENCES markets(id) ON DELETE SET NULL,
    source_window_start TIMESTAMPTZ NULL,
    source_window_end TIMESTAMPTZ NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NULL,
    CONSTRAINT research_reports_title_non_empty CHECK (length(trim(title)) > 0),
    CONSTRAINT research_reports_summary_non_empty CHECK (length(trim(summary)) > 0),
    CONSTRAINT research_reports_status_non_empty CHECK (length(trim(status)) > 0)
);

CREATE INDEX idx_research_reports_category ON research_reports (category);
CREATE INDEX idx_research_reports_market_id ON research_reports (market_id);
CREATE INDEX idx_research_reports_status ON research_reports (status);
CREATE INDEX idx_research_reports_created_at ON research_reports (created_at DESC);

CREATE TRIGGER research_reports_set_updated_at
BEFORE UPDATE ON research_reports
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS telegram_messages (
    id BIGSERIAL PRIMARY KEY,
    report_id BIGINT NULL REFERENCES research_reports(id) ON DELETE SET NULL,
    chat_id TEXT NOT NULL,
    message_type TEXT NOT NULL,
    title TEXT NULL,
    body TEXT NOT NULL,
    payload JSONB NULL,
    status TEXT NOT NULL,
    scheduled_for TIMESTAMPTZ NULL,
    sent_at TIMESTAMPTZ NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0 CHECK (attempt_count >= 0),
    last_error TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT telegram_messages_chat_id_non_empty CHECK (length(trim(chat_id)) > 0),
    CONSTRAINT telegram_messages_message_type_non_empty CHECK (length(trim(message_type)) > 0),
    CONSTRAINT telegram_messages_body_non_empty CHECK (length(trim(body)) > 0),
    CONSTRAINT telegram_messages_status_non_empty CHECK (length(trim(status)) > 0)
);

CREATE INDEX idx_telegram_messages_status ON telegram_messages (status);
CREATE INDEX idx_telegram_messages_scheduled_for ON telegram_messages (scheduled_for);
CREATE INDEX idx_telegram_messages_chat_id ON telegram_messages (chat_id);
CREATE INDEX idx_telegram_messages_report_id ON telegram_messages (report_id);

CREATE TRIGGER telegram_messages_set_updated_at
BEFORE UPDATE ON telegram_messages
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id BIGSERIAL PRIMARY KEY,
    job_name TEXT NOT NULL UNIQUE,
    service_name TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    schedule_type TEXT NOT NULL,
    schedule_value TEXT NOT NULL,
    timezone TEXT NOT NULL DEFAULT 'UTC',
    last_run_at TIMESTAMPTZ NULL,
    next_run_at TIMESTAMPTZ NULL,
    last_status TEXT NULL,
    retry_count INTEGER NOT NULL DEFAULT 0 CHECK (retry_count >= 0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    metadata JSONB NULL,
    CONSTRAINT scheduler_jobs_service_name_non_empty CHECK (length(trim(service_name)) > 0),
    CONSTRAINT scheduler_jobs_schedule_type_non_empty CHECK (length(trim(schedule_type)) > 0),
    CONSTRAINT scheduler_jobs_schedule_value_non_empty CHECK (length(trim(schedule_value)) > 0),
    CONSTRAINT scheduler_jobs_timezone_non_empty CHECK (length(trim(timezone)) > 0)
);

CREATE INDEX idx_scheduler_jobs_enabled ON scheduler_jobs (enabled);
CREATE INDEX idx_scheduler_jobs_next_run_at ON scheduler_jobs (next_run_at);
CREATE INDEX idx_scheduler_jobs_service_name ON scheduler_jobs (service_name);

CREATE TRIGGER scheduler_jobs_set_updated_at
BEFORE UPDATE ON scheduler_jobs
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TABLE IF NOT EXISTS ingestion_runs (
    id BIGSERIAL PRIMARY KEY,
    job_id BIGINT NULL REFERENCES scheduler_jobs(id) ON DELETE SET NULL,
    source_id BIGINT NULL REFERENCES sources(id) ON DELETE SET NULL,
    run_type TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ NULL,
    items_seen INTEGER NOT NULL DEFAULT 0 CHECK (items_seen >= 0),
    items_inserted INTEGER NOT NULL DEFAULT 0 CHECK (items_inserted >= 0),
    items_updated INTEGER NOT NULL DEFAULT 0 CHECK (items_updated >= 0),
    error_message TEXT NULL,
    metadata JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ingestion_runs_run_type_non_empty CHECK (length(trim(run_type)) > 0),
    CONSTRAINT ingestion_runs_status_non_empty CHECK (length(trim(status)) > 0)
);

CREATE INDEX idx_ingestion_runs_job_id ON ingestion_runs (job_id);
CREATE INDEX idx_ingestion_runs_source_id ON ingestion_runs (source_id);
CREATE INDEX idx_ingestion_runs_run_type ON ingestion_runs (run_type);
CREATE INDEX idx_ingestion_runs_status ON ingestion_runs (status);
CREATE INDEX idx_ingestion_runs_started_at ON ingestion_runs (started_at DESC);

-- Seed canonical sources used by the current application.
INSERT INTO sources (source_type, name, base_url, domain, category, is_active)
VALUES
    ('polymarket', 'Polymarket Gamma', 'https://gamma-api.polymarket.com', 'polymarket.com', 'crypto', TRUE),
    ('polymarket', 'Polymarket Data', 'https://data-api.polymarket.com', 'polymarket.com', 'crypto', TRUE),
    ('polymarket', 'Polymarket CLOB', 'https://clob.polymarket.com', 'polymarket.com', 'crypto', TRUE)
ON CONFLICT (name) DO UPDATE
SET
    source_type = EXCLUDED.source_type,
    base_url = EXCLUDED.base_url,
    domain = EXCLUDED.domain,
    category = EXCLUDED.category,
    is_active = EXCLUDED.is_active,
    updated_at = now();

COMMIT;

-- Optional verification queries:
-- SELECT * FROM sources ORDER BY id;
-- SELECT * FROM scheduler_jobs ORDER BY id;
