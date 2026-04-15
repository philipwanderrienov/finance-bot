from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shared.config import settings
from shared.models import TelegramMessage


def send_telegram_message(message: TelegramMessage, retries: int = 2) -> dict[str, Any]:
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        return {"ok": False, "error": "telegram_not_configured", "message": asdict(message)}

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {
        "chat_id": message.chat_id or settings.telegram_chat_id,
        "text": message.text,
        "parse_mode": message.parse_mode,
        "disable_web_page_preview": message.disable_web_page_preview,
    }
    body = json.dumps(payload).encode("utf-8")
    request = Request(url, data=body, headers={"Content-Type": "application/json", "User-Agent": "finance-bot/1.0"})

    last_error: str | None = None
    for attempt in range(max(1, retries + 1)):
        try:
            with urlopen(request, timeout=20) as response:
                response_body = response.read().decode("utf-8")
            return {"ok": True, "response": json.loads(response_body)}
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = str(exc)
            continue

    return {"ok": False, "error": last_error or "unknown_error", "message": payload}