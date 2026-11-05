"""Single-origin container application; preserve the separate local dev servers."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "salary_web.settings")

from django.core.asgi import get_asgi_application
from api.main import app

# Registered API routes (/health, /api/v1/predict, /docs) take precedence.
app.mount("/", get_asgi_application())
