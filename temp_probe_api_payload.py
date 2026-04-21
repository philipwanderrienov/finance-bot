from backend.services.api.app import get_dashboard_payload

try:
    payload = get_dashboard_payload(limit=1, category="stocks")
    print("OK")
    print(type(payload).__name__)
    print(str(payload)[:2000])
except Exception as exc:
    print("ERROR")
    print(type(exc).__name__)
    print(str(exc))
    raise
