# Queue Integration — Completion Report

This document summarizes the work completed to add a Celery-based task queue to this repository, the tests performed, safety improvements applied, outstanding risks, and recommended next steps.

Date: 2025-11-19

## Scope
- Goal: Add a production-quality task queue (Celery + Redis) to run long-running video-generation pipelines outside the Django web process.
- Outcome: Celery scaffold, task wrappers, a local dev `docker-compose` stack, smoke tests, and documentation scaffolding. Local smoke tests passed.

## Files added / modified
- `config/celery.py` — Celery app scaffold (reads Django settings; supports `CELERY_BROKER_URL`).
- `config/__init__.py` — exposes `celery_app`.
- `config/settings.py` — added `django_celery_results` to `INSTALLED_APPS`; added `CELERY_BROKER_URL` and `CELERY_RESULT_BACKEND` defaults.
- `kyle_code/__init__.py` — compatibility wrapper so `kyle-code` scripts can be imported as `kyle_code`.
- `web/tasks.py` — added `run_pipeline_task` (Celery wrapper for `orchestrate_pipeline`) and `write_marker_task` (no-op marker writer). Added file-based logging to `output_dir/pipeline.log` for UI integration. Added retries/timeouts/acks_late.
- `web/views.py` — prefer enqueueing Celery task when `CELERY_BROKER_URL` configured; fall back to original subprocess/thread runner.
- `requirements.txt` — added `celery[redis]`, `django-celery-results`, `flower`.
- `docker-compose.yml` — dev stack: `redis`, `web`, `worker`, `flower`. (Mounts `/tmp` for smoke test verification.)
- `scripts/smoke_celery_test.py` — synchronous import/import-time smoke test for Celery integration.
- `scripts/enqueue_marker.py` — helper to enqueue the marker task from inside the `web` container.
- `QUEUE_README.md` and `ROLES.md` — planning and agent roles documentation.

## What I ran & verified
- Synchronous smoke test: `python3 scripts/smoke_celery_test.py` — imported `config.celery` and ran `debug_task.apply()` synchronously (no Redis required). PASS.
- Docker-compose smoke test:
  1. `docker-compose up -d --build redis worker web`
  2. `docker-compose exec web python3 scripts/enqueue_marker.py`
  3. Verified marker: `/tmp/celery_test_marker.txt` (host) was written by the worker. PASS.
- Git: changes committed to branch `skel-dev`.

## Safety & improvements applied
- Per-task file logging: `run_pipeline_task` attaches a temporary `FileHandler` that writes `output_dir/pipeline.log`, keeping the existing web UI log-tail behavior.
- Task robustness: `run_pipeline_task` configured with `max_retries`, `soft_time_limit`, `time_limit`, and `acks_late=True`.
- Retry handling: `PipelineError` and general exceptions are caught and retried with sensible countdowns. `write_marker_task` uses `max_retries` and proper `self.retry()` usage.
- Compatibility: Added `kyle_code` wrapper to import `kyle-code` modules without renaming folders.

## Outstanding risks & required production work
These items must be completed before declaring the integration production-ready:

1. Secrets: provide `GEMINI_API_KEY`, `RUNWAYML_API_SECRET`, and other API keys to worker/web via environment variables or a secrets manager. Do not commit secrets to the repo.
2. Native dependencies: install `ffmpeg` and any OS-level packages on worker containers. Replace the current `python:3.12-slim` container-with-install pattern with a proper `Dockerfile` that pre-installs system packages and Python deps.
3. Migrations & result backend: `django-celery-results` requires migrations. Run `python manage.py migrate` and ensure worker startup is sequenced after migrations/DB readiness.
4. Storage strategy: the pipeline currently writes artifacts to `MEDIA_ROOT` on the local filesystem (single-host). For multi-host deployments, implement S3/GCS uploads in the pipeline or mount a shared network filesystem.
5. Backoff & error classification: implement exponential backoff and classify transient vs. fatal errors to avoid retry storms.
6. Rate limiting & queues: add Celery `rate_limit` or dedicated worker queues to respect remote API quotas. Configure worker concurrency appropriately.
7. Monitoring & security: secure Flower, add centralized logging/metrics (Prometheus/ELK), and add alerting for task failures.

## Recommended next steps (priority)
1. Add a production `Dockerfile` that installs `ffmpeg` and pre-installs Python deps; update `docker-compose.yml` to use built images.
2. Add `.env.example` and update `docker-compose.yml` to read env vars from an `env_file`. Ensure secrets are supplied securely.
3. Implement S3/GCS artifact upload in `kyle-code/pipeline.py` or adopt a shared filesystem approach.
4. Harden retry strategy: exponential backoff, error classification, and clearer failure semantics (no-retry for fatal errors).
5. Add unit/integration tests that mock external APIs to validate `run_pipeline_task` retry and log-writing behavior.

## Reproduction commands (dev)
```bash
# install deps (optional, for local dev)
pip install -r requirements.txt

# run synchronous smoke import test (no Redis required)
python3 scripts/smoke_celery_test.py

# start services (docker required)
docker-compose up -d --build redis worker web

# enqueue marker task from web container
docker-compose exec web python3 scripts/enqueue_marker.py

# verify marker on host
ls -l /tmp/celery_test_marker.txt
cat /tmp/celery_test_marker.txt
```

## Status
- Local dev sign-off: PASS (smoke tests passed and marker file verified via docker-compose).
- Production sign-off: NOT YET — see 'Outstanding risks' above.

---

If you want, I can now:
- Add a production-ready `Dockerfile` and update compose to use it, or
- Implement S3 artifact upload and signed-URL support in the pipeline, or
- Implement exponential backoff and queue-level rate limits.

Tell me which next step you'd like and I'll implement it.
