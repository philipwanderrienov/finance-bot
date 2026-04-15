# Scheduler Configuration Contract

This document defines the configuration contract for the **scheduler/orchestrator** service in the Financial Bot.

The scheduler is responsible for:
- polling Polymarket public data sources
- polling external news sources
- honoring quiet hours and rate limits
- retrying failed runs safely
- sending work to downstream services such as research summarization and Telegram notification
- running in worker mode when configured for background processing

The goal is to keep the scheduler **simple, adjustable, and beginner-friendly**.

---

## 1) Design goals

The scheduler should:
- be configurable without code changes
- support enable/disable switching
- poll Polymarket and news sources on different schedules
- stay focused on **stocks market** and **crypto** only
- avoid sending too many requests too quickly
- support quiet hours so alerts are not sent at inconvenient times
- keep a clear record of each run in PostgreSQL

---

## 2) Configuration shape

The scheduler reads its settings from environment variables or a config file, then stores the effective settings in the `scheduler_jobs` and `ingestion_runs` tables when appropriate.

A beginner-friendly configuration object could look like this:

```yaml
scheduler:
  enabled: true
  timezone: "UTC"
  polling_interval_seconds: 300
  quiet_hours:
    enabled: false
    start: "22:00"
    end: "07:00"
  retry_policy:
    max_retries: 3
    backoff_seconds: 30
    max_backoff_seconds: 300
  request_timeout_seconds: 20
  max_items_per_run: 50
  domain_filter:
    allowed_domains:
      - stocks
      - crypto
  output_destination: "postgresql"
  per_source:
    polymarket:
      enabled: true
      interval_seconds: 300
      max_items_per_run: 25
      timeout_seconds: 15
    news_api:
      enabled: true
      interval_seconds: 900
      max_items_per_run: 20
      timeout_seconds: 20
```

---

## 3) Core options

### `enabled`
- Type: `boolean`
- Default: `true`
- Meaning: turns the scheduler on or off

When disabled:
- no polling occurs
- no downstream jobs are created
- existing config is still loaded and validated

---

### `timezone`
- Type: `string`
- Default: `"UTC"`
- Meaning: timezone used for quiet hours and schedule evaluation

Use one timezone consistently across the scheduler. UTC is the simplest choice for a distributed system.

---

### `polling_interval_seconds`
- Type: `integer`
- Default: `300`
- Meaning: default interval between scheduler checks

This is the main loop interval for the orchestrator. It does not have to be the exact interval for every source, because each source may define its own schedule.

---

### `request_timeout_seconds`
- Type: `integer`
- Default: `20`
- Meaning: default timeout for external HTTP requests

This protects the scheduler from hanging on slow APIs.

---

### `max_items_per_run`
- Type: `integer`
- Default: `50`
- Meaning: maximum total items the scheduler may fetch or enqueue in one run

This prevents the bot from overwhelming downstream services when a source suddenly returns many results.

---

### `output_destination`
- Type: `string`
- Default: `"postgresql"`
- Allowed values:
  - `postgresql`
  - `queue`
  - `webhook`

This describes where the scheduler sends its results after a successful poll.

For the first version of the project, `postgresql` is the simplest and safest choice.

---

## 4) Quiet hours

Quiet hours are used to reduce or pause outgoing notifications.

### `quiet_hours.enabled`
- Type: `boolean`
- Default: `false`

### `quiet_hours.start`
- Type: `string`
- Example: `"22:00"`

### `quiet_hours.end`
- Type: `string`
- Example: `"07:00"`

### Behavior
If quiet hours are enabled:
- the scheduler may still collect data
- the scheduler should delay or queue notifications
- urgency rules can override quiet hours if needed

Recommended beginner-friendly rule:
- ingest data at any time
- suppress Telegram sending during quiet hours unless the alert type is marked as high priority

---

## 5) Per-source schedules

Different sources should be able to run on different schedules.

### `per_source`
A map of source-specific settings.

Example sources:
- `polymarket`
- `news_api`
- `rss_feeds`
- `manual_curated_feeds`

Each source can define:
- `enabled`
- `interval_seconds`
- `cron`
- `timeout_seconds`
- `max_items_per_run`
- `retry_policy`

Example:

```yaml
per_source:
  polymarket:
    enabled: true
    interval_seconds: 300
    timeout_seconds: 15
    max_items_per_run: 25
  news_api:
    enabled: true
    interval_seconds: 900
    timeout_seconds: 20
    max_items_per_run: 20
```

### Supported schedule styles
The scheduler may support either of these:
- fixed interval polling, such as every 5 minutes
- cron-like schedules for advanced control

For beginner-friendliness, interval polling should be the default.

---

## 6) Retry policy

Retries help recover from temporary network or API failures.

### `retry_policy.max_retries`
- Type: `integer`
- Default: `3`

### `retry_policy.backoff_seconds`
- Type: `integer`
- Default: `30`

### `retry_policy.max_backoff_seconds`
- Type: `integer`
- Default: `300`

### Suggested behavior
- retry only transient failures
- use exponential backoff
- stop after the maximum retry count
- record retry attempts in `ingestion_runs`

Example:
1. first failure: wait 30 seconds
2. second failure: wait 60 seconds
3. third failure: wait 120 seconds
4. stop after max retries

---

## 7) Domain filter

The project only covers **stocks market** and **crypto**.

### `domain_filter.allowed_domains`
- Type: array of strings
- Default:
  - `stocks`
  - `crypto`

The scheduler must reject or ignore other domains such as:
- sports
- politics
- entertainment
- gaming

This filter should apply to:
- Polymarket market ingestion
- news source ingestion
- summarization jobs
- Telegram alerts

---

## 8) Output destination

The output destination defines where collected data goes after polling.

### Common destinations
- `postgresql`: store raw and processed records in the database
- `queue`: send work to a job queue
- `webhook`: call another service over HTTP

For this repository, the simplest supported path is:
1. scheduler fetches source data
2. scheduler stores ingestion results in PostgreSQL
3. other services read from the database or receive queued work

---

## 9) Suggested environment variables

A simple implementation can map configuration into environment variables:

- `SCHEDULER_ENABLED=true`
- `SCHEDULER_TIMEZONE=UTC`
- `SCHEDULER_POLLING_INTERVAL_SECONDS=300`
- `SCHEDULER_QUIET_HOURS_ENABLED=false`
- `SCHEDULER_QUIET_HOURS_START=22:00`
- `SCHEDULER_QUIET_HOURS_END=07:00`
- `SCHEDULER_RETRY_MAX_RETRIES=3`
- `SCHEDULER_RETRY_BACKOFF_SECONDS=30`
- `SCHEDULER_RETRY_MAX_BACKOFF_SECONDS=300`
- `SCHEDULER_REQUEST_TIMEOUT_SECONDS=20`
- `SCHEDULER_MAX_ITEMS_PER_RUN=50`
- `SCHEDULER_OUTPUT_DESTINATION=postgresql`
- `SCHEDULER_ALLOWED_DOMAINS=stocks,crypto`

---

## 10) Persistence expectations

The scheduler should persist each run so the system can answer:
- when did a poll happen?
- which source was checked?
- how many items were found?
- did the run succeed or fail?
- what retry attempts happened?

Recommended tables:
- `scheduler_jobs`
- `ingestion_runs`

Typical data to store:
- job name
- source name
- schedule type
- next run time
- last run time
- run status
- error message
- item counts
- timestamps

---

## 11) Suggested run flow

A simple scheduler loop can work like this:

1. Load config
2. Check whether the scheduler is enabled
3. Determine which sources are due
4. Skip sources outside the allowed domains
5. Poll the source with timeout and retry rules
6. Save raw result metadata to PostgreSQL
7. Enqueue or trigger downstream processing
8. Record the run outcome
9. Sleep until the next polling interval

When the orchestrator is running in worker mode, it should keep processing background work until stopped.

---

## 12) Beginner-friendly defaults

Recommended defaults for the first version:
- `enabled = true`
- `timezone = UTC`
- `polling_interval_seconds = 300`
- `quiet_hours.enabled = false`
- `request_timeout_seconds = 20`
- `max_items_per_run = 50`
- `allowed_domains = [stocks, crypto]`
- `output_destination = postgresql`

These defaults are easy to understand and safe for a small deployment.

---

## 13) Notes for microservices

The scheduler should not contain business logic for ranking or summarizing news. Its job is only to:
- decide what to poll
- fetch data
- apply basic filtering
- store the result
- notify other services

This keeps the service small and easy to maintain.