from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MarketItem:
    id: str
    title: str
    category: str = "stocks"
    source: str = "polymarket"
    url: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NewsItem:
    id: str
    title: str
    summary: str = ""
    category: str = "stocks"
    source: str = ""
    published_at: datetime | None = None
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ResearchReport:
    id: str
    title: str
    summary: str
    generated_at: datetime
    items: list[NewsItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TelegramMessage:
    chat_id: str
    text: str
    parse_mode: str = "HTML"
    disable_web_page_preview: bool = True