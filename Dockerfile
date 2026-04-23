# ═══════════════════════════════════════════════════════════════
# Stage 1: builder — compiles all Python deps once
# ═══════════════════════════════════════════════════════════════
FROM python:3.11-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Build-time system deps. These NEVER make it into the final image.
# `libpq-dev` is needed to build psycopg2; `build-essential` brings gcc
# for any other C extension (cryptography, cffi, ...).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       build-essential \
       libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install into /install so we can copy exactly that tree into stage 2.
# `--prefix=/install` gives us /install/bin, /install/lib/..., etc.,
# which maps cleanly onto /usr/local in the runtime image.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --upgrade pip \
    && pip install --prefix=/install -r /tmp/requirements.txt


# ═══════════════════════════════════════════════════════════════
# Stage 2: runtime — the image that actually ships to ECR
# ═══════════════════════════════════════════════════════════════
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Runtime-only system deps. libpq5 is the shared library psycopg2 links
# against (~3MB). We deliberately DO NOT install libpq-dev or gcc here.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --system --home-dir /app --shell /bin/bash django

WORKDIR /app

# Bring in the pre-built Python packages from the builder stage.
# They land at /usr/local/{bin,lib,...} which is already on PATH and
# PYTHONPATH by default for python:slim.
COPY --from=builder /install /usr/local

# Copy the application code with correct ownership upfront.
COPY --chown=django:django . /app/

# Collect static files. A dummy SECRET_KEY is fine here because
# settings.py refuses to start without one, and collectstatic does
# not read anything sensitive at build time.
RUN SECRET_KEY='dummy-key-for-build' python manage.py collectstatic --noinput \
    && chmod +x /app/entrypoint.sh \
    && chown -R django:django /app/staticfiles

# Run as non-root for the rest of the container's life.
USER django

EXPOSE 4000

CMD ["/app/entrypoint.sh"]
