FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Install uv for fast reliable package management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy dependency definitions
COPY pyproject.toml .

# Install python dependencies into system environment
RUN uv pip install --system -r pyproject.toml

# Copy project files
COPY . .

# Expose healthcheck / port if running webhooks
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD python3 -c "import socket; s = socket.socket(); s.connect(('127.0.0.1', 6379)); s.close()" || exit 0

# Start bot
CMD ["python3", "-m", "app.main"]
