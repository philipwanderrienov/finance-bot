from __future__ import annotations

from typing import Any

from shared.config import settings
from shared.db import insert_market_item
from shared.polymarket import fetch_all_market_sources, market_item_to_dict, utc_now_iso


def build_ingestion_batch(limit: int = 20) -> dict[str, Any]:
    items = fetch_all_market_sources(limit=limit)
    filtered = [item for item in items if item.category in {"stocks", "crypto"}]
    persisted_items = []
    persisted_count = 0
    failed_count = 0
    for item in filtered:
        try:
            persisted_items.append(insert_market_item(item))
            persisted_count += 1
        except Exception as exc:
            failed_count += 1
            error_message = str(exc)
            persisted_items.append({"id": item.id, "title": item.title, "error": error_message})
            print(f"[ingestion] failed to persist {item.id} ({item.title}): {error_message}")
    print(
        f"[ingestion] persistence complete: {persisted_count} inserted, "
        f"{failed_count} failed, {len(filtered)} attempted"
    )
    return {
        "generated_at": utc_now_iso(),
        "source_count": len(items),
        "filtered_count": len(filtered),
        "persisted_count": persisted_count,
        "failed_count": failed_count,
        "items": [market_item_to_dict(item) for item in filtered],
        "persisted_items": persisted_items,
        "settings": {
            "stocks_market_enabled": settings.stocks_market_enabled,
            "crypto_market_enabled": settings.crypto_market_enabled,
        },
    }


def main() -> dict[str, Any]:
    batch = build_ingestion_batch(limit=20)
    print(f"[ingestion] collected {batch['source_count']} market items")
    print(
        f"[ingestion] wrote {batch['persisted_count']} rows to PostgreSQL "
        f"with {batch['failed_count']} failures"
    )
    return batch


if __name__ == "__main__":
    main()
