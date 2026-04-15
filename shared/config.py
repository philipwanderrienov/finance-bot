from __future__ import annotations

import os
from dataclasses import dataclass


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    postgres_dsn: str = os.getenv(
        "POSTGRES_DSN",
        os.getenv("DATABASE_URL", "postgresql://postgres:qwerty123@127.0.0.1:5432/financebot"),
    )
    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")
    gamma_api_base_url: str = os.getenv("GAMMA_API_BASE_URL", "https://gamma-api.polymarket.com")
    data_api_base_url: str = os.getenv("DATA_API_BASE_URL", "https://data-api.polymarket.com")
    clob_api_base_url: str = os.getenv("CLOB_API_BASE_URL", "https://clob.polymarket.com")
    scheduler_interval_seconds: int = int(os.getenv("SCHEDULER_INTERVAL_SECONDS", "300"))
    scheduler_enabled: bool = _env_bool("SCHEDULER_ENABLED", "true")
    scheduler_backoff_seconds: int = int(os.getenv("SCHEDULER_BACKOFF_SECONDS", "30"))
    scheduler_max_backoff_seconds: int = int(os.getenv("SCHEDULER_MAX_BACKOFF_SECONDS", "300"))
    stocks_market_enabled: bool = _env_bool("STOCKS_MARKET_ENABLED", "true")
    crypto_market_enabled: bool = _env_bool("CRYPTO_MARKET_ENABLED", "true")


settings = Settings()