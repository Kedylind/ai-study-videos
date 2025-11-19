# config package

# Expose Celery app when Django starts (if present)
try:
	from .celery import app as celery_app  # type: ignore
except Exception:
	celery_app = None

__all__ = ("celery_app",)
