from __future__ import annotations

import hashlib
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterable, Optional, TypeVar
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shared.config import settings
from shared.models import MarketItem

try:  # pragma: no cover - optional runtime dependency
    import ssl
except Exception:  # pragma: no cover
    ssl = None

T = TypeVar("T")

DEFAULT_TIMEOUT = 15
DEFAULT_RETRIES = 3
DEFAULT_BACKOFF_SECONDS = 0.75
DEFAULT_CACHE_TTL_SECONDS = 120
DEFAULT_MAX_CACHE_ENTRIES = 64

if ssl is not None:
    SSL_CONTEXT = ssl.create_default_context()
    SSL_CONTEXT.check_hostname = False
    SSL_CONTEXT.verify_mode = ssl.CERT_NONE
else:  # pragma: no cover
    SSL_CONTEXT = None


@dataclass
class CacheEntry:
    value: Any
    created_at: float
    expires_at: float


@dataclass
class PolymarketFetchResult:
    markets: list[MarketItem] = field(default_factory=list)
    source: str = ""
    fetched_at: str = ""
    cache_hit: bool = False
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class PolymarketAccessLayer:
    def __init__(
        self,
        ttl_seconds: int = DEFAULT_CACHE_TTL_SECONDS,
        max_entries: int = DEFAULT_MAX_CACHE_ENTRIES,
        timeout: int = DEFAULT_TIMEOUT,
        retries: int = DEFAULT_RETRIES,
        backoff_seconds: float = DEFAULT_BACKOFF_SECONDS,
    ) -> None:
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_entries = max(1, int(max_entries))
        self.timeout = max(1, int(timeout))
        self.retries = max(1, int(retries))
        self.backoff_seconds = max(0.0, float(backoff_seconds))
        self._cache: dict[str, CacheEntry] = {}

    def _now(self) -> float:
        return time.time()

    def _cache_key(self, prefix: str, **kwargs: Any) -> str:
        payload = json.dumps(kwargs, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return f"{prefix}:{digest}"

    def _get_cached(self, key: str) -> Any | None:
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._now():
            self._cache.pop(key, None)
            return None
        return entry.value

    def _set_cached(self, key: str, value: Any) -> None:
        if len(self._cache) >= self.max_entries:
            self._evict_expired()
        if len(self._cache) >= self.max_entries:
            oldest_key = min(self._cache.items(), key=lambda item: item[1].created_at)[0]
            self._cache.pop(oldest_key, None)
        now = self._now()
        self._cache[key] = CacheEntry(value=value, created_at=now, expires_at=now + self.ttl_seconds)

    def _evict_expired(self) -> None:
        now = self._now()
        expired = [key for key, entry in self._cache.items() if entry.expires_at <= now]
        for key in expired:
            self._cache.pop(key, None)

    def _build_request(self, url: str) -> Request:
        return Request(
            url,
            headers={
                "User-Agent": "finance-bot/1.0",
                "Accept": "application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    def _fetch_json(self, url: str, fallback: Any = None) -> Any:
        request = self._build_request(url)
        last_error: Exception | None = None

        for attempt in range(self.retries):
            try:
                kwargs = {"timeout": self.timeout}
                if SSL_CONTEXT is not None:
                    kwargs["context"] = SSL_CONTEXT
                with urlopen(request, **kwargs) as response:
                    payload = response.read().decode("utf-8")
                return json.loads(payload)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError, Exception) as exc:
                last_error = exc
                if attempt < self.retries - 1:
                    sleep_for = self.backoff_seconds * (2**attempt)
                    print(f"[polymarket] fetch retry {attempt + 1}/{self.retries} url={url} error={exc}")
                    time.sleep(sleep_for)
                    continue
                if fallback is not None:
                    print(f"[polymarket] fetch fallback used url={url} error={exc}")
                    return fallback
                raise last_error

        if fallback is not None:
            return fallback
        if last_error is not None:
            raise last_error
        return fallback

    def _normalize_market_id(self, raw: dict[str, Any], fallback_index: int) -> str:
        return str(
            raw.get("id")
            or raw.get("market_id")
            or raw.get("conditionId")
            or raw.get("condition_id")
            or raw.get("slug")
            or raw.get("questionID")
            or fallback_index
        )

    def _normalize_market_url(self, raw: dict[str, Any]) -> str:
        market_url = str(raw.get("url") or raw.get("market_url") or raw.get("slug") or "")
        if market_url and not market_url.startswith("http"):
            market_url = f"https://polymarket.com/market/{market_url.lstrip('/')}"
        return market_url

    def _extract_raw_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            for key in ("markets", "data", "items", "results"):
                value = payload.get(key)
                if isinstance(value, list):
                    return [item for item in value if isinstance(item, dict)]
        return []

    def _market_score(self, raw: dict[str, Any]) -> float:
        candidates = (
            raw.get("liquidity"),
            raw.get("score"),
            raw.get("volume"),
            raw.get("volume24hr"),
            raw.get("volume_24h"),
            raw.get("price"),
        )
        for value in candidates:
            try:
                if value is None:
                    continue
                return float(value)
            except (TypeError, ValueError):
                continue
        return 0.0

    def _numeric_from_raw(self, raw: dict[str, Any], keys: tuple[str, ...], default: float = 0.0) -> float:
        for key in keys:
            try:
                value = raw.get(key)
                if value is None:
                    continue
                return float(value)
            except (TypeError, ValueError, AttributeError):
                continue
        return default

    def _technical_verification(self, raw: dict[str, Any]) -> dict[str, Any]:
        title_text = " ".join(
            [
                str(raw.get("question") or raw.get("title") or raw.get("name") or raw.get("slug") or ""),
                str(raw.get("description") or raw.get("subtitle") or raw.get("tags") or ""),
            ]
        ).lower()

        tokens = set(title_text.split())
        momentum_positive_terms = {"uptrend", "breakout", "momentum", "rally", "support", "accumulation", "higher", "surge", "spike"}
        momentum_negative_terms = {"downtrend", "breakdown", "resistance", "distribution", "selloff", "lower", "dump", "fade"}

        price = self._numeric_from_raw(raw, ("price", "lastPrice", "last_price", "mid", "midPrice", "mid_price"))
        volume = self._numeric_from_raw(raw, ("volume", "volume24hr", "volume_24h", "volume24h", "liquidity"))
        prev_volume = self._numeric_from_raw(raw, ("previousVolume", "previous_volume", "volume24hPrevious", "volume_24h_previous", "volume7d", "volume_7d"))

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
        volume_proxy = max(volume, raw.get("liquidity") or 0.0, raw.get("market_cap") or 0.0)
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

    def _parse_markets(self, raw_items: Iterable[dict[str, Any]], limit: int, source: str) -> list[MarketItem]:
        items: list[MarketItem] = []
        seen: set[str] = set()
        for index, raw in enumerate(raw_items):
            market_id = self._normalize_market_id(raw, index)
            if market_id in seen:
                continue
            seen.add(market_id)

            title = str(raw.get("question") or raw.get("title") or raw.get("name") or raw.get("slug") or "Untitled market")
            metadata = dict(raw)
            metadata.setdefault("technical_verification", self._technical_verification(raw))
            metadata.setdefault("verification", metadata["technical_verification"])
            metadata.setdefault("momentum_score", metadata["technical_verification"]["momentum_score"])
            metadata.setdefault("volume_change_pct", metadata["technical_verification"]["volume_change_pct"])
            metadata.setdefault("technical_confirmation", metadata["technical_verification"]["technical_confirmation"])
            metadata.setdefault("verification_reason", metadata["technical_verification"]["verification_reason"])

            items.append(
                MarketItem(
                    id=market_id,
                    title=title,
                    category=str(raw.get("category") or "crypto"),
                    source=source,
                    url=self._normalize_market_url(raw),
                    score=self._market_score(raw),
                    metadata=metadata,
                )
            )
            if len(items) >= limit:
                break
        return items

    def fetch_gamma_markets(self, limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
        cache_key = self._cache_key("gamma_markets", limit=limit)
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                print(f"[polymarket] gamma cache_hit limit={limit} items={len(cached)}")
                return list(cached)

        base_url = settings.gamma_api_base_url.rstrip("/")
        url = f"{base_url}/markets?{urlencode({'limit': int(limit)})}"
        payload = self._fetch_json(url, fallback=[])
        raw_items = self._extract_raw_items(payload)
        items = self._parse_markets(raw_items, limit, "polymarket_gamma")
        self._set_cached(cache_key, list(items))
        print(f"[polymarket] gamma fetched limit={limit} raw_items={len(raw_items)} parsed_items={len(items)}")
        return items

    def fetch_data_api_items(self, limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
        cache_key = self._cache_key("data_api_items", limit=limit)
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                print(f"[polymarket] data_api cache_hit limit={limit} items={len(cached)}")
                return list(cached)

        base_url = getattr(settings, "polymarket_data_api_base_url", "") or getattr(settings, "polymarket_api_base_url", "")
        if not base_url:
            print("[polymarket] data api base url missing; returning empty list")
            return []

        url = f"{base_url.rstrip('/')}/markets?{urlencode({'limit': int(limit)})}"
        payload = self._fetch_json(url, fallback=[])
        raw_items = self._extract_raw_items(payload)
        items = self._parse_markets(raw_items, limit, "polymarket_data_api")
        self._set_cached(cache_key, list(items))
        print(f"[polymarket] data_api fetched limit={limit} raw_items={len(raw_items)} parsed_items={len(items)}")
        return items

    def fetch_public_clob_markets(self, limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
        cache_key = self._cache_key("clob_markets", limit=limit)
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                print(f"[polymarket] clob cache_hit limit={limit} items={len(cached)}")
                return list(cached)

        base_url = getattr(settings, "polymarket_clob_base_url", "") or getattr(settings, "polymarket_api_base_url", "")
        if not base_url:
            print("[polymarket] clob base url missing; returning empty list")
            return []

        url = f"{base_url.rstrip('/')}/markets?{urlencode({'limit': int(limit)})}"
        payload = self._fetch_json(url, fallback=[])
        raw_items = self._extract_raw_items(payload)
        items = self._parse_markets(raw_items, limit, "polymarket_clob")
        self._set_cached(cache_key, list(items))
        print(f"[polymarket] clob fetched limit={limit} raw_items={len(raw_items)} parsed_items={len(items)}")
        return items

    def fetch_all_market_sources(self, limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
        cache_key = self._cache_key("all_sources", limit=limit)
        if use_cache:
            cached = self._get_cached(cache_key)
            if cached is not None:
                print(f"[polymarket] all_sources cache_hit limit={limit} items={len(cached)}")
                return list(cached)

        combined: list[MarketItem] = []
        errors: list[str] = []
        for fetcher in (
            self.fetch_gamma_markets,
            self.fetch_data_api_items,
            self.fetch_public_clob_markets,
        ):
            try:
                combined.extend(fetcher(limit=limit, use_cache=use_cache))
            except Exception as exc:
                errors.append(str(exc))
                print(f"[polymarket] source fetch failed fetcher={getattr(fetcher, '__name__', 'unknown')} error={exc}")

        deduped: dict[str, MarketItem] = {}
        for item in combined:
            deduped.setdefault(item.id, item)

        result = list(deduped.values())[:limit]
        self._set_cached(cache_key, list(result))
        print(f"[polymarket] all_sources combined={len(combined)} deduped={len(result)} errors={len(errors)}")
        return result

    def get_cached_result(self, cache_key: str) -> Any | None:
        return self._get_cached(cache_key)

    def cache_snapshot(self) -> dict[str, dict[str, Any]]:
        now = self._now()
        snapshot: dict[str, dict[str, Any]] = {}
        for key, entry in self._cache.items():
            snapshot[key] = {
                "created_at": entry.created_at,
                "expires_at": entry.expires_at,
                "age_seconds": max(0.0, now - entry.created_at),
                "ttl_seconds": max(0.0, entry.expires_at - entry.created_at),
            }
        return snapshot

    def fetch_market_signals(self, limit: int = 20, use_cache: bool = True) -> dict[str, Any]:
        markets = self.fetch_all_market_sources(limit=limit, use_cache=use_cache)
        volume_like = [item.score for item in markets if isinstance(item.score, (int, float))]
        average_score = sum(volume_like) / len(volume_like) if volume_like else 0.0
        top_market = markets[0] if markets else None

        verified_markets = [
            item for item in markets
            if bool((item.metadata or {}).get("technical_confirmation"))
        ]
        confirmation_ratio = (len(verified_markets) / len(markets)) if markets else 0.0
        momentum_values = [
            _safe_float((item.metadata or {}).get("momentum_score"))
            for item in markets
            if (item.metadata or {}).get("momentum_score") is not None
        ]
        volume_change_values = [
            _safe_float((item.metadata or {}).get("volume_change_pct"))
            for item in markets
            if (item.metadata or {}).get("volume_change_pct") is not None
        ]

        return {
            "markets": markets,
            "signals": {
                "count": len(markets),
                "average_score": average_score,
                "top_market_id": top_market.id if top_market else None,
                "top_market_title": top_market.title if top_market else None,
                "cached": use_cache,
                "momentum_average": round(sum(momentum_values) / len(momentum_values), 4) if momentum_values else 0.0,
                "volume_change_average": round(sum(volume_change_values) / len(volume_change_values), 4) if volume_change_values else 0.0,
                "technical_confirmation_ratio": round(confirmation_ratio, 4),
                "verified_markets": len(verified_markets),
            },
            "cache": self.cache_snapshot(),
        }


_default_layer = PolymarketAccessLayer()


def get_polymarket_access_layer() -> PolymarketAccessLayer:
    return _default_layer


def fetch_gamma_markets(limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
    return _default_layer.fetch_gamma_markets(limit=limit, use_cache=use_cache)


def fetch_data_api_items(limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
    return _default_layer.fetch_data_api_items(limit=limit, use_cache=use_cache)


def fetch_public_clob_markets(limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
    return _default_layer.fetch_public_clob_markets(limit=limit, use_cache=use_cache)


def fetch_all_market_sources(limit: int = 20, use_cache: bool = True) -> list[MarketItem]:
    return _default_layer.fetch_all_market_sources(limit=limit, use_cache=use_cache)


def fetch_market_signals(limit: int = 20, use_cache: bool = True) -> dict[str, Any]:
    return _default_layer.fetch_market_signals(limit=limit, use_cache=use_cache)


def get_cached_result(cache_key: str) -> Any | None:
    return _default_layer.get_cached_result(cache_key)


def cache_snapshot() -> dict[str, dict[str, Any]]:
    return _default_layer.cache_snapshot()