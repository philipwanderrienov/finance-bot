from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class SentimentLabel(str, Enum):
    VERY_NEGATIVE = "very_negative"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    POSITIVE = "positive"
    VERY_POSITIVE = "very_positive"


class AdvisoryAction(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    WATCH = "watch"
    REDUCE = "reduce"


class RecommendationDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class AnalysisHorizon(str, Enum):
    INTRADAY = "intraday"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class BacktestOutcome(str, Enum):
    WIN = "win"
    LOSS = "loss"
    BREAKEVEN = "breakeven"


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


@dataclass
class SentimentSignal:
    item_id: str
    source: str
    label: SentimentLabel = SentimentLabel.NEUTRAL
    score: float = 0.0
    confidence: float = 0.0
    magnitude: float = 0.0
    rationale: str = ""
    keywords: list[str] = field(default_factory=list)
    created_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NewsSummary:
    id: str
    title: str
    summary: str
    bullet_points: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    sentiment: SentimentSignal | None = None
    generated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AdvisoryDecision:
    asset_id: str
    symbol: str = ""
    action: AdvisoryAction = AdvisoryAction.HOLD
    direction: RecommendationDirection = RecommendationDirection.NEUTRAL
    horizon: AnalysisHorizon = AnalysisHorizon.SHORT_TERM
    confidence: float = 0.0
    conviction: float = 0.0
    target_price: float | None = None
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    expected_return: float | None = None
    risk_reward_ratio: float | None = None
    reasons: list[str] = field(default_factory=list)
    supporting_signals: list[SentimentSignal] = field(default_factory=list)
    related_news: list[NewsItem] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioPosition:
    symbol: str
    quantity: float = 0.0
    average_cost: float = 0.0
    current_price: float | None = None
    market_value: float | None = None
    unrealized_pnl: float | None = None
    unrealized_pnl_pct: float | None = None
    weight: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioSummary:
    total_value: float = 0.0
    cash_balance: float = 0.0
    invested_value: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    positions: list[PortfolioPosition] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioImpactItem:
    symbol: str
    action: AdvisoryAction = AdvisoryAction.HOLD
    projected_position_value: float | None = None
    projected_weight: float | None = None
    projected_pnl: float | None = None
    projected_pnl_pct: float | None = None
    expected_impact: float = 0.0
    risk_delta: float = 0.0
    rationale: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioImpactAnalysis:
    portfolio: PortfolioSummary
    decisions: list[AdvisoryDecision] = field(default_factory=list)
    items: list[PortfolioImpactItem] = field(default_factory=list)
    portfolio_risk_score: float = 0.0
    projected_return: float | None = None
    projected_drawdown: float | None = None
    summary: str = ""
    generated_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestTrade:
    symbol: str
    action: AdvisoryAction
    entry_at: datetime | None = None
    exit_at: datetime | None = None
    entry_price: float | None = None
    exit_price: float | None = None
    quantity: float = 0.0
    pnl: float = 0.0
    pnl_pct: float = 0.0
    outcome: BacktestOutcome = BacktestOutcome.BREAKEVEN
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BacktestResult:
    strategy_name: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    horizon: AnalysisHorizon = AnalysisHorizon.SHORT_TERM
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0
    total_return_pct: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    sharpe_ratio: float | None = None
    trades: list[BacktestTrade] = field(default_factory=list)
    decisions: list[AdvisoryDecision] = field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)