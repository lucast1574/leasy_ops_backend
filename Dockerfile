# Stage 1: Build stage
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies needed for building Python packages
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# Stage 2: Production stage
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install only runtime dependencies (libpq is needed for psycopg2)
RUN apt-get update && apt-get install -y \
    libpq5 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Copy virtualenv from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy project files
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p /app/staticfiles /app/media && \
    useradd -m leasyuser && \
    chown -R leasyuser:leasyuser /app

# Ensure entrypoint script is executable and has Linux line endings (fix Windows CRLF)
RUN apt-get update && apt-get install -y dos2unix --no-install-recommends && \
    dos2unix /app/scripts/entrypoint.sh && \
    chmod +x /app/scripts/entrypoint.sh && \
    rm -rf /var/lib/apt/lists/*

USER leasyuser

EXPOSE 8000
ENTRYPOINT ["/app/scripts/entrypoint.sh"]

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120", "core.wsgi:application"]
