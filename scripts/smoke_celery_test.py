"""Quick smoke test for Celery integration.

This script attempts to:
- import the Celery app from `config.celery`
- run the `debug_task` defined in `config.celery` using `.apply()` (synchronous)
- verify that `web.tasks.run_pipeline_task` is importable (but does not execute it)

Run locally: `python3 scripts/smoke_celery_test.py`

The script is intentionally conservative: it will not enqueue heavy pipeline work or require a running Redis broker.
"""
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def main() -> int:
    print("Celery smoke test starting...")

    # 1. Import celery app and debug_task
    try:
        import config.celery as celery_mod

        print("Imported config.celery")
    except Exception as e:
        print("Failed to import config.celery:", e)
        traceback.print_exc()
        return 2

    # Check for debug_task
    debug_task = getattr(celery_mod, "debug_task", None)
    if debug_task is None:
        print("No debug_task found in config.celery")
        return 3

    # Execute debug_task synchronously with .apply() so this doesn't require a broker
    try:
        print("Running debug_task.apply() (synchronous)")
        res = debug_task.apply()
        print("debug_task result:", res.get(timeout=5) if hasattr(res, 'get') else res)
    except Exception as e:
        print("debug_task.apply() failed:", e)
        traceback.print_exc()
        return 4

    # 2. Ensure web.tasks.run_pipeline_task is importable but do NOT execute it
    try:
        import web.tasks as tasks_mod
        print("Imported web.tasks")
        if hasattr(tasks_mod, "run_pipeline_task"):
            print("Found run_pipeline_task (not executing)")
        else:
            print("run_pipeline_task not found in web.tasks")
            return 5
    except Exception as e:
        print("Failed to import web.tasks:", e)
        traceback.print_exc()
        return 6

    print("Smoke test passed: basic Celery import and debug task execution succeeded.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
