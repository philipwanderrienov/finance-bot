"""Simple command-line launcher for finance-bot services.

Usage:
    python main.py orchestrator
    python main.py ingestion
    python main.py aggregation
    python main.py research
    python main.py api
    python main.py backend

This starter launcher keeps the project beginner-friendly and avoids
framework-specific bootstrapping. It prints a helpful message if the
requested service entrypoint is not yet implemented.
"""

from __future__ import annotations

import argparse
import importlib
import signal
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable


ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


SERVICE_MODULES = {
    "orchestrator": "backend.services.orchestrator.app",
    "ingestion": "backend.services.ingestion.app",
    "aggregation": "backend.services.aggregation.app",
    "research": "backend.services.research.app",
    "api": "backend.services.api.app",
}

BACKEND_SERVICES = ("orchestrator", "api")


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


def _spawn_backend_service(service_name: str) -> subprocess.Popen[str] | None:
    module_path = SERVICE_MODULES[service_name]
    command = [sys.executable, "-m", module_path]
    try:
        process = subprocess.Popen(command)
    except FileNotFoundError as exc:
        print(f"[backend] failed to start {service_name}: {exc}")
        return None

    print(f"[backend] started {service_name} (pid={process.pid})")
    return process


def _stop_backend_services(processes: dict[str, subprocess.Popen[str]]) -> None:
    for service_name, process in processes.items():
        if process.poll() is None:
            print(f"[backend] stopping {service_name} (pid={process.pid})")
            process.terminate()

    for service_name, process in processes.items():
        try:
            return_code = process.wait(timeout=10)
            print(f"[backend] stopped {service_name} (exit={return_code})")
        except subprocess.TimeoutExpired:
            print(f"[backend] force stopping {service_name} (pid={process.pid})")
            process.kill()
            return_code = process.wait(timeout=10)
            print(f"[backend] stopped {service_name} (exit={return_code})")


def _run_backend_stack() -> int:
    processes: dict[str, subprocess.Popen[str]] = {}
    shutdown_requested = False

    def _request_shutdown(signum: int, _frame: object) -> None:
        nonlocal shutdown_requested
        if not shutdown_requested:
            shutdown_requested = True
            print(f"[backend] received signal {signum}, shutting down...")

    signal.signal(signal.SIGINT, _request_shutdown)
    signal.signal(signal.SIGTERM, _request_shutdown)

    try:
        for service_name in BACKEND_SERVICES:
            process = _spawn_backend_service(service_name)
            if process is None:
                shutdown_requested = True
                break
            processes[service_name] = process

        if shutdown_requested and processes:
            _stop_backend_services(processes)
            return 1

        print("[backend] all services started. Press Ctrl+C to stop.")

        while True:
            for service_name, process in processes.items():
                return_code = process.poll()
                if return_code is not None:
                    print(f"[backend] {service_name} exited unexpectedly with code {return_code}")
                    shutdown_requested = True
                    break
            if shutdown_requested:
                break
            signal.pause()
    except KeyboardInterrupt:
        print("[backend] interrupted by user, shutting down...")
    finally:
        if processes:
            _stop_backend_services(processes)

    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Finance bot service launcher")
    parser.add_argument(
        "service",
        choices=sorted(list(SERVICE_MODULES.keys()) + ["backend"]),
        help="Service to start",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.service == "backend":
        return _run_backend_stack()
    return _run_service(args.service)


if __name__ == "__main__":
    raise SystemExit(main())