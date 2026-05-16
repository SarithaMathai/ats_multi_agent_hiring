# ── ATS App Dockerfile ────────────────────────────────────────────────────────
# Multi-stage build: development target has hot-reload tools;
# production target is a slim, non-root image.

ARG PYTHON_VERSION=3.11
ARG POETRY_VERSION=1.8.3

# ── Base stage ────────────────────────────────────────────────────────────────
FROM python:${PYTHON_VERSION}-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    POETRY_VERSION=${POETRY_VERSION} \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=false \
    PATH="/opt/poetry/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN curl -sSL https://install.python-poetry.org | python3 -

WORKDIR /app

COPY pyproject.toml poetry.lock* ./

# ── Development stage ─────────────────────────────────────────────────────────
FROM base AS development

RUN poetry install --no-interaction --no-ansi

COPY . .

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]

# ── Production stage ──────────────────────────────────────────────────────────
FROM base AS production

RUN poetry install --no-interaction --no-ansi --only main

COPY . .

# Create non-root user
RUN addgroup --system ats && adduser --system --ingroup ats ats
USER ats

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
