FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    COVERAGE_FILE=/tmp/.coverage \
    PYTEST_ADDOPTS="-p no:cacheprovider" \
    RUFF_CACHE_DIR=/tmp/.ruff_cache \
    PORT=5000

WORKDIR /app

RUN addgroup --system aceest && adduser --system --ingroup aceest aceest

COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir --requirement requirements-dev.txt

COPY --chown=aceest:aceest app.py ./
COPY --chown=aceest:aceest templates ./templates
COPY --chown=aceest:aceest static ./static
COPY --chown=aceest:aceest tests ./tests
COPY --chown=aceest:aceest pyproject.toml ./

RUN mkdir -p /app/instance && chown aceest:aceest /app/instance

USER aceest

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=2)"

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "2", "--access-logfile", "-", "app:app"]
