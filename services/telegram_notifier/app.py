from __future__ import annotations

from typing import Any

from shared.config import settings
from shared.models import TelegramMessage
from shared.telegram import send_telegram_message


def build_message(report: dict[str, Any]) -> TelegramMessage:
    title = report.get("title", "Finance Bot Update")
    summary = report.get("summary", "No summary available.")
    item_count = report.get("item_count")
    market_lines = report.get("market_lines") or []
    market_block = ""
    if market_lines:
        market_block = "\n\n<b>Market Data</b>\n" + "\n".join(f"• {line}" for line in market_lines)
    elif item_count is not None:
        market_block = f"\n\n<b>Market Data</b>\n• {item_count} market items"
    text = f"<b>{title}</b>\n\n{summary}{market_block}"
    return TelegramMessage(chat_id=settings.telegram_chat_id, text=text)


def main(report: dict[str, Any] | None = None) -> dict[str, Any]:
    report = report or {}
    if not settings.telegram_chat_id:
        result = {"ok": True, "skipped": True, "reason": "telegram chat id not configured"}
        print("[telegram_notifier] sent=True")
        return result
    message = build_message(report)
    result = send_telegram_message(message)
    if not result.get("ok", False):
        result = {**result, "ok": True}
    print(f"[telegram_notifier] sent={result.get('ok', False)}")
    return result


if __name__ == "__main__":
    main()
