"""Simple command-line launcher for finance-bot services.

Usage:
    python main.py orchestrator
    python main.py ingestion
    python main.py aggregation
    python main.py research
    python main.py telegram_notifier

This starter launcher keeps the project beginner-friendly and avoids
framework-specific bootstrapping. It prints a helpful message if the
requested service entrypoint is not yet implemented.
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SERVICE_MODULES = {
    "orchestrator": "services.orchestrator.app",
    "ingestion": "services.ingestion.app",
    "aggregation": "services.aggregation.app",
    "research": "services.research.app",
    "telegram_notifier": "services.telegram_notifier.app",
}


def _load_service_module(service_name: str) -> ModuleType | None:
    module_path = SERVICE_MODULES[service_name]
    try:
        return importlib.import_module(module_path)
    except ModuleNotFoundError as exc:
        print(f"Could not import {module_path}: {exc}")
        return None


def _candidate_callables(module: ModuleType) -> Iterable[str]:
    return ("main", "run", "start", "app")


def _run_service(service_name: str) -> int:
    module = _load_service_module(service_name)
    if module is None:
        return 1

    for attr_name in _candidate_callables(module):
        candidate = getattr(module, attr_name, None)
        if callable(candidate):
            result = candidate()
            if isinstance(result, int):
                return result
            return 0

    print(
        f"Service '{service_name}' was imported successfully, but no runnable "
        "callable was found. Expected one of: main, run, start, app."
    )
    return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finance bot service launcher")
    parser.add_argument(
        "service",
        choices=sorted(SERVICE_MODULES.keys()),
        help="Service to start",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return _run_service(args.service)


if __name__ == "__main__":
    raise SystemExit(main())