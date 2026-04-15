from __future__ import annotations

from collections import defaultdict
from typing import Any

from shared.models import MarketItem, NewsItem


def cluster_news_items(items: list[NewsItem]) -> dict[str, list[NewsItem]]:
    clusters: dict[str, list[NewsItem]] = defaultdict(list)
    for item in items:
        key = item.category if item.category in {"stocks", "crypto"} else "other"
        clusters[key].append(item)
    return dict(clusters)


def filter_relevant_news(items: list[NewsItem], minimum_score: float = 0.0) -> list[NewsItem]:
    return [item for item in items if item.category in {"stocks", "crypto"} and item.score >= minimum_score]


def summarize_clusters(items: list[NewsItem]) -> dict[str, Any]:
    clusters = cluster_news_items(filter_relevant_news(items))
    return {
        "cluster_count": len(clusters),
        "clusters": {
            category: [
                {
                    "id": item.id,
                    "title": item.title,
                    "summary": item.summary,
                    "source": item.source,
                    "score": item.score,
                }
                for item in cluster_items
            ]
            for category, cluster_items in clusters.items()
        },
    }


def build_news_items_from_markets(items: list[MarketItem]) -> list[NewsItem]:
    news_items: list[NewsItem] = []
    for item in items:
        news_items.append(
            NewsItem(
                id=item.id,
                title=item.title,
                summary=item.metadata.get("description") or item.metadata.get("summary") or item.title,
                category=item.category,
                source=item.source,
                score=item.score,
                metadata=item.metadata,
            )
        )
    return news_items


def main() -> dict[str, Any]:
    report = summarize_clusters([])
    print(f"[aggregation] prepared {report['cluster_count']} clusters")
    return report


if __name__ == "__main__":
    main()
