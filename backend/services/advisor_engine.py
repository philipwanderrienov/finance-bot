from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from shared import db
from shared.models import MarketItem, NewsItem, ResearchReport, SentimentLabel
from shared.polymarket import fetch_all_market_sources, market_item_to_dict


POSITIVE_KEYWORDS = {
    "beat",
    "beats",
    "bullish",
    "growth",
    "gain",
    "gains",
    "improve",
    "improves",
    "improving",
    "positive",
    "profit",
    "profits",
    "raise",
    "raises",
    "strong",
    "strength",
    "upside",
    "win",
    "wins",
    "record",
    "outperform",
    "surge",
    "surges",
    "accelerate",
    "accelerates",
    "expansion",
    "expands",
    "tailwind",
    "tailwinds",
    "resilient",
}

NEGATIVE_KEYWORDS = {
    "bearish",
    "concern",
    "concerns",
    "decline",
    "declines",
    "downside",
    "fall",
    "falls",
    "negative",
    "loss",
    "losses",
    "miss",
    "misses",
    "risk",
    "risks",
    "weak",
    "weakness",
    "warning",
    "warnings",
    "lawsuit",
    "recession",
    "slump",
    "slumps",
    "cut",
    "cuts",
    "downgrade",
    "downgrades",
    "fraud",
    "investigation",
    "investigations",
}

TECHNICAL_POSITIVE = {"uptrend", "breakout", "support", "momentum", "accumulation", "higher", "rally"}
TECHNICAL_NEGATIVE = {"downtrend", "breakdown", "resistance", "distribution", "selloff", "lower", "dump"}

BULLISH_CUES = {
    "approval",
    "awarded",
    "award",
    "boost",
    "buyback",
    "contract",
    "expansion",
    "guidance raise",
    "record revenue",
    "upgrade",
    "upgraded",
    "growth",
    "profit beat",
}

BEARISH_CUES = {
    "cut guidance",
    "downgraded",
    "investigation",
    "probe",
    "recall",
    "resign",
    "resigns",
    "lawsuit",
    "shortfall",
    "warning",
    "fraud",
    "bankruptcy",
    "suspension",
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").strip())


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z']+", text.lower())


def _clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _clean_keywords(keywords: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for keyword in keywords:
        token = keyword.strip().lower()
        if token and token not in cleaned:
            cleaned.append(token)
    return cleaned[:8]


def _label_from_score(score: float) -> SentimentLabel:
    if score >= 0.65:
        return SentimentLabel.VERY_POSITIVE
    if score >= 0.15:
        return SentimentLabel.POSITIVE
    if score <= -0.65:
        return SentimentLabel.VERY_NEGATIVE
    if score <= -0.15:
        return SentimentLabel.NEGATIVE
    return SentimentLabel.NEUTRAL


def _direction_from_score(score: float) -> str:
    if score >= 0.15:
        return "bullish"
    if score <= -0.15:
        return "bearish"
    return "neutral"


def summarize_news_items(items: Iterable[NewsItem], max_sentences: int = 3) -> str:
    collected = list(items)
    if not collected:
        return "No recent news items were available for summarization."

    sentences: list[str] = []
    for item in collected:
        text = _normalize_text(item.summary or item.title)
        if not text:
            continue
        split_sentences = re.split(r"(?<=[.!?])\s+", text)
        sentences.extend([sentence.strip() for sentence in split_sentences if sentence.strip()])
        if len(sentences) >= max_sentences:
            break

    if not sentences:
        return "No textual content was available to summarize."

    summary = " ".join(sentences[:max_sentences]).strip()
    if len(summary) > 600:
        summary = summary[:597].rstrip() + "..."
    return summary


class SentimentAnalyzer:
    def analyze(self, item: NewsItem) -> dict[str, Any]:
        raise NotImplementedError


class RuleBasedSentimentAnalyzer(SentimentAnalyzer):
    def __init__(
        self,
        positive_keywords: set[str] | None = None,
        negative_keywords: set[str] | None = None,
    ) -> None:
        self.positive_keywords = positive_keywords or POSITIVE_KEYWORDS
        self.negative_keywords = negative_keywords or NEGATIVE_KEYWORDS

    def _extract_keywords(self, text: str) -> list[str]:
        tokens = _tokenize(text)
        matched: list[str] = []
        for token in tokens:
            if token in self.positive_keywords or token in self.negative_keywords:
                matched.append(token)
        for cue in BULLISH_CUES.union(BEARISH_CUES):
            if cue in text:
                matched.extend(cue.split())
        return _clean_keywords(matched)

    def analyze(self, item: NewsItem) -> dict[str, Any]:
        text = " ".join(
            [
                item.title,
                item.summary,
                str(item.metadata.get("headline", "")) if item.metadata else "",
                str(item.metadata.get("summary", "")) if item.metadata else "",
                str(item.metadata.get("description", "")) if item.metadata else "",
            ]
        ).strip().lower()

        tokens = _tokenize(text)
        if not tokens:
            return {
                "score": 0.0,
                "label": SentimentLabel.NEUTRAL,
                "direction": "neutral",
                "confidence": 0.2,
                "magnitude": 0.0,
                "rationale": "No textual signal was available.",
                "keywords": [],
                "method": "rule_based",
            }

        positive_hits = [token for token in tokens if token in self.positive_keywords]
        negative_hits = [token for token in tokens if token in self.negative_keywords]
        technical_positive_hits = [token for token in tokens if token in TECHNICAL_POSITIVE]
        technical_negative_hits = [token for token in tokens if token in TECHNICAL_NEGATIVE]

        cue_keywords: list[str] = []
        for cue in BULLISH_CUES:
            if cue in text:
                cue_keywords.extend(cue.split())
        for cue in BEARISH_CUES:
            if cue in text:
                cue_keywords.extend(cue.split())

        signal_balance = (
            len(positive_hits)
            + len(technical_positive_hits) * 0.85
            + len([cue for cue in BULLISH_CUES if cue in text]) * 1.25
            - len(negative_hits)
            - len(technical_negative_hits) * 0.85
            - len([cue for cue in BEARISH_CUES if cue in text]) * 1.25
        )

        total_signal_terms = (
            len(positive_hits)
            + len(negative_hits)
            + len(technical_positive_hits)
            + len(technical_negative_hits)
            + len(cue_keywords)
        )

        diversity = max(len(set(positive_hits + negative_hits + technical_positive_hits + technical_negative_hits + cue_keywords)), 1)
        raw_score = signal_balance / math.sqrt(max(len(tokens), 1))
        raw_score += min(0.25, diversity * 0.03)

        if item.score:
            raw_score += _safe_float(item.score) * 0.04

        score = _clamp(raw_score)
        label = _label_from_score(score)
        direction = _direction_from_score(score)
        magnitude = round(abs(score), 4)

        if direction == "bullish":
            rationale = "The article contains more constructive than negative language."
        elif direction == "bearish":
            rationale = "The article contains more cautionary than constructive language."
        else:
            rationale = "The article presents a mixed or balanced signal."

        if positive_hits and negative_hits:
            rationale += " Both positive and negative cues were present, indicating a nuanced tone."
        elif positive_hits:
            rationale += " Positive language and supportive cues dominate the text."
        elif negative_hits:
            rationale += " Negative language and risk cues dominate the text."

        keywords = self._extract_keywords(text)
        if not keywords and item.title:
            keywords = _clean_keywords(_tokenize(item.title)[:3])

        confidence = _clamp(0.35 + min(0.45, total_signal_terms * 0.06) + magnitude * 0.2, 0.0, 0.99)

        return {
            "score": round(score, 4),
            "label": label,
            "direction": direction,
            "confidence": round(confidence, 4),
            "magnitude": round(magnitude, 4),
            "rationale": rationale,
            "keywords": keywords,
            "method": "rule_based",
        }


class PluggableSentimentEngine:
    def __init__(self, analyzer: SentimentAnalyzer | None = None) -> None:
        self.analyzer = analyzer or RuleBasedSentimentAnalyzer()

    def analyze_item(self, item: NewsItem) -> dict[str, Any]:
        try:
            result = self.analyzer.analyze(item)
        except Exception as exc:
            print(f"[advisor_engine] sentiment analysis failed for {item.id}: {exc}")
            result = RuleBasedSentimentAnalyzer().analyze(item)
        result.setdefault("score", 0.0)
        result.setdefault("label", SentimentLabel.NEUTRAL)
        result.setdefault("direction", _direction_from_score(_safe_float(result.get("score"))))
        result.setdefault("confidence", 0.0)
        result.setdefault("magnitude", abs(_safe_float(result.get("score"))))
        result.setdefault("rationale", "")
        result.setdefault("keywords", [])
        result.setdefault("method", "rule_based")
        return result


def score_news_item(item: NewsItem, engine: PluggableSentimentEngine | None = None) -> float:
    analyzer = engine or PluggableSentimentEngine()
    analysis = analyzer.analyze_item(item)
    return _safe_float(analysis.get("score"))


def derive_sentiment_score(items: Iterable[NewsItem], engine: PluggableSentimentEngine | None = None) -> dict[str, Any]:
    collected = list(items)
    analyzer = engine or PluggableSentimentEngine()
    if not collected:
        return {
            "score": 0.0,
            "label": SentimentLabel.NEUTRAL.value,
            "direction": "neutral",
            "confidence": 0.0,
            "magnitude": 0.0,
            "rationale": "No recent news items were available.",
            "keywords": [],
            "items_scored": 0,
            "bullish_items": 0,
            "bearish_items": 0,
            "item_scores": [],
            "method": "rule_based",
        }

    analyses = [analyzer.analyze_item(item) for item in collected]
    scores = [_safe_float(entry.get("score")) for entry in analyses]
    bullish_items = sum(1 for entry in analyses if _safe_float(entry.get("score")) > 0.15)
    bearish_items = sum(1 for entry in analyses if _safe_float(entry.get("score")) < -0.15)
    average = sum(scores) / len(scores)
    magnitude = abs(average)

    if average > 0.15:
        label = SentimentLabel.POSITIVE if average < 0.65 else SentimentLabel.VERY_POSITIVE
    elif average < -0.15:
        label = SentimentLabel.NEGATIVE if average > -0.65 else SentimentLabel.VERY_NEGATIVE
    else:
        label = SentimentLabel.NEUTRAL

    direction = _direction_from_score(average)
    if direction == "bullish":
        rationale = "Recent news sentiment leans constructive overall."
    elif direction == "bearish":
        rationale = "Recent news sentiment leans cautionary overall."
    else:
        rationale = "Recent news sentiment is broadly balanced."

    confidence = _clamp(0.35 + min(0.45, sum(_safe_float(entry.get("confidence")) for entry in analyses) / len(analyses) * 0.5) + magnitude * 0.15, 0.0, 0.99)
    keywords = _clean_keywords(
        keyword
        for entry in analyses
        for keyword in entry.get("keywords", [])
    )

    return {
        "score": round(average, 4),
        "label": label.value,
        "direction": direction,
        "confidence": round(confidence, 4),
        "magnitude": round(magnitude, 4),
        "rationale": rationale,
        "keywords": keywords,
        "items_scored": len(collected),
        "bullish_items": bullish_items,
        "bearish_items": bearish_items,
        "item_scores": [
            {
                "id": item.id,
                "title": item.title,
                "score": round(_safe_float(analysis.get("score")), 4),
                "label": getattr(analysis.get("label"), "value", analysis.get("label")),
                "direction": analysis.get("direction", "neutral"),
                "confidence": round(_safe_float(analysis.get("confidence")), 4),
                "magnitude": round(_safe_float(analysis.get("magnitude")), 4),
                "rationale": analysis.get("rationale", ""),
                "keywords": analysis.get("keywords", []),
                "source": item.source,
            }
            for item, analysis in zip(collected, analyses)
        ],
        "method": "rule_based",
    }


def score_market_technical(item: MarketItem) -> dict[str, Any]:
    technical = (item.metadata or {}).get("technical_verification") if item.metadata else None
    if isinstance(technical, dict):
        score = _safe_float(technical.get("momentum_score"))
        return {
            "score": round(score, 4),
            "positive_signals": 1 if score > 0.15 else 0,
            "negative_signals": 1 if score < -0.15 else 0,
            "base_score": round(_safe_float(item.score), 4),
            "momentum_score": round(score, 4),
            "volume_change": round(_safe_float(technical.get("volume_change")), 4),
            "volume_change_pct": round(_safe_float(technical.get("volume_change_pct")), 4),
            "volume_proxy": round(_safe_float(technical.get("volume_proxy")), 4),
            "technical_confirmation": bool(technical.get("technical_confirmation")),
            "verification_reason": str(technical.get("verification_reason", "")),
            "verification_strength": round(_safe_float(technical.get("verification_strength")), 4),
        }

    text = " ".join(
        [
            item.title,
            str(item.metadata.get("description", "")) if item.metadata else "",
            str(item.metadata.get("tags", "")) if item.metadata else "",
        ]
    ).lower()
    tokens = set(_tokenize(text))
    positive = len(tokens.intersection(TECHNICAL_POSITIVE))
    negative = len(tokens.intersection(TECHNICAL_NEGATIVE))

    base_score = _safe_float(item.score)
    signal_score = _clamp((positive - negative) * 0.25 + (base_score / 1000.0 if base_score else 0.0))
    return {
        "score": round(signal_score, 4),
        "positive_signals": positive,
        "negative_signals": negative,
        "base_score": round(base_score, 4),
        "momentum_score": round(signal_score, 4),
        "volume_change": 0.0,
        "volume_change_pct": 0.0,
        "volume_proxy": round(base_score, 4),
        "technical_confirmation": signal_score >= 0.15 and positive >= negative,
        "verification_reason": "Fallback technical heuristic derived from market metadata.",
        "verification_strength": round(abs(signal_score), 4),
    }


def _recommendation_from_score(score: float) -> str:
    if score >= 0.35:
        return "buy"
    if score <= -0.35:
        return "sell"
    return "hold"


def _confidence_from_score(score: float, support: float = 0.0) -> float:
    magnitude = abs(score) + abs(support)
    return round(_clamp(0.35 + magnitude * 0.45, 0.0, 0.99), 4)


def build_advisory_recommendation(
    market: MarketItem,
    sentiment_score: float,
    technical_score: float,
    news_summary: str,
    supporting_news: list[NewsItem] | None = None,
    sentiment_analysis: dict[str, Any] | None = None,
    technical_details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    support_items = supporting_news or []
    technical_details = technical_details or {}
    technical_confirmation = bool(technical_details.get("technical_confirmation")) if technical_details else False
    momentum_score = _safe_float(technical_details.get("momentum_score", technical_score))
    volume_change_pct = _safe_float(technical_details.get("volume_change_pct"))
    verification_strength = _safe_float(technical_details.get("verification_strength"))
    combined = _clamp((technical_score * 0.6) + (sentiment_score * 0.4))
    if technical_confirmation:
        combined = _clamp(combined + min(0.12, verification_strength * 0.1))
    recommendation = _recommendation_from_score(combined)
    reasons: list[str] = []

    if sentiment_score > 0.15:
        reasons.append("News flow is constructive.")
    elif sentiment_score < -0.15:
        reasons.append("News flow is deteriorating.")
    else:
        reasons.append("News flow is mixed or neutral.")

    if technical_score > 0.15:
        reasons.append("Technical cues suggest positive momentum.")
    elif technical_score < -0.15:
        reasons.append("Technical cues suggest weakening momentum.")
    else:
        reasons.append("Technical cues are balanced.")

    if technical_confirmation:
        reasons.append("Momentum and volume both confirm the market setup.")
    elif verification_strength > 0:
        reasons.append("Technical verification is partial and should be treated cautiously.")
    else:
        reasons.append("Technical verification is weak.")

    if volume_change_pct > 0:
        reasons.append("Volume is expanding versus the comparison baseline.")
    elif volume_change_pct < 0:
        reasons.append("Volume is contracting versus the comparison baseline.")

    if support_items:
        reasons.append(f"Based on {len(support_items)} recent news item(s).")

    if sentiment_analysis:
        rationale = str(sentiment_analysis.get("rationale", "")).strip()
        if rationale:
            reasons.append(rationale)

    return {
        "market_id": market.id,
        "market_title": market.title,
        "recommendation": recommendation,
        "confidence": _confidence_from_score(combined, support=technical_score),
        "combined_score": round(combined, 4),
        "sentiment_score": round(sentiment_score, 4),
        "technical_score": round(technical_score, 4),
        "reasons": reasons,
        "news_summary": news_summary,
        "technical_verification": {
            "momentum_score": round(momentum_score, 4),
            "volume_change_pct": round(volume_change_pct, 4),
            "technical_confirmation": technical_confirmation,
            "verification_strength": round(verification_strength, 4),
            "verification_reason": str(technical_details.get("verification_reason", "")),
        },
        "sentiment": {
            "score": round(_safe_float((sentiment_analysis or {}).get("score"), sentiment_score), 4),
            "label": getattr((sentiment_analysis or {}).get("label"), "value", (sentiment_analysis or {}).get("label", SentimentLabel.NEUTRAL.value)),
            "direction": (sentiment_analysis or {}).get("direction", _direction_from_score(sentiment_score)),
            "confidence": round(_safe_float((sentiment_analysis or {}).get("confidence"), _confidence_from_score(sentiment_score)), 4),
            "magnitude": round(_safe_float((sentiment_analysis or {}).get("magnitude"), abs(sentiment_score)), 4),
            "rationale": (sentiment_analysis or {}).get("rationale", ""),
            "keywords": (sentiment_analysis or {}).get("keywords", []),
            "method": (sentiment_analysis or {}).get("method", "rule_based"),
        },
        "market": market_item_to_dict(market),
    }


def analyze_portfolio_impact(
    recommendations: list[dict[str, Any]],
    portfolio: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    portfolio = portfolio or []
    impact_by_action = {"buy": 0, "hold": 0, "sell": 0}
    exposure_delta = 0.0

    for rec in recommendations:
        action = str(rec.get("recommendation", "hold")).lower()
        impact_by_action[action] = impact_by_action.get(action, 0) + 1
        combined_score = _safe_float(rec.get("combined_score"))
        exposure_delta += combined_score

    portfolio_value = sum(_safe_float(item.get("market_value") or item.get("value")) for item in portfolio)
    risk_budget = portfolio_value * 0.1 if portfolio_value else len(recommendations)

    return {
        "portfolio_items": len(portfolio),
        "portfolio_value": round(portfolio_value, 2),
        "recommendation_counts": impact_by_action,
        "estimated_exposure_delta": round(exposure_delta, 4),
        "risk_budget": round(risk_budget, 2),
        "impact_label": "elevated" if abs(exposure_delta) > 1.5 else "moderate" if abs(exposure_delta) > 0.5 else "low",
    }


def backtest_recommendations(
    historical_items: list[dict[str, Any]] | None = None,
    starting_capital: float = 10000.0,
) -> dict[str, Any]:
    historical_items = historical_items or []
    capital = float(starting_capital)
    trades: list[dict[str, Any]] = []
    pnl = 0.0

    for index, item in enumerate(historical_items):
        score = _safe_float(item.get("combined_score") or item.get("score"))
        if score == 0:
            continue
        direction = 1 if score > 0 else -1
        trade_return = score * 0.02 * direction
        trade_pnl = capital * trade_return * 0.1
        pnl += trade_pnl
        capital += trade_pnl
        trades.append(
            {
                "index": index,
                "action": "buy" if direction > 0 else "sell",
                "score": round(score, 4),
                "trade_pnl": round(trade_pnl, 2),
            }
        )

    return {
        "starting_capital": round(starting_capital, 2),
        "ending_capital": round(capital, 2),
        "pnl": round(pnl, 2),
        "return_pct": round((pnl / starting_capital * 100.0) if starting_capital else 0.0, 2),
        "trades": trades,
        "sample_size": len(historical_items),
        "status": "stubbed",
    }


@dataclass
class AdvisoryRun:
    generated_at: datetime
    summary: str
    sentiment: dict[str, Any]
    recommendations: list[dict[str, Any]] = field(default_factory=list)
    portfolio_impact: dict[str, Any] = field(default_factory=dict)
    backtest: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


def load_recent_news(category: str = "stocks", limit: int = 25, config: Any | None = None) -> list[NewsItem]:
    try:
        rows = db.list_recent_news(category=category, limit=limit, config=config)
    except Exception as exc:
        print(f"[advisor_engine] load_recent_news failed: {exc}")
        return []

    news_items: list[NewsItem] = []
    for row in rows:
        try:
            news_items.append(
                NewsItem(
                    id=str(row.get("id", "")),
                    title=str(row.get("title", "")),
                    summary=str(row.get("summary", "")),
                    category=str(row.get("category", category)),
                    source=str(row.get("source", "")),
                    published_at=row.get("published_at"),
                    score=_safe_float(row.get("score")),
                    metadata=row.get("metadata") or {},
                )
            )
        except Exception as exc:
            print(f"[advisor_engine] skipping news row due to parse error: {exc}")
    return news_items


def ingest_news_items(items: Iterable[NewsItem], config: Any | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for item in items:
        try:
            row = db.insert_news_item(item, config=config)
            results.append(row)
        except Exception as exc:
            print(f"[advisor_engine] failed to ingest news item {item.id}: {exc}")
    return results


def generate_advisory_run(
    category: str = "stocks",
    news_limit: int = 25,
    market_limit: int = 20,
    config: Any | None = None,
) -> AdvisoryRun:
    print(f"[advisor_engine] generating advisory run category={category} news_limit={news_limit} market_limit={market_limit}")
    news_items = load_recent_news(category=category, limit=news_limit, config=config)
    summary = summarize_news_items(news_items)
    sentiment = derive_sentiment_score(news_items)

    try:
        markets = fetch_all_market_sources(limit=market_limit)
    except Exception as exc:
        print(f"[advisor_engine] market fetch failed: {exc}")
        markets = []

    recommendations: list[dict[str, Any]] = []
    for market in markets:
        technical = score_market_technical(market)
        recommendation = build_advisory_recommendation(
            market=market,
            sentiment_score=_safe_float(sentiment.get("score")),
            technical_score=_safe_float(technical.get("score")),
            news_summary=summary,
            supporting_news=news_items[:5],
            sentiment_analysis=sentiment,
            technical_details=technical,
        )
        recommendation["technical_details"] = technical
        recommendations.append(recommendation)

    portfolio_impact = analyze_portfolio_impact(recommendations)
    backtest = backtest_recommendations(recommendations)

    return AdvisoryRun(
        generated_at=_utcnow(),
        summary=summary,
        sentiment=sentiment,
        recommendations=recommendations,
        portfolio_impact=portfolio_impact,
        backtest=backtest,
        metadata={
            "category": category,
            "news_count": len(news_items),
            "market_count": len(markets),
        },
    )


def generate_advisory_payload(
    category: str = "stocks",
    news_limit: int = 25,
    market_limit: int = 20,
    config: Any | None = None,
) -> dict[str, Any]:
    run = generate_advisory_run(category=category, news_limit=news_limit, market_limit=market_limit, config=config)
    return {
        "generated_at": run.generated_at.isoformat(),
        "summary": run.summary,
        "sentiment": run.sentiment,
        "recommendations": run.recommendations,
        "portfolio_impact": run.portfolio_impact,
        "backtest": run.backtest,
        "metadata": run.metadata,
    }


def create_research_report_from_advisory(category: str = "stocks", config: Any | None = None) -> ResearchReport:
    run = generate_advisory_run(category=category, config=config)
    report = ResearchReport(
        id=f"advisor-{run.generated_at.timestamp():.0f}",
        title=f"Advisor report for {category}",
        summary=run.summary,
        generated_at=run.generated_at,
        items=load_recent_news(category=category, limit=10, config=config),
        metadata={
            "sentiment": run.sentiment,
            "recommendations": run.recommendations,
            "portfolio_impact": run.portfolio_impact,
            "backtest": run.backtest,
            "generated_by": "advisor_engine",
        },
    )
    try:
        db.insert_research_report(report, category=category, config=config)
    except Exception as exc:
        print(f"[advisor_engine] failed to persist research report: {exc}")
    return report