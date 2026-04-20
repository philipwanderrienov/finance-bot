from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable

from backend.services.advisor_engine import generate_advisory_payload
from shared.db import list_open_markets
from shared.models import MarketItem
from shared.polymarket_efficiency import (
    cache_snapshot,
    fetch_all_market_sources,
    fetch_gamma_markets,
    fetch_market_signals,
    fetch_public_clob_markets,
    get_cached_result,
    get_polymarket_access_layer,
)

ACCESS_LAYER = get_polymarket_access_layer()


def _rows_to_market_items(rows: Iterable[dict[str, Any]]) -> list[MarketItem]:
    items: list[MarketItem] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata")
        if isinstance(metadata, str):
            try:
                import json

                metadata = json.loads(metadata)
            except Exception:
                metadata = {}
        if not isinstance(metadata, dict):
            metadata = {}

        item_id = str(row.get("external_id") or row.get("slug") or row.get("id") or len(items))
        title = str(row.get("title") or row.get("question") or row.get("name") or "Untitled market")
        items.append(
            MarketItem(
                id=item_id,
                title=title,
                category=str(row.get("category") or "stocks"),
                source=str(row.get("source") or "database"),
                url=str(row.get("url") or ""),
                score=float(row.get("score") or metadata.get("score") or 0.0),
                metadata=metadata,
            )
        )
    return items


def get_market_feed(limit: int = 20, include_database: bool = True) -> dict[str, Any]:
    markets = fetch_all_market_sources(limit=limit, use_cache=True)
    db_markets: list[MarketItem] = []
    if include_database:
        try:
            db_rows = list_open_markets(category="crypto", limit=limit)
            db_markets = _rows_to_market_items(db_rows)
        except Exception as exc:
            print(f"[orchestrator] database market lookup failed: {exc}")

    merged: dict[str, MarketItem] = {}
    for item in db_markets + markets:
        merged.setdefault(item.id, item)

    feed = list(merged.values())[:limit]
    return {
        "markets": [asdict(item) for item in feed],
        "signals": fetch_market_signals(limit=limit, use_cache=True).get("signals", {}),
        "cache": cache_snapshot(),
        "source_count": len(feed),
    }


def get_polymarket_snapshot(limit: int = 20) -> dict[str, Any]:
    layer = ACCESS_LAYER
    return {
        "gamma": [asdict(item) for item in fetch_gamma_markets(limit=limit, use_cache=True)],
        "public_clob": [asdict(item) for item in fetch_public_clob_markets(limit=limit, use_cache=True)],
        "combined": [asdict(item) for item in fetch_all_market_sources(limit=limit, use_cache=True)],
        "signals": fetch_market_signals(limit=limit, use_cache=True),
        "cache": layer.cache_snapshot(),
    }


def get_dashboard(limit: int = 20, category: str = "stocks") -> dict[str, Any]:
    advisory = generate_advisory_payload(category=category, market_limit=limit, news_limit=limit)
    recommendations = advisory.get("recommendations", [])
    buy_items = [item for item in recommendations if str(item.get("recommendation", "")).lower() == "buy"]
    sell_items = [item for item in recommendations if str(item.get("recommendation", "")).lower() == "sell"]
    hold_items = [item for item in recommendations if str(item.get("recommendation", "")).lower() == "hold"]

    return {
        "ok": True,
        "dashboard": {
            "summary": {
                "portfolio": advisory.get("portfolio_impact", {}),
                "sentiment": {"metrics": advisory.get("sentiment", {})},
            },
            "sections": {
                "stockRecommendations": {
                    "subsections": {
                        "buy": {"items": buy_items},
                        "sell": {"items": sell_items},
                        "hold": {"items": hold_items},
                    }
                }
            },
            "sharedMeta": {
                "generatedAt": advisory.get("generated_at"),
                "category": category,
                "limit": limit,
                "recommendationCount": len(recommendations),
            },
        },
        "advisory": advisory,
    }


def get_cached_polymarket_result(cache_key: str) -> Any | None:
    return get_cached_result(cache_key)


def main() -> int:
    snapshot = get_polymarket_snapshot(limit=10)
    print(
        "[orchestrator] polymarket snapshot "
        f"combined={len(snapshot.get('combined', []))} "
        f"cache_entries={len(snapshot.get('cache', {}))}"
    )
    return 0


def run() -> int:
    return main()


def start() -> int:
    return main()


app = main