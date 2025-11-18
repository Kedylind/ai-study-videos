import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Ensure STATIC_ROOT directory exists before Django starts
# This is critical for WhiteNoise to work properly
try:
    from django.conf import settings
    from pathlib import Path
    static_root = Path(settings.STATIC_ROOT)
    static_root.mkdir(parents=True, exist_ok=True)
except Exception:
    # If settings aren't loaded yet, we'll try again after get_wsgi_application
    pass

application = get_wsgi_application()

# Try again after Django is fully loaded
try:
    from django.conf import settings
    from pathlib import Path
    static_root = Path(settings.STATIC_ROOT)
    static_root.mkdir(parents=True, exist_ok=True)
except Exception:
    pass
