from __future__ import annotations

from typing import Any

from services.api.app import build_dashboard_payload


def get_dashboard(limit: int = 20) -> dict[str, Any]:
    return build_dashboard_payload(limit=limit)
