# Financial Bot Architecture

## Overview

Financial Bot is a beginner-friendly Python microservices project focused on:

- Stock market news
- Crypto news
- Polymarket market monitoring
- A frontend dashboard for presenting market data and recommendations

The system is split into small Python services that each do one job. This keeps the project simple for beginners while still matching a real microservices design.

## Services

### 1. Scheduler / Orchestrator
**Job:** Decide when each task should run.

**Responsibilities:**
- Reads scheduler config
- Triggers polling on a fixed interval
- Supports quiet hours and retry rules
- Can run in worker mode for background jobs
- Starts ingestion jobs for markets and news
- Starts research summarization jobs
- Records job execution status

**Why it exists:**
- It is the central control plane for the bot
- It avoids mixing scheduling logic into every service

### 2. Market Ingestion Service
**Job:** Fetch and store market data.

**Responsibilities:**
- Polls public Polymarket APIs
- Filters for stocks market and crypto focus
- Stores market metadata
- Stores market snapshots over time
- Tracks which sources were checked in each run

**Input examples:**
- Polymarket Gamma API
- Polymarket Data API
- Public CLOB market snapshots when needed

**Output:**
- New or updated markets
- Time-series snapshots for analysis

### 3. News Aggregation Service
**Job:** Collect external news items.

**Responsibilities:**
- Polls external news sources
- Filters by domain and topic
- Keeps only stocks and crypto related items
- Deduplicates repeated articles
- Stores normalized news records

**Output:**
- Clean news items ready for summarization

### 4. Research Summarization Service
**Job:** Turn market and news data into short research reports.

**Responsibilities:**
- Combines fresh news with market snapshots
- Produces simple summaries for humans
- Generates dashboard-ready insights
- Saves reports to the database

**Output:**
- Structured research reports
- Dashboard JSON payloads

### 5. Frontend Dashboard
**Job:** Present the latest market and recommendation data in the browser.

**Responsibilities:**
- Fetch structured API responses from the backend
- Render a markets grid
- Render buy/sell stock recommendation sections
- Display price details, summaries, and metadata
- Refresh the view as new backend data becomes available

**Output:**
- Human-friendly dashboard UI
- Browser-based presentation layer

## How the services communicate

The system uses PostgreSQL as the shared source of truth.

### Communication pattern
- Scheduler writes jobs into the database
- Worker services read jobs or run on scheduler triggers
- Ingestion services write data into database tables
- Research service reads recent markets and news
- Orchestrator prepares dashboard payloads for the frontend
- Frontend reads structured JSON from the backend API
- Each service updates status fields so others can see progress

### Beginner-friendly rule
Each backend service should:
1. Read the data it needs
2. Do one clear task
3. Write the result back to PostgreSQL

If PostgreSQL is unavailable, services should log a clear message and continue in a safe no-op or demo mode instead of crashing.

This keeps communication simple and avoids needing a message broker at the start.

## Data flow

A typical run looks like this:

1. Scheduler checks whether a job should run
2. Market ingestion fetches Polymarket market updates
3. News aggregation fetches related news articles
4. Research summarization combines the new data into a report
5. Orchestrator prepares a dashboard payload from the latest data
6. The frontend dashboard fetches and renders the payload
7. Each step stores its result in PostgreSQL

## Deployment notes

### Recommended local layout
- One container or process per service
- One PostgreSQL database shared by all services
- One `.env` or config file per environment

### Suggested runtime setup
- `scheduler` service runs continuously
- `scheduler` can also operate in worker mode for background jobs
- `market-ingestion` service can be started by the scheduler or on demand
- `news-aggregation` service can also run on a schedule
- `research-summarization` service runs after fresh data is available
- `frontend-dashboard` runs as a separate Vite app and calls the backend API

### Launcher note
For local development, `python main.py backend` can start the backend API and orchestrator together from one command. The lower-level services still matter when you want to run ingestion, aggregation, or research separately, or when you need to test a specific stage in isolation.

### Beginner-friendly deployment idea
Start with a single machine or local Docker Compose setup:
- Python service containers
- PostgreSQL container
- Environment variables for API keys and Telegram settings

## Focus and scope

This project only focuses on:
- Stocks market
- Crypto
- Polymarket related market data from Gamma, Data, and public CLOB read endpoints
- News relevant to those topics
- A browser-based dashboard for viewing market data and recommendation summaries

It does not support:
- authenticated Polymarket trading
- general-purpose markets
- unrelated domains
- Telegram-first presentation

## Design goals

- Simple to understand
- Easy to extend later
- Clean separation between services
- PostgreSQL-first design
- Minimal dependencies
- Beginner-friendly Python implementation