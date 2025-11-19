"""Enqueue a small marker-writing Celery task.

Usage: run this inside the `web` container (it uses the project package layout).
  docker-compose exec web python3 scripts/enqueue_marker.py

The task writes `/tmp/celery_test_marker.txt` inside the container, which is
mounted to the host `/tmp` via `docker-compose.yml` so you can verify it.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

def main():
    try:
        from web.tasks import write_marker_task
    except Exception as e:
        print("Failed to import write_marker_task:", e)
        return 2

    # Enqueue the task
    result = write_marker_task.delay("/tmp/celery_test_marker.txt", "celery smoke ok")
    print("Enqueued write_marker_task, task id:", result.id)
    print("Use 'docker-compose logs worker' or check /tmp/celery_test_marker.txt on host to verify.")
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
