FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DJANGO_SETTINGS_MODULE=salary_web.settings \
    DJANGO_DEBUG=False \
    SALARY_API_URL=/
WORKDIR /app
ARG DEPLOYMENT_VERSION=local
ENV DEPLOYMENT_VERSION=$DEPLOYMENT_VERSION

COPY requirements.txt requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt -r requirements.txt && python -m pip check

# Explicit allowlist: never copy local models, credentials, data, or Git metadata.
COPY manage.py ./
COPY api/ ./api/
COPY ml/ ./ml/
COPY salary_web/ ./salary_web/
COPY webapp/ ./webapp/
COPY templates/ ./templates/
COPY static/ ./static/

# Rebuild the frozen selected model from only the 80 committed training rows.
# A failed deserialization, dependency import, or prediction fails the image build.
RUN python -m ml.build_model \
    && python -c "from pathlib import Path; assert not Path('/app/ml/datasets/test.csv').exists(), 'Final test data must not enter training image'" \
    && python -m ml.check_model \
    && python manage.py check \
    && python manage.py collectstatic --noinput

RUN useradd --create-home --uid 10001 appuser && mkdir /state && chown appuser:appuser /state
USER appuser
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["python", "-m", "uvicorn", "api.container:app", "--host", "0.0.0.0", "--port", "8000"]
