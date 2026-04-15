# Smoke test note

Run the smoke test from the repository root:

```bash
python scripts/smoke_test.py
```

The smoke test checks that the shared package and service entrypoints import cleanly.

It expects the current shared config API to use `Settings` and the module-level `settings` instance, not the older `AppConfig` names.