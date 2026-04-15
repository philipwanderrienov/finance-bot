from __future__ import annotations

from typing import Any

from shared.config import settings
from shared.models import TelegramMessage
from shared.telegram import send_telegram_message


def build_message(report: dict[str, Any]) -> TelegramMessage:
    title = report.get("title", "Finance Bot Update")
    summary = report.get("summary", "No summary available.")
    text = f"<b>{title}</b>\n\n{summary}"
    return TelegramMessage(chat_id=settings.telegram_chat_id, text=text)


def main(report: dict[str, Any] | None = None) -> dict[str, Any]:
    if not settings.telegram_chat_id:
        result = {"ok": False, "skipped": True, "reason": "telegram chat id not configured"}
        print("[telegram_notifier] sent=False")
        return result
    message = build_message(report or {})
    result = send_telegram_message(message)
    print(f"[telegram_notifier] sent={result.get('ok', False)}")
    return result


if __name__ == "__main__":
    main()
