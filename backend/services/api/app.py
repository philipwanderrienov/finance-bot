from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI

from backend.services.orchestrator.app import run_polling_cycle
from shared.config import settings


def build_dashboard_payload(limit: int = 20) -> dict[str, Any]:
    cycle_result = run_polling_cycle(limit=limit)
    dashboard = cycle_result.get("dashboard") or {}
    if not dashboard:
        dashboard = {
            "sections": {
                "marketsGrid": {"title": "Markets", "items": []},
                "stockRecommendations": {
                    "title": "Recommended Stocks",
                    "summary": "",
                    "subsections": {
                        "buy": {"label": "Buy", "items": []},
                        "sell": {"label": "Sell", "items": []},
                    },
                },
            },
            "sharedMeta": {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "reportId": None,
                "counts": {
                    "markets": 0,
                    "buyRecommendations": 0,
                    "sellRecommendations": 0,
                },
            },
        }
    return {
        "ok": True,
        "source": "backend.services.api.app",
        "frontendBaseUrl": settings.frontend_base_url,
        "cycle": cycle_result,
        "dashboard": dashboard,
    }


app = FastAPI(title="finance-bot-api")


@app.get("/api/dashboard")
def dashboard(limit: int = 20) -> dict[str, Any]:
    return build_dashboard_payload(limit=limit)


def main() -> dict[str, Any]:
    payload = build_dashboard_payload(limit=20)
    print(f"[api] dashboard payload ready: {payload['dashboard']['sharedMeta']['generatedAt']}")
    return payload


if __name__ == "__main__":
    main()
