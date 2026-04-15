"""Lightweight PostgreSQL helpers and repository functions for the Financial Bot."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse, parse_qs

from shared.config import Settings, settings
from shared.models import MarketItem, NewsItem, ResearchReport, TelegramMessage

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
except Exception:  # pragma: no cover - dependency may not be installed in all environments
    psycopg2 = None
    RealDictCursor = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_psycopg2() -> None:
    if psycopg2 is None:
        raise RuntimeError(
            "psycopg2 is required for database access. Install the project dependencies first."
        )


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str, ensure_ascii=False)


def _dt_to_iso(value: Optional[datetime]) -> Optional[str]:
    if value is None:
        return None
    return value.isoformat()


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


def get_database_config() -> Settings:
    return settings


def _build_connect_kwargs(db: Settings) -> Dict[str, Any]:
    dsn = getattr(db, "postgres_dsn", "") or ""
    if not dsn:
        raise RuntimeError("POSTGRES_DSN is not configured.")

    parsed = urlparse(dsn)
    connect_kwargs: Dict[str, Any] = {
        "dbname": parsed.path.lstrip("/") or None,
        "user": parsed.username,
        "password": parsed.password,
        "host": parsed.hostname,
        "port": parsed.port,
    }

    query = parse_qs(parsed.query)
    sslmode = query.get("sslmode", [None])[0]
    if sslmode:
        connect_kwargs["sslmode"] = sslmode

    return {key: value for key, value in connect_kwargs.items() if value is not None}


def get_connection(config: Optional[Settings] = None):
    """Create a new PostgreSQL connection using the project configuration."""
    _ensure_psycopg2()
    db = config or get_database_config()
    return psycopg2.connect(**_build_connect_kwargs(db))


@contextmanager
def connection(config: Optional[Settings] = None):
    conn = get_connection(config)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def cursor(config: Optional[Settings] = None):
    with connection(config) as conn:
        cur = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield cur
        finally:
            cur.close()


def fetch_one(query: str, params: Optional[Sequence[Any]] = None, config: Optional[Settings] = None) -> Dict[str, Any]:
    with cursor(config) as cur:
        cur.execute(query, params or [])
        return _row_to_dict(cur.fetchone())


def fetch_all(query: str, params: Optional[Sequence[Any]] = None, config: Optional[Settings] = None) -> List[Dict[str, Any]]:
    with cursor(config) as cur:
        cur.execute(query, params or [])
        rows = cur.fetchall() or []
        return [_row_to_dict(row) for row in rows]


def execute(query: str, params: Optional[Sequence[Any]] = None, config: Optional[Settings] = None) -> int:
    with cursor(config) as cur:
        cur.execute(query, params or [])
        return cur.rowcount


def insert_news_item(news_item: NewsItem, config: Optional[Settings] = None) -> Dict[str, Any]:
    query = """
        INSERT INTO news_items (title, summary, category, source, url, metadata, published_at, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
        RETURNING *
    """
    params = (
        news_item.title,
        news_item.summary or None,
        news_item.category or "stocks",
        news_item.source or "",
        getattr(news_item, "url", "") or None,
        _json_dumps(getattr(news_item, "metadata", {}) or {}),
        news_item.published_at,
        utcnow(),
        utcnow(),
    )
    return fetch_one(query, params, config)


def insert_research_report(report: ResearchReport, category: str = "stocks", config: Optional[Settings] = None) -> Dict[str, Any]:
    query = """
        INSERT INTO research_reports (title, summary, details, category, status, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
        RETURNING *
    """
    params = (
        report.title,
        report.summary,
        _json_dumps({"items": [asdict(item) for item in report.items], "metadata": report.metadata}),
        category,
        "ready",
        utcnow(),
        utcnow(),
    )
    return fetch_one(query, params, config)


def insert_market_item(item: MarketItem, config: Optional[Settings] = None) -> Dict[str, Any]:
    query = """
        INSERT INTO markets (
            external_id,
            title,
            category,
            url,
            source,
            score,
            metadata,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
        ON CONFLICT (external_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            category = EXCLUDED.category,
            url = EXCLUDED.url,
            source = EXCLUDED.source,
            score = EXCLUDED.score,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING *
    """
    params = (
        item.id,
        item.title,
        item.category,
        item.url or None,
        item.source,
        item.score,
        _json_dumps(item.metadata or {}),
        utcnow(),
        utcnow(),
    )
    return fetch_one(query, params, config)


def insert_telegram_message(message: TelegramMessage, config: Optional[Settings] = None) -> Dict[str, Any]:
    query = """
        INSERT INTO telegram_messages (chat_id, body, status, created_at, updated_at)
        VALUES (%s, %s, %s, COALESCE(%s, NOW()), COALESCE(%s, NOW()))
        RETURNING *
    """
    params = (
        message.chat_id,
        message.text,
        "pending",
        utcnow(),
        utcnow(),
    )
    return fetch_one(query, params, config)


def mark_telegram_message_status(message_id: int, status: str, last_error: str = "", config: Optional[Settings] = None) -> int:
    query = """
        UPDATE telegram_messages
        SET status = %s,
            last_error = %s,
            updated_at = NOW(),
            sent_at = CASE WHEN %s = 'sent' THEN COALESCE(sent_at, NOW()) ELSE sent_at END
        WHERE id = %s
    """
    return execute(query, (status, last_error or None, status, message_id), config)


def create_ingestion_run(run: Any, run_type: str, config: Optional[Settings] = None) -> Dict[str, Any]:
    query = """
        INSERT INTO ingestion_runs (run_type, status, started_at, finished_at, items_seen, items_inserted, items_updated, error_message, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, COALESCE(%s, NOW()))
        RETURNING *
    """
    params = (
        run_type,
        getattr(run, "status", "running"),
        getattr(run, "started_at", utcnow()),
        getattr(run, "finished_at", None),
        getattr(run, "items_seen", getattr(run, "items_ingested", 0)),
        getattr(run, "items_inserted", 0),
        getattr(run, "items_updated", 0),
        getattr(run, "error_message", None),
        _json_dumps(getattr(run, "metadata", {}) or {}),
        utcnow(),
    )
    return fetch_one(query, params, config)


def list_ready_telegram_messages(limit: int = 25, config: Optional[Settings] = None) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM telegram_messages
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT %s
    """
    return fetch_all(query, (limit,), config)


def list_open_markets(category: str = "stocks", limit: int = 100, config: Optional[Settings] = None) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM markets
        WHERE category = %s
        ORDER BY updated_at DESC
        LIMIT %s
    """
    return fetch_all(query, (category, limit), config)


def list_recent_news(category: str = "stocks", limit: int = 100, config: Optional[Settings] = None) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM news_items
        WHERE category = %s
        ORDER BY COALESCE(published_at, created_at) DESC
        LIMIT %s
    """
    return fetch_all(query, (category, limit), config)


def list_recent_reports(category: str = "stocks", limit: int = 25, config: Optional[Settings] = None) -> List[Dict[str, Any]]:
    query = """
        SELECT *
        FROM research_reports
        WHERE category = %s
        ORDER BY created_at DESC
        LIMIT %s
    """
    return fetch_all(query, (category, limit), config)
