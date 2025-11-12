Hidden Hill staging (Django)

This repository now contains a minimal Django 5 app for staging/deployment. Files added include a small `web` app with a home and health endpoint, `config` settings, a `Procfile`, and `requirements.txt`.

Endpoints:
- / -> home page
- /health -> JSON health check

To set up locally in a Codespace or Linux environment, from the repository root run:

```bash
git init
python -V
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py runserver 0.0.0.0:8000
```

Stop the server with Ctrl+C. Forward port 8000 in your Codespace to view the site.
