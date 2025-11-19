import os
import logging

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

logger = logging.getLogger(__name__)

# Use environment variable or Django setting to configure broker
broker_url = os.getenv("CELERY_BROKER_URL")

app = Celery("ai_study_videos")

# Default configuration will read from Django settings prefixed with CELERY_
app.config_from_object("django.conf:settings", namespace="CELERY")

if broker_url:
    # allow override from env
    app.conf.broker_url = broker_url

# autodiscover tasks from installed apps
app.autodiscover_tasks()


@app.task(bind=True)
def debug_task(self):
    logger.info(f"Celery debug task running: {self.request!r}")
    return "ok"
