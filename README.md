# WhatsApp AI Auto-Reply Bot

AI-powered WhatsApp auto-reply bot with conversation memory, business-data tools, human handoff, and an admin dashboard.

## Architecture

```
Customer → Meta Cloud API → POST /webhook/{key} → FastAPI → LLM → WhatsApp reply
Dashboard (React) → /api/* (cookie auth) → same database
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2 (async), Alembic |
| Frontend | React (JS), Vite, TanStack Query, Tailwind CSS |
| Database | PostgreSQL on Neon (serverless) |
| AI | Provider-agnostic (Anthropic, OpenAI, Gemini) |
| Deploy | Docker Compose + Caddy (auto HTTPS) |

## Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- A [Neon](https://neon.tech) PostgreSQL project
- A Meta WhatsApp Business API app

## Setup

### 1. Clone and configure

```bash
cp .env.example .env
# Edit .env with your Neon connection strings and secrets
```

### 2. Generate security keys

```bash
# SECRET_KEY
python -c "import secrets; print(secrets.token_urlsafe(64))"

# ENCRYPTION_KEY
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### 3. Create the Neon project

1. Go to [Neon Console](https://console.neon.tech)
2. Create a new project
3. Copy the **pooled** connection string → `DATABASE_URL` in `.env`
4. Copy the **direct** connection string → `DIRECT_DATABASE_URL` in `.env`

### 4. Run locally (development)

```bash
# Backend
cd apps/api
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend (separate terminal)
cd apps/web
npm install
npm run dev
```

### 5. Run with Docker

```bash
docker compose up --build
# App available at http://localhost
# API health: http://localhost/api/health
```

### 6. Create the Meta WhatsApp Business App

1. Go to [Meta for Developers](https://developers.facebook.com)
2. Create a Business app → add WhatsApp product
3. Note: Phone Number ID, WABA ID, Access Token, App Secret
4. Configure webhook URL: `{PUBLIC_BASE_URL}/webhook/{webhook_key}`
5. Subscribe to `messages` webhook field

## Development Commands

```bash
make help          # Show all commands
make api-dev       # Run API with hot reload
make web-dev       # Run React dev server
make lint          # Run all linters
make test          # Run backend tests
make migrate       # Run database migrations
make up            # Start Docker services
```

## Project Structure

```
├── apps/
│   ├── api/          # FastAPI backend
│   │   ├── app/
│   │   │   ├── core/       # Config, database, logging, auth
│   │   │   ├── models/     # SQLAlchemy models
│   │   │   ├── schemas/    # Pydantic schemas
│   │   │   ├── routers/    # API endpoints
│   │   │   ├── services/   # Business logic (AI, WhatsApp, pipeline)
│   │   │   ├── tools/      # LLM tool definitions
│   │   │   └── cli.py      # Management CLI
│   │   ├── alembic/        # Database migrations
│   │   └── tests/
│   └── web/          # React dashboard
│       └── src/
│           ├── pages/
│           ├── components/
│           ├── hooks/
│           └── api/
├── docs/
├── docker-compose.yml
├── Caddyfile
└── Makefile
```
