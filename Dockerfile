# syntax=docker/dockerfile:1.7

# ---------- Stage 1: builder ----------
FROM python:3.13-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Poetry lives in its own venv: `pip install --prefix` skips anything already present in the
# system site-packages, so poetry's own dependencies would silently go missing from /install.
RUN python -m venv /opt/poetry \
 && /opt/poetry/bin/pip install poetry==2.3.4 poetry-plugin-export==1.9.0

WORKDIR /build

# Dependencies get their own layer, pinned (with hashes) from poetry.lock: the image installs
# exactly what the tests ran against, and the layer is rebuilt only when the lock changes.
COPY pyproject.toml poetry.lock README.md ./
RUN /opt/poetry/bin/poetry export --only main --format requirements.txt --output requirements.txt \
 && pip install --prefix=/install -r requirements.txt

# --no-deps: every dependency is already installed from the pinned set above.
COPY caching_svc/ caching_svc/
RUN /opt/poetry/bin/poetry build --format wheel \
 && pip install --prefix=/install --no-deps dist/*.whl

# ---------- Stage 2: runtime ----------
FROM python:3.13-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN groupadd --system --gid 10001 app \
 && useradd  --system --uid 10001 --gid app --no-create-home --shell /sbin/nologin app

WORKDIR /app

# Installed packages only: no poetry, no wheels, no build toolchain.
COPY --from=builder /install /usr/local

# Alembic migrations are not part of the wheel.
COPY --chown=app:app alembic.ini /app/alembic.ini
COPY --chown=app:app alembic/    /app/alembic/

USER 10001:10001

EXPOSE 8000

# Console scripts: `website` (API), `cache-cli` (test client), `alembic upgrade head` (migrations).
CMD ["website"]
