from __future__ import annotations

from dataclasses import asdict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from json import dumps
from typing import Any
from urllib.parse import parse_qs, urlparse

from backend.services.advisor_engine import generate_advisory_payload


DECISION_SUPPORT_ONLY_DISCLAIMER = (
    "Decision support only: this dashboard surfaces signals and explanations for human review. "
    "It is not an autonomous decision-maker, and users should review the underlying data before acting."
)


def _json_response(payload: dict[str, Any], status: int = 200) -> tuple[int, str]:
    return status, dumps(payload, default=str, ensure_ascii=False)


def get_dashboard_payload(limit: int = 20, category: str = "stocks") -> dict[str, Any]:
    advisory = generate_advisory_payload(category=category, market_limit=limit, news_limit=limit)

    recommendations = advisory.get("recommendations", [])
    buy_items = [item for item in recommendations if str(item.get("recommendation", "")).lower() == "buy"]
    sell_items = [item for item in recommendations if str(item.get("recommendation", "")).lower() == "sell"]
    hold_items = [item for item in recommendations if str(item.get("recommendation", "")).lower() == "hold"]

    portfolio_impact = advisory.get("portfolio_impact", {})
    sentiment = advisory.get("sentiment", {})
    generated_at = advisory.get("generated_at")

    dashboard = {
        "summary": {
            "portfolio": portfolio_impact,
            "sentiment": {
                "metrics": sentiment,
            },
        },
        "sections": {
            "stockRecommendations": {
                "subsections": {
                    "buy": {"items": buy_items},
                    "sell": {"items": sell_items},
                    "hold": {"items": hold_items},
                }
            }
        },
        "sharedMeta": {
            "generatedAt": generated_at,
            "category": category,
            "limit": limit,
            "recommendationCount": len(recommendations),
            "decisionSupportOnly": True,
            "disclaimer": DECISION_SUPPORT_ONLY_DISCLAIMER,
        },
    }

    return {
        "ok": True,
        "decision_support_only": True,
        "disclaimer": DECISION_SUPPORT_ONLY_DISCLAIMER,
        "dashboard": dashboard,
        "advisory": advisory,
    }


class DashboardRequestHandler(BaseHTTPRequestHandler):
    def _set_cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = dumps(payload, default=str, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._set_cors_headers()
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path not in {"/api/dashboard", "/dashboard"}:
            self._send_json({"ok": False, "error": "not_found", "path": parsed.path}, status=404)
            return

        query = parse_qs(parsed.query)
        limit = 20
        category = "stocks"
        try:
            if query.get("limit"):
                limit = max(1, int(query["limit"][0]))
        except Exception:
            limit = 20
        if query.get("category"):
            category = str(query["category"][0]) or "stocks"

        try:
            payload = get_dashboard_payload(limit=limit, category=category)
            self._send_json(payload, status=200)
        except Exception as exc:
            self._send_json({"ok": False, "error": str(exc)}, status=500)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
        print(f"[api] {self.address_string()} - {format % args}")


def create_server(host: str = "0.0.0.0", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), DashboardRequestHandler)


def main() -> int:
    server = create_server()
    print("[api] serving dashboard on http://0.0.0.0:8000/api/dashboard")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("[api] shutting down")
    finally:
        server.server_close()
    return 0


def run() -> int:
    return main()


def start() -> int:
    return main()


app = main