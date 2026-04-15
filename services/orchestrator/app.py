from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from services.aggregation.app import build_news_items_from_markets, summarize_clusters
from services.ingestion.app import build_ingestion_batch
from services.research.app import build_research_report
from services.telegram_notifier.app import main as send_telegram_update
from shared.config import settings
from shared.models import MarketItem, NewsItem


def _batch_to_market_items(batch: dict[str, Any]) -> list[MarketItem]:
    items: list[MarketItem] = []
    for raw in batch.get("items", []):
        if not isinstance(raw, dict):
            continue
        items.append(
            MarketItem(
                id=str(raw.get("id", "")),
                title=str(raw.get("title", "Untitled market")),
                category=str(raw.get("category", "stocks")),
                source=str(raw.get("source", "polymarket")),
                url=str(raw.get("url", "")),
                score=float(raw.get("score", 0.0)),
                metadata=raw,
            )
        )
    return items


def _batch_to_news_items(batch: dict[str, Any]) -> list[NewsItem]:
    market_items = _batch_to_market_items(batch)
    return build_news_items_from_markets(market_items)


def run_polling_cycle(limit: int = 20) -> dict[str, Any]:
    cycle_result: dict[str, Any] = {
        "ingestion": {},
        "aggregation": {},
        "research": None,
        "telegram": None,
        "errors": [],
    }

    try:
        ingestion_batch = build_ingestion_batch(limit=limit)
        cycle_result["ingestion"] = ingestion_batch
    except Exception as exc:
        cycle_result["errors"].append(f"ingestion: {exc}")
        ingestion_batch = {"items": []}

    news_items = _batch_to_news_items(ingestion_batch)

    try:
        aggregation = summarize_clusters(news_items)
        cycle_result["aggregation"] = aggregation
    except Exception as exc:
        cycle_result["errors"].append(f"aggregation: {exc}")
        aggregation = {"cluster_count": 0, "clusters": []}
        cycle_result["aggregation"] = aggregation

    try:
        research_report = build_research_report(news_items)
        cycle_result["research"] = {
            "id": research_report.id,
            "title": research_report.title,
            "summary": research_report.summary,
            "generated_at": research_report.generated_at.isoformat(),
            "item_count": len(research_report.items),
        }
    except Exception as exc:
        cycle_result["errors"].append(f"research: {exc}")
        research_report = None

    try:
        if research_report is not None:
            telegram_result = send_telegram_update(
                {
                    "title": research_report.title,
                    "summary": research_report.summary,
                    "item_count": len(research_report.items),
                }
            )
        else:
            telegram_result = {"ok": False, "skipped": True, "reason": "research unavailable"}
        cycle_result["telegram"] = telegram_result
    except Exception as exc:
        cycle_result["errors"].append(f"telegram: {exc}")
        cycle_result["telegram"] = {"ok": False, "error": str(exc)}

    return cycle_result


def _safe_sleep(seconds: int) -> None:
    time.sleep(max(1, seconds))


def run_worker_loop() -> None:
    interval_seconds = max(1, int(settings.scheduler_interval_seconds))
    backoff_seconds = max(1, min(int(settings.scheduler_backoff_seconds), int(settings.scheduler_max_backoff_seconds)))
    print(f"[orchestrator] starting worker loop (interval={interval_seconds}s, backoff={backoff_seconds}s)")

    while True:
        cycle_started = datetime.now(timezone.utc).isoformat()
        print(f"[orchestrator] cycle started at {cycle_started}")

        try:
            cycle_result = run_polling_cycle(limit=20)
            errors = cycle_result.get("errors", [])
            if errors:
                for error in errors:
                    print(f"[orchestrator] stage error: {error}")
            research = cycle_result.get("research") or {}
            aggregation = cycle_result.get("aggregation") or {}
            telegram = cycle_result.get("telegram") or {}
            print(
                "[orchestrator] cycle complete: "
                f"items={len(_batch_to_market_items(cycle_result.get('ingestion') or {}))} "
                f"clusters={aggregation.get('cluster_count', 0)} "
                f"report={research.get('title', 'n/a')} "
                f"telegram={bool(telegram.get('ok', False))}"
            )
            _safe_sleep(interval_seconds)
        except Exception as exc:  # pragma: no cover - defensive logging for long-running worker
            print(f"[orchestrator] recoverable error: {exc}")
            _safe_sleep(backoff_seconds)


def main() -> dict[str, Any] | None:
    if not settings.scheduler_enabled:
        result = run_polling_cycle()
        print(f"[orchestrator] single cycle complete: {result['research']['title']}")
        return result

    run_worker_loop()
    return None


if __name__ == "__main__":
    main()
