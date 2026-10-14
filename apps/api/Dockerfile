FROM python:3.11-slim AS base

WORKDIR /app

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Non-root user for security hardening
RUN useradd -m -u 1000 appuser

# Copy application source
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

# Run uvicorn behind reverse proxy with forwarded headers
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers", "--forwarded-allow-ips", "*"]
