# Queue Integration Guide

This document outlines the tasks and a minimal implementation plan to add a task queue to this project so long-running video-generation pipelines are handled reliably outside the Django web process.

**Goal:** Replace the current in-process background thread/subprocess approach in `web/views.py` with a robust task queue (recommended: Celery + Redis). Provide clear steps, required environment changes, and a minimal migration path so the repo stays simple but workable.

**Why a queue?**
- Long-running jobs (Gemini/Runway calls, `ffmpeg`) shouldn't run in web worker processes.
- Queues provide retries, timeouts, concurrency limits, and monitoring.
- Queueing lets you scale workers independently, manage rate limits, and keep web servers responsive.

**High-level design**
- Web UI enqueues a job (task) with the paper ID and output path.
- Worker process runs the pipeline (`kyle-code.pipeline.orchestrate_pipeline`) and writes outputs to `MEDIA_ROOT/<pmid>/`.
- Shared storage: For multi-host deployments, use S3/GCS for artifacts or a shared filesystem.

**Recommended stack**
- Task queue: Celery
- Broker: Redis
- Optional: `django-celery-results` for task result persistence and `flower` for monitoring

**Top-level tasks (ordered)**
1. Add dependencies and environment notes.
2. Add Celery scaffold to the Django project (`config/celery.py`).
3. Add `web/tasks.py` with a Celery task wrapper for `orchestrate_pipeline`.
4. Update `web/views.py` to enqueue tasks instead of starting threads/subprocesses.
5. Ensure workers share or can upload to `MEDIA_ROOT` (S3 or network share).
6. Add a `docker-compose` dev stack (optional) to run Redis + Celery locally.
7. Add run/test instructions and a simple smoke-test that enqueues a no-op or very small test job.
8. Add monitoring and graceful retry strategy.

Detailed steps and notes

**1) Dependencies**
- Add to `kyle-code/pyproject.toml` or root `requirements.txt`:
  - `celery[redis]`
  - `django-celery-results` (optional, to store results in DB)
  - `flower` (optional, for monitoring)

Example (append to `requirements.txt` or install manually):
```
celery[redis]
django-celery-results
flower
```

**2) Celery scaffold (`config/celery.py`)**
Create a small Celery app that reads settings from Django. Minimal example to add:

```python
# config/celery.py
import os
from celery import Celery

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
app = Celery('ai_study_videos')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()

if __name__ == '__main__':
    app.start()
```

Add to `config/__init__.py` (if not already):
```python
from .celery import app as celery_app
__all__ = ('celery_app',)
```

**3) Create a task wrapper (`web/tasks.py`)**
- Implement a Celery `@shared_task` that calls `orchestrate_pipeline`. Keep the wrapper small and let the pipeline handle idempotency.

Example:

```python
# web/tasks.py
from celery import shared_task
from pathlib import Path
from kyle_code.pipeline import orchestrate_pipeline, PipelineError

@shared_task(bind=True, max_retries=3, rate_limit='2/m', soft_time_limit=60*60)
def run_pipeline_task(self, pmid: str, output_dir: str, skip_existing=True, voice='Kore', max_workers=2, merge=True):
    out = Path(output_dir)
    try:
        orchestrate_pipeline(pmid=pmid, output_dir=out, skip_existing=skip_existing, voice=voice, max_workers=max_workers, merge=merge)
    except Exception as exc:
        raise self.retry(exc=exc, countdown=30)

```

**Note on import paths:** the example uses `kyle_code.pipeline` (PEP8 package-style) — adjust imports to match the project layout (in this repo the folder is `kyle-code`; when importing from Django tasks you'll need to ensure Python package importing works or add a tiny wrapper module under a valid package name).

**4) Enqueue from `web/views.py`**
- Replace `_start_pipeline_async(...)` or the `subprocess` call with a simple `run_pipeline_task.delay(pmid, str(output_dir))` call.
- Keep the existing `pipeline_status` endpoints, which already read logs / marker files.

Change example inside `upload_paper`:

```python
from .tasks import run_pipeline_task

# instead of _start_pipeline_async(...)
run_pipeline_task.delay(pmid, str(output_dir))
```

**5) Storage & deployment considerations**
- If web and worker run on same host and use the same `MEDIA_ROOT`, files will be visible to Django. For multi-host, switch to object storage (S3/GCS):
  - Option A: Modify pipeline to upload artifacts to S3 (using `boto3`) and update `pipeline_status` and `pipeline_result` to use signed URLs.
  - Option B: Mount shared storage (NFS) to `MEDIA_ROOT` on all hosts.

**6) Dev/test environment (docker-compose example)**
Add a `docker-compose.yml` with services: `redis`, `web` (Django), `worker` (Celery). Minimal example (conceptual):

```yaml
version: '3.8'
services:
  redis:
    image: redis:7
    ports: ['6379:6379']

  web:
    build: .
    command: python manage.py runserver 0.0.0.0:8000
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    volumes:
      - .:/app
    ports:
      - '8000:8000'

  worker:
    build: .
    command: celery -A config.celery.app worker --loglevel=info
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0
    volumes:
      - .:/app
```

**7) Testing & smoke checks**
- Install requirements in a venv.
- Run `redis-server` (or `docker-compose up redis`).
- Start a Celery worker: `celery -A config.celery.app worker --loglevel=info`.
- Start Django: `python manage.py runserver`.
- Trigger an enqueue via the upload UI or call `run_pipeline_task.delay('TEST_PAPER', '/tmp/test')` from Django shell.

**8) Monitoring & retries**
- Use `django-celery-results` to persist task results if you want UI status in DB.
- Use `flower` for lightweight monitoring.

**9) Rollout plan**
1. Implement Celery scaffold and task wrapper.
2. Add a dev compose file and smoke test with small synthetic job.
3. Replace thread/subprocess usage in `web/views.py` with enqueue.
4. Test in single-host mode (same `MEDIA_ROOT`).
5. Move to multi-host by adding S3 support or shared filesystem.
6. Add monitoring and adjust worker resource sizes.

**Appendix: Environment variables**
- `GEMINI_API_KEY` — required by the pipeline
- `RUNWAYML_API_SECRET` — required for video generation
- `CELERY_BROKER_URL` — e.g. `redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND` — optional (e.g., `django-db` via `django-celery-results`)

---

Keep things simple: implement the minimal Celery wrapper, keep the heavy logic inside `kyle-code` pipeline (it already has idempotency checks), and iterate on storage/monitoring as needed.
