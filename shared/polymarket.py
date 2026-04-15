from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json
import ssl
import time

from shared.config import settings
from shared.models import MarketItem


def _fetch_json(url: str, timeout: int = 15, retries: int = 3, backoff_seconds: float = 1.0) -> Any:
    request = Request(url, headers={"User-Agent": "finance-bot/1.0"})
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except (ssl.SSLError, TimeoutError, HTTPError, URLError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(backoff_seconds * (2 ** attempt))
                continue
            raise last_error


def fetch_gamma_markets(limit: int = 20) -> list[MarketItem]:
    url = f"{settings.gamma_api_base_url.rstrip('/')}/markets?limit={int(limit)}"
    try:
        payload = _fetch_json(url)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return []

    items: list[MarketItem] = []
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("markets") or payload.get("data") or []
    else:
        raw_items = []

    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or raw.get("tag") or "stocks").lower()
        if category not in {"stocks", "crypto"}:
            continue
        items.append(
            MarketItem(
                id=str(raw.get("id") or raw.get("market_id") or raw.get("slug") or len(items)),
                title=str(raw.get("question") or raw.get("title") or raw.get("name") or "Untitled market"),
                category=category,
                source="polymarket_gamma",
                url=str(raw.get("url") or raw.get("market_url") or ""),
                score=float(raw.get("score") or raw.get("liquidity") or 0.0),
                metadata=raw,
            )
        )
    return items[:limit]


def fetch_data_api_items(limit: int = 20) -> list[MarketItem]:
    url = f"{settings.data_api_base_url.rstrip('/')}/markets?limit={int(limit)}"
    try:
        payload = _fetch_json(url)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return []

    raw_items = payload if isinstance(payload, list) else payload.get("data") or payload.get("markets") or []
    items: list[MarketItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or raw.get("asset_class") or "stocks").lower()
        if category not in {"stocks", "crypto"}:
            continue
        items.append(
            MarketItem(
                id=str(raw.get("id") or raw.get("market_id") or len(items)),
                title=str(raw.get("title") or raw.get("question") or "Untitled market"),
                category=category,
                source="polymarket_data_api",
                url=str(raw.get("url") or ""),
                score=float(raw.get("score") or raw.get("volume") or 0.0),
                metadata=raw,
            )
        )
    return items[:limit]


def fetch_public_clob_markets(limit: int = 20) -> list[MarketItem]:
    url = f"{settings.clob_api_base_url.rstrip('/')}/markets"
    try:
        payload = _fetch_json(url)
    except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError):
        return []

    raw_items = payload if isinstance(payload, list) else payload.get("data") or payload.get("markets") or []
    items: list[MarketItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        category = str(raw.get("category") or raw.get("market_type") or "stocks").lower()
        if category not in {"stocks", "crypto"}:
            continue
        items.append(
            MarketItem(
                id=str(raw.get("id") or raw.get("market_id") or len(items)),
                title=str(raw.get("question") or raw.get("title") or "Untitled market"),
                category=category,
                source="polymarket_clob_public",
                url=str(raw.get("url") or ""),
                score=float(raw.get("score") or 0.0),
                metadata=raw,
            )
        )
    return items[:limit]


def fetch_all_market_sources(limit: int = 20) -> list[MarketItem]:
    combined = fetch_gamma_markets(limit) + fetch_data_api_items(limit) + fetch_public_clob_markets(limit)
    deduped: dict[str, MarketItem] = {}
    for item in combined:
        deduped[item.id] = item
    return list(deduped.values())[:limit]


def market_item_to_dict(item: MarketItem) -> dict[str, Any]:
    data = asdict(item)
    data["metadata"] = item.metadata
    return data


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
