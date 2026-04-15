"""Simple smoke test for finance-bot.

This script imports the shared modules and service entrypoints to confirm that
the project wiring is intact.
"""

from importlib import import_module
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

MODULES = [
    "shared.config",
    "shared.models",
    "shared.db",
    "shared.polymarket",
    "shared.telegram",
    "services.orchestrator.app",
    "services.ingestion.app",
    "services.aggregation.app",
    "services.research.app",
    "services.telegram_notifier.app",
]


def main() -> int:
    for module_name in MODULES:
        import_module(module_name)
        print(f"OK: {module_name}")
    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
