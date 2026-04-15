# PostgreSQL Database Schema

## Overview

This schema is designed for the Financial Bot project and supports only:
- Stocks market
- Crypto
- Polymarket market tracking
- News aggregation
- Research summaries
- Telegram notifications
- Scheduler jobs
- Ingestion runs

The schema uses PostgreSQL as the shared storage layer for all services.

## Common conventions

### Primary key style
- Use `bigserial` for row IDs
- Each table has a simple numeric primary key

### Timestamp fields
- `created_at` for when a row was created
- `updated_at` for when a row was last changed, when useful
- Use `timestamptz` for all timestamps

### Status fields
Use simple text values or short enums for:
- job status
- ingestion status
- message status
- report status

### Scope filtering
Markets and news should be limited to:
- `stocks`
- `crypto`

You can store this as a text field with a check constraint or as a small enum.

---

## Table: sources

Stores data sources used by ingestion and research.

### Purpose
Keep track of where records came from.

### Columns
- `id` bigserial primary key
- `source_type` text not null  
  Examples: `polymarket`, `news_feed`, `rss`, `manual`
- `name` text not null
- `base_url` text null
- `domain` text null
- `category` text not null  
  Allowed values: `stocks`, `crypto`
- `is_active` boolean not null default true
- `created_at` timestamptz not null default now()
- `updated_at` timestamptz not null default now()

### Constraints
- `category` should only allow `stocks` or `crypto`
- `source_type` should be non-empty

### Indexes
- index on `source_type`
- index on `category`
- unique index on `name`

---

## Table: markets

Stores tracked market metadata.

### Purpose
Represent Polymarket markets and other market-like items the bot monitors.

### Columns
- `id` bigserial primary key
- `source_id` bigint not null foreign key references `sources(id)`
- `external_id` text not null
- `slug` text null
- `title` text not null
- `description` text null
- `category` text not null  
  Allowed values: `stocks`, `crypto`
- `status` text not null  
  Examples: `active`, `closed`, `archived`
- `url` text null
- `published_at` timestamptz null
- `resolved_at` timestamptz null
- `created_at` timestamptz not null default now()
- `updated_at` timestamptz not null default now()

### Constraints
- unique `(source_id, external_id)`
- `category` restricted to `stocks` or `crypto`

### Indexes
- index on `source_id`
- index on `category`
- index on `status`
- index on `published_at`
- unique index on `external_id` together with `source_id`

---

## Table: news_items

Stores aggregated news articles and posts.

### Purpose
Hold deduplicated news records for later summarization.

### Columns
- `id` bigserial primary key
- `source_id` bigint not null foreign key references `sources(id)`
- `market_id` bigint null foreign key references `markets(id)`
- `external_id` text null
- `title` text not null
- `summary` text null
- `content` text null
- `url` text not null
- `domain` text null
- `category` text not null  
  Allowed values: `stocks`, `crypto`
- `published_at` timestamptz null
- `fetched_at` timestamptz not null default now()
- `created_at` timestamptz not null default now()

### Constraints
- unique `(source_id, external_id)` when `external_id` is present
- unique `url` if the source does not provide stable IDs
- `category` restricted to `stocks` or `crypto`

### Indexes
- index on `source_id`
- index on `market_id`
- index on `category`
- index on `published_at`
- index on `domain`

---

## Table: market_snapshots

Stores time-series snapshots of market state.

### Purpose
Track how a market changes over time.

### Columns
- `id` bigserial primary key
- `market_id` bigint not null foreign key references `markets(id)`
- `snapshot_time` timestamptz not null
- `source_id` bigint not null foreign key references `sources(id)`
- `price` numeric(18,8) null
- `best_bid` numeric(18,8) null
- `best_ask` numeric(18,8) null
- `volume_24h` numeric(18,8) null
- `liquidity` numeric(18,8) null
- `raw_payload` jsonb null
- `created_at` timestamptz not null default now()

### Constraints
- each snapshot belongs to one market
- snapshot time should be stored with timezone awareness

### Indexes
- index on `market_id`
- index on `snapshot_time desc`
- index on `(market_id, snapshot_time desc)`
- index on `source_id`

---

## Table: research_reports

Stores synthesized research outputs.

### Purpose
Save human-readable summaries generated from market and news data.

### Columns
- `id` bigserial primary key
- `title` text not null
- `summary` text not null
- `details` text null
- `category` text not null  
  Allowed values: `stocks`, `crypto`
- `market_id` bigint null foreign key references `markets(id)`
- `source_window_start` timestamptz null
- `source_window_end` timestamptz null
- `status` text not null  
  Examples: `draft`, `ready`, `sent`, `failed`
- `created_at` timestamptz not null default now()
- `updated_at` timestamptz not null default now()

### Constraints
- `category` restricted to `stocks` or `crypto`

### Indexes
- index on `category`
- index on `market_id`
- index on `status`
- index on `created_at desc`

---

## Table: telegram_messages

Stores notification messages before and after sending.

### Purpose
Track outbound Telegram alerts and their delivery state.

### Columns
- `id` bigserial primary key
- `report_id` bigint null foreign key references `research_reports(id)`
- `chat_id` text not null
- `message_type` text not null  
  Examples: `alert`, `summary`, `status`
- `title` text null
- `body` text not null
- `payload` jsonb null
- `status` text not null  
  Examples: `pending`, `sending`, `sent`, `failed`
- `scheduled_for` timestamptz null
- `sent_at` timestamptz null
- `attempt_count` integer not null default 0
- `last_error` text null
- `created_at` timestamptz not null default now()
- `updated_at` timestamptz not null default now()

### Constraints
- status must be one of the allowed message states
- attempt count must be zero or greater

### Indexes
- index on `status`
- index on `scheduled_for`
- index on `chat_id`
- index on `report_id`

---

## Table: scheduler_jobs

Stores job definitions and scheduling state.

### Purpose
Let the orchestrator manage recurring jobs in a simple database-driven way.

### Columns
- `id` bigserial primary key
- `job_name` text not null
- `service_name` text not null  
  Examples: `market_ingestion`, `news_aggregation`, `research_summarization`, `telegram_notification`
- `enabled` boolean not null default true
- `schedule_type` text not null  
  Examples: `interval`, `cron`, `manual`
- `schedule_value` text not null  
  Example: `15m`, `0 */2 * * *`
- `timezone` text not null default 'UTC'
- `last_run_at` timestamptz null
- `next_run_at` timestamptz null
- `last_status` text null
- `retry_count` integer not null default 0
- `max_retries` integer not null default 3
- `created_at` timestamptz not null default now()
- `updated_at` timestamptz not null default now()

### Constraints
- unique `job_name`
- `retry_count` and `max_retries` should be non-negative

### Indexes
- index on `enabled`
- index on `next_run_at`
- index on `service_name`
- unique index on `job_name`

---

## Table: ingestion_runs

Stores one record for each ingestion execution.

### Purpose
Track every polling run and its outcome.

### Columns
- `id` bigserial primary key
- `job_id` bigint null foreign key references `scheduler_jobs(id)`
- `source_id` bigint null foreign key references `sources(id)`
- `run_type` text not null  
  Examples: `market_ingestion`, `news_aggregation`
- `status` text not null  
  Examples: `running`, `success`, `failed`, `partial`
- `started_at` timestamptz not null
- `finished_at` timestamptz null
- `items_seen` integer not null default 0
- `items_inserted` integer not null default 0
- `items_updated` integer not null default 0
- `error_message` text null
- `metadata` jsonb null
- `created_at` timestamptz not null default now()

### Constraints
- `items_seen`, `items_inserted`, and `items_updated` must be zero or greater

### Indexes
- index on `job_id`
- index on `source_id`
- index on `run_type`
- index on `status`
- index on `started_at desc`

## Recommended relationships

- `sources` is the parent table for data origins
- `markets` references `sources`
- `news_items` references `sources` and optionally `markets`
- `market_snapshots` references `markets` and `sources`
- `research_reports` can reference one market or many items indirectly through report logic
- `telegram_messages` may reference a `research_reports` row
- `scheduler_jobs` defines recurring work
- `ingestion_runs` records each execution of a job

## Minimal implementation notes

To keep the project beginner-friendly:
- start with these tables only
- avoid overly complex partitioning at first
- use JSONB only for raw payloads and metadata that do not need immediate querying
- keep category values restricted to `stocks` and `crypto`
- add more tables later only if the project needs them

## Suggested ordering for creation

1. `sources`
2. `markets`
3. `news_items`
4. `market_snapshots`
5. `research_reports`
6. `telegram_messages`
7. `scheduler_jobs`
8. `ingestion_runs`

This order makes foreign key relationships easy to apply.