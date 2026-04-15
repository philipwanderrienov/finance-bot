from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shared.models import NewsItem, ResearchReport


def build_research_report(items: list[NewsItem]) -> ResearchReport:
    selected = [item for item in items if item.category in {"stocks", "crypto"}]
    now = datetime.now(timezone.utc)
    title = "Finance Bot Research Report"
    summary = f"Compiled {len(selected)} relevant market items across stocks and crypto."
    return ResearchReport(
        id=now.strftime("%Y%m%d%H%M%S"),
        title=title,
        summary=summary,
        generated_at=now,
        items=selected,
        metadata={"item_count": len(selected)},
    )


def report_to_dict(report: ResearchReport) -> dict[str, Any]:
    return {
        "id": report.id,
        "title": report.title,
        "summary": report.summary,
        "generated_at": report.generated_at.isoformat(),
        "item_count": len(report.items),
        "metadata": report.metadata,
    }


def main() -> dict[str, Any]:
    report = build_research_report([])
    result = report_to_dict(report)
    print(f"[research] {result['title']}: {result['summary']}")
    return result


if __name__ == "__main__":
    main()