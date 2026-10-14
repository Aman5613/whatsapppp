# Multi-stage Dockerfile: Builds frontend and serves everything via FastAPI on a single port
# Stage 1: Build React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /web
COPY apps/web/package.json apps/web/package-lock.json* ./
RUN npm ci
COPY apps/web/ .
RUN npm run build

# Stage 2: Backend + Static Asset Serving
FROM python:3.11-slim AS production
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl && \
    rm -rf /var/lib/apt/lists/*

COPY apps/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY apps/api/ .

# Copy built frontend into backend directory
COPY --from=frontend-builder /web/dist ./dist

# Create unprivileged user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000
ENV PORT=8000

# Start Uvicorn listening on Render's dynamic $PORT
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers --forwarded-allow-ips '*'"]
