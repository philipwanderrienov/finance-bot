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

SSL_CONTEXT = ssl.create_default_context()
SSL_CONTEXT.check_hostname = False
SSL_CONTEXT.verify_mode = ssl.CERT_NONE


def _fetch_json(url: str, timeout: int = 15, retries: int = 3, backoff_seconds: float = 1.0) -> Any:
    request = Request(
        url,
        headers={
            "User-Agent": "finance-bot/1.0",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout, context=SSL_CONTEXT) as response:
                payload = response.read().decode("utf-8")
            return json.loads(payload)
        except (ssl.SSLError, TimeoutError, HTTPError, URLError, ValueError, json.JSONDecodeError) as exc:
            last_error = exc
            if attempt < retries - 1:
                time.sleep(backoff_seconds * (2 ** attempt))
                continue
            raise last_error


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_market_url(raw: dict[str, Any]) -> str:
    market_url = str(raw.get("url") or raw.get("market_url") or raw.get("slug") or "")
    if market_url and not market_url.startswith("http"):
        market_url = f"https://polymarket.com/market/{market_url.lstrip('/')}"
    return market_url


def _technical_verification(raw: dict[str, Any]) -> dict[str, Any]:
    title_text = " ".join(
        [
            str(raw.get("question") or raw.get("title") or raw.get("name") or raw.get("slug") or ""),
            str(raw.get("description") or raw.get("subtitle") or raw.get("tags") or ""),
        ]
    ).lower()

    tokens = set(title_text.split())
    momentum_positive_terms = {"uptrend", "breakout", "momentum", "rally", "support", "accumulation", "higher", "surge", "spike"}
    momentum_negative_terms = {"downtrend", "breakdown", "resistance", "distribution", "selloff", "lower", "dump", "fade"}

    price = _safe_float(raw.get("price") or raw.get("lastPrice") or raw.get("last_price") or raw.get("mid") or raw.get("midPrice") or raw.get("mid_price"))
    volume = _safe_float(raw.get("volume") or raw.get("volume24hr") or raw.get("volume_24h") or raw.get("volume24h") or raw.get("liquidity"))
    prev_volume = _safe_float(
        raw.get("previousVolume")
        or raw.get("previous_volume")
        or raw.get("volume24hPrevious")
        or raw.get("volume_24h_previous")
        or raw.get("volume7d")
        or raw.get("volume_7d")
    )

    if prev_volume <= 0:
        prev_volume = max(volume * 0.85, 1.0)

    volume_change = volume - prev_volume
    volume_change_pct = (volume_change / prev_volume) if prev_volume else 0.0

    momentum_hits = len(tokens.intersection(momentum_positive_terms))
    weakening_hits = len(tokens.intersection(momentum_negative_terms))
    price_bias = 0.0
    if price:
        if price >= 0.6:
            price_bias = 0.15
        elif price <= 0.4:
            price_bias = -0.15

    momentum_score = max(-1.0, min(1.0, (momentum_hits - weakening_hits) * 0.3 + price_bias + max(-0.2, min(0.2, volume_change_pct * 0.4))))
    volume_proxy = max(volume, _safe_float(raw.get("liquidity")), _safe_float(raw.get("market_cap")))
    technical_confirmation = momentum_score >= 0.15 and volume_change_pct >= 0.0
    if momentum_score <= -0.15 and volume_change_pct <= 0.0:
        technical_confirmation = False
    verification_strength = abs(momentum_score) + min(abs(volume_change_pct), 1.0) * 0.5
    if technical_confirmation:
        verification_reason = "Momentum and volume are aligned with the market direction."
    elif momentum_score < -0.15 or volume_change_pct < -0.1:
        verification_reason = "Momentum or volume is weakening, so the market is not technically confirmed."
    else:
        verification_reason = "Technical evidence is mixed and does not strongly confirm the move."

    return {
        "momentum_score": round(momentum_score, 4),
        "momentum_direction": "bullish" if momentum_score > 0.15 else "bearish" if momentum_score < -0.15 else "neutral",
        "volume_change": round(volume_change, 4),
        "volume_change_pct": round(volume_change_pct, 4),
        "volume_proxy": round(volume_proxy, 4),
        "technical_confirmation": bool(technical_confirmation),
        "verification_reason": verification_reason,
        "verification_strength": round(min(1.0, verification_strength), 4),
    }


def fetch_gamma_markets(limit: int = 20) -> list[MarketItem]:
    url = f"{settings.gamma_api_base_url.rstrip('/')}/markets?limit={int(limit)}"
    try:
        payload = _fetch_json(url)
    except Exception as exc:
        print(f"[polymarket] gamma fetch failed: {exc}")
        return []

    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict):
        raw_items = payload.get("markets") or payload.get("data") or payload.get("items") or []
    else:
        raw_items = []

    items: list[MarketItem] = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue

        title = str(raw.get("question") or raw.get("title") or raw.get("name") or raw.get("slug") or "Untitled market")
        market_id = str(
            raw.get("id")
            or raw.get("market_id")
            or raw.get("conditionId")
            or raw.get("condition_id")
            or raw.get("slug")
            or len(items)
        )
        market_url = _normalize_market_url(raw)

        liquidity = raw.get("liquidity") or raw.get("score") or raw.get("volume") or 0.0
        try:
            score = float(liquidity)
        except (TypeError, ValueError):
            score = 0.0

        metadata = dict(raw)
        technical = _technical_verification(raw)
        metadata.setdefault("technical_verification", technical)
        metadata.setdefault("verification", technical)
        metadata.setdefault("momentum_score", technical["momentum_score"])
        metadata.setdefault("volume_change_pct", technical["volume_change_pct"])
        metadata.setdefault("technical_confirmation", technical["technical_confirmation"])
        metadata.setdefault("verification_reason", technical["verification_reason"])

        items.append(
            MarketItem(
                id=market_id,
                title=title,
                category="crypto",
                source="polymarket_gamma",
                url=market_url,
                score=score,
                metadata=metadata,
            )
        )
        if len(items) >= limit:
            break
    print(f"[polymarket] gamma raw_items={len(raw_items)} parsed_items={len(items)}")
    return items[:limit]


def fetch_data_api_items(limit: int = 20) -> list[MarketItem]:
    return []


def fetch_public_clob_markets(limit: int = 20) -> list[MarketItem]:
    return []


def fetch_all_market_sources(limit: int = 20) -> list[MarketItem]:
    combined = fetch_gamma_markets(limit)
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