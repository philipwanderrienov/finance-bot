# finance-bot

Finance bot for orchestrating simple market research flows around stocks market and crypto.

## What it does

This repository is organized as a small set of synchronous Python services:

- `orchestrator` - coordinates a polling cycle and can run in worker mode
- `ingestion` - fetches Polymarket market data
- `aggregation` - filters and clusters news items
- `research` - creates a simple report object
- `telegram_notifier` - prepares and sends a Telegram message

The project is intentionally beginner-friendly and keeps authenticated Polymarket CLOB trading out of scope.

## Requirements

- Python 3.11+
- PostgreSQL
- A Telegram bot token if you want notifications
- Optional public access to Polymarket Gamma/Data endpoints and public CLOB read endpoints

## Configuration

Copy `.env.example` to `.env` and fill in the values.

Important:
- the database env values must be filled in by you
- if PostgreSQL is unreachable, the services should log a clear message and continue in a safe no-op or demo mode instead of crashing

Typical environment variables used by the app:

- `DATABASE_URL`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `POLYMARKET_GAMMA_API_URL`
- `POLYMARKET_DATA_API_URL`
- `POLYMARKET_CLOB_API_URL`

See `shared/config.py` for the exact field names expected by the code. The shared package now exports `Settings` and the module-level `settings` instance.

## Run the services

The repo includes a CLI launcher in `main.py`. Run it with one of the service names:

```bash
python main.py orchestrator
python main.py ingestion
python main.py aggregation
python main.py research
python main.py telegram_notifier
```

The orchestrator also has a worker mode for running background jobs when configured that way. In worker mode, a single recoverable stage or network error is logged and the next cycle continues after the backoff.

If your launcher supports a help flag, you can inspect available commands with:

```bash
python main.py --help
```

## Smoke test

Run the smoke test from the repository root:

```bash
python scripts/smoke_test.py
```

This imports the shared package and service entrypoints and prints a clear pass/fail message. It expects the current shared config exports (`Settings` and `settings`) rather than the older `AppConfig` names.

## Project layout

- `main.py` - CLI launcher
- `shared/` - config, models, database, Polymarket, and Telegram helpers
- `services/` - runnable service entrypoints
- `scripts/` - simple utility scripts such as the smoke test
- `docs/` - architecture and integration notes

## Notes

- Polymarket authenticated trading is not implemented.
- The implementation focuses on stocks market and crypto only.
- Keep the services synchronous and simple for ease of use.