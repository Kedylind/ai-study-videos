"""
Celery configuration for Hidden Hill video generation tasks.

This module sets up Celery for asynchronous task processing.
Tasks are stored in Redis (or RabbitMQ) broker and survive server restarts.
"""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Create Celery app instance
app = Celery("hidden_hill")

# Load configuration from Django settings
# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Auto-discover tasks from all registered Django apps
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery setup."""
    print(f"Request: {self.request!r}")

