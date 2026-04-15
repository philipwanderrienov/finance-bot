# Telegram Integration Contract

This document defines how the Financial Bot sends Telegram notifications.

The Telegram integration belongs to a dedicated **telegram-notification** service. Its job is to:
- read ready-to-send messages from storage
- format messages for Telegram
- apply chat settings and rate limiting
- send messages through the Telegram Bot API
- persist send status before and after delivery
- support the current worker mode flow used by the orchestrator

The goal is to keep Telegram delivery reliable, predictable, and easy to understand.

---

## 1) Design goals

The Telegram service should:
- send alerts in a consistent format
- support multiple alert types
- respect quiet hours and rate limits
- persist messages before sending
- record success or failure for every attempt
- stay focused only on notification delivery

It should not:
- poll external APIs directly
- summarize news
- make market decisions

Those responsibilities belong to other services.

---

## 2) Message flow

A simple message flow is:

1. A producer service creates a notification request
2. The request is stored in PostgreSQL as a pending Telegram message
3. The Telegram service reads pending messages
4. The service formats the message
5. The service checks chat settings and rate limits
6. The service sends the message to Telegram
7. The service updates the message status in the database

This makes sending observable and retryable.

---

## 3) Persistent message states

Telegram messages should be saved before delivery so no alert is lost if the service restarts.

Recommended states:
- `pending` — ready to be sent
- `sending` — currently being delivered
- `sent` — successfully delivered
- `failed` — delivery failed after retries
- `skipped` — not sent due to quiet hours, disabled chat, or filtering

Recommended fields in storage:
- message id
- chat id
- alert type
- subject
- message body
- formatted text
- status
- priority
- retry count
- scheduled send time
- last error
- created time
- sent time

---

## 4) Alert types

The bot should support a small, clear set of alert types.

### Suggested alert types
- `market_update`
- `news_update`
- `research_summary`
- `price_movement`
- `trend_change`
- `error`
- `system_status`

### Beginner-friendly meaning
- `market_update`: a new market or market snapshot is available
- `news_update`: a relevant news article was found
- `research_summary`: a summarization service produced an analysis
- `price_movement`: a notable price or probability change was detected
- `trend_change`: a trend or sentiment shift was detected
- `error`: something went wrong and needs attention
- `system_status`: routine service health or startup/shutdown notification

---

## 5) Message format

Messages should be short, readable, and useful on mobile.

### Suggested structure
- title line
- alert type
- main summary
- key metrics
- source
- timestamp
- optional link

Example format:

```text
[Market Update] BTC-related event detected

Source: Polymarket
Type: market_update
Summary: New market snapshot suggests higher activity in crypto-related contracts.
Key data:
- Price: 0.63
- Change: +4.2%
- Volume: 12500

Time: 2026-04-15 12:30 UTC
```

### Formatting rules
- keep the first line short and clear
- put the most important information first
- use bullet points for metrics
- include a timestamp
- include a source label
- include a link when available

---

## 6) Telegram-friendly formatting

Telegram supports simple formatting. To keep things easy:
- plain text should work by default
- optional Markdown-style emphasis can be used carefully
- avoid overly complex formatting that may break messages

Recommended style:
- bold title
- short labels
- line breaks for readability

If formatting is added later, keep it consistent across all alerts.

---

## 7) Chat settings

Each Telegram chat or channel should have its own settings.

### Suggested settings
- `chat_id`
- `enabled`
- `display_name`
- `allowed_alert_types`
- `quiet_hours_enabled`
- `quiet_hours_start`
- `quiet_hours_end`
- `min_priority`
- `language`
- `is_group`
- `is_channel`

### Behavior
A chat can choose:
- which alert types it wants
- whether quiet hours apply
- the minimum priority it accepts

Example:
- a private admin chat may receive `error` and `system_status`
- a public channel may receive only `market_update` and `news_update`

---

## 8) Rate limiting

Telegram delivery should be rate-limited so the bot does not send too many messages too quickly.

### Rate limiting goals
- protect against Telegram API limits
- reduce spam
- keep the notification stream readable

### Suggested rate limit settings
- `messages_per_minute`
- `messages_per_chat_per_minute`
- `burst_limit`
- `cooldown_seconds`

Example configuration:

```yaml
telegram:
  rate_limit:
    messages_per_minute: 20
    messages_per_chat_per_minute: 5
    burst_limit: 3
    cooldown_seconds: 2
```

### Suggested behavior
- send high-priority alerts first
- queue lower-priority alerts if limits are reached
- retry later instead of dropping messages immediately
- record rate-limit delays in the database

---

## 9) Quiet hours and delivery rules

Telegram delivery should respect the scheduler quiet-hours policy when possible.

### Suggested rule
- if quiet hours are active, do not send low-priority messages
- allow important error or system alerts if needed
- mark skipped messages clearly in storage

This prevents unnecessary notifications while keeping critical alerts visible.

---

## 10) Persistence before sending

Every message must be persisted before the service tries to send it.

### Required steps
1. Create a `pending` record in PostgreSQL
2. Save the intended destination chat and message content
3. Mark the message as `sending` when delivery begins
4. Update the record to `sent` or `failed`
5. Store the Telegram response metadata when available

### Why this matters
If the service crashes:
- pending messages are not lost
- failed messages can be retried
- duplicates can be avoided by checking message status

---

## 11) Retry policy for sending

Sending can fail for temporary reasons such as network issues or Telegram rate limits.

### Suggested retry settings
- `max_retries`: 3
- `backoff_seconds`: 10
- `max_backoff_seconds`: 120

### Retry rules
Retry only for temporary failures:
- network timeout
- 429 rate limit response
- temporary Telegram API failure

Do not retry forever. If all attempts fail:
- mark the message as `failed`
- store the final error
- optionally alert an admin chat

---

## 12) Message priorities

A simple priority system helps the bot decide what to send first.

### Suggested priority levels
- `low`
- `normal`
- `high`
- `critical`

### Example usage
- `low`: routine market update
- `normal`: news item related to tracked assets
- `high`: strong price movement
- `critical`: service failure or urgent data issue

Priority can affect:
- ordering in the queue
- whether quiet hours apply
- retry speed

---

## 13) Telegram API interaction

The service should isolate Telegram-specific API calls in one place.

Responsibilities:
- authenticate with the bot token
- send text messages
- handle send errors
- capture message IDs and timestamps
- avoid direct Telegram calls from other services

This keeps the rest of the system independent from Telegram details.

---

## 14) Suggested environment variables

A simple configuration set could be:

- `TELEGRAM_ENABLED=true`
- `TELEGRAM_BOT_TOKEN=...`
- `TELEGRAM_DEFAULT_CHAT_ID=...`
- `TELEGRAM_RATE_LIMIT_MESSAGES_PER_MINUTE=20`
- `TELEGRAM_RATE_LIMIT_MESSAGES_PER_CHAT_PER_MINUTE=5`
- `TELEGRAM_RATE_LIMIT_BURST_LIMIT=3`
- `TELEGRAM_RATE_LIMIT_COOLDOWN_SECONDS=2`
- `TELEGRAM_MAX_RETRIES=3`
- `TELEGRAM_BACKOFF_SECONDS=10`
- `TELEGRAM_MAX_BACKOFF_SECONDS=120`

---

## 15) Suggested database integration

The Telegram service should read and update a `telegram_messages` table.

Typical workflow:
- insert new message rows with `pending`
- select pending rows for sending
- lock or claim the row during delivery
- update status after the API response
- store retry count and error details

This makes delivery auditable and easy to debug.

---

## 16) Example message templates

### Market update
```text
[Market Update] New Polymarket snapshot

Source: Polymarket
Category: crypto
Summary: Activity increased on crypto-related markets.
Change: +4.2%
Time: 2026-04-15 12:30 UTC
```

### News update
```text
[News Update] Relevant article found

Source: News API
Category: stocks
Summary: A new article may affect tracked equities.
Headline: Major company reports earnings beat
Time: 2026-04-15 12:40 UTC
```

### Research summary
```text
[Research Summary] Daily analysis ready

Summary: The latest report highlights stronger momentum in crypto markets.
Confidence: Medium
Time: 2026-04-15 13:00 UTC
```

---

## 17) Beginner-friendly defaults

Recommended first-version defaults:
- one default chat
- plain text messages
- pending/sent/failed status tracking
- modest rate limits
- simple retry logic
- quiet hours respected for non-critical alerts
- compatible with the smoke test command in `scripts/smoke_test.py`

This keeps the integration easy to operate while still being reliable.

---

## 18) Notes for microservices

The Telegram service should only handle:
- message formatting
- message persistence
- message sending
- delivery status updates

Other services should only create message requests. They should not know Telegram API details.

This separation keeps the system modular and easy to extend later.