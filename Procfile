image.pngweb: python manage.py migrate --noinput && python manage.py collectstatic --noinput && python -m gunicorn config.wsgi:application --bind 0.0.0.0:${PORT}
worker: celery -A config worker --loglevel=info --concurrency=2 --max-tasks-per-child=50 --uid=1000 --gid=1000
