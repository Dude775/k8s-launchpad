# field-guide-api Dockerfile — multi-stage python:3.11-slim, non-root UID 10001, gunicorn PID 1.
# Source: CLAUDE.md researched stack pattern + docs.gunicorn.org/en/stable/signals.html
# Build context: apps/field-guide-api/

# --- Builder stage ---
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Runtime stage ---
FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app

# Copy installed packages from builder (avoids re-downloading in runtime layer)
COPY --from=builder /install /usr/local

# Explicit allowlist COPY — never a broad COPY . . (keeps Windows venv and test
# artifacts out even if .dockerignore were absent; defense-in-depth against T-03-02)
COPY app/ ./app/
COPY wsgi.py .

# Non-root user — numeric UID so Kubernetes runAsNonRoot is verifiable by the kubelet.
# A named USER directive cannot be validated by runAsNonRoot: true in pod securityContext.
RUN groupadd -r -g 10001 app && useradd -r -u 10001 -g app app
USER 10001

EXPOSE 8000

# Exec form (JSON array) — gunicorn becomes PID 1 and receives SIGTERM directly.
# Shell form would put /bin/sh at PID 1 and swallow SIGTERM → 30s force-kill on every rollout.
# gunicorn TERM = graceful shutdown (default graceful_timeout 30s matches K8s terminationGracePeriodSeconds).
# workers=1 is mandatory: multiple workers corrupt prometheus-flask-exporter metrics registries.
# --access-logfile - routes access logs to stdout for kubectl logs (and future Loki scraping).
CMD ["gunicorn", "--bind", "0.0.0.0:8000", \
     "--workers", "1", "--threads", "4", \
     "--access-logfile", "-", "--error-logfile", "-", \
     "wsgi:app"]
