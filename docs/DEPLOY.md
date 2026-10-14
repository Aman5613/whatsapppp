# Production Deployment Guide

This guide describes deploying the WhatsApp AI Auto-Reply Bot to a Linux VPS (Ubuntu/Debian) with Docker, automatic TLS via Caddy, and Neon Serverless PostgreSQL.

---

## 1. Prerequisites

- **Server:** 1 vCPU, 1 GB RAM minimum (e.g. Hetzner, DigitalOcean, AWS EC2, Linode).
- **Domain:** A domain or subdomain with an `A` record pointing to the server's public IPv4 (e.g., `bot.yourdomain.com`).
- **Database:** A Neon PostgreSQL database instance (pooled connection URL and direct URL).
- **Meta Developer Account:** WhatsApp Cloud API App configured with a verified business phone number.
- **AI Keys:** API key for OpenAI, Anthropic, or Google Gemini.

---

## 2. Server Initial Setup

1. **Update packages and install Docker:**
   ```bash
   sudo apt update && sudo apt upgrade -y
   sudo apt install -y curl git ufw
   curl -fsSL https://get.docker.com -o get-docker.sh
   sudo sh get-docker.sh
   sudo usermod -aG docker $USER
   ```

2. **Configure Firewall (UFW):**
   ```bash
   sudo ufw default deny incoming
   sudo ufw default allow outgoing
   sudo ufw allow ssh
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   sudo ufw enable
   ```

---

## 3. Clone Repository & Configure Environment

1. **Clone repository:**
   ```bash
   git clone <your-repo-url> /opt/whatsapp-bot
   cd /opt/whatsapp-bot
   ```

2. **Create production `.env`:**
   ```bash
   cp .env.example .env
   ```

3. **Configure essential variables in `.env`:**
   ```ini
   # Environment & Domain
   DEBUG=false
   DOMAIN=bot.yourdomain.com
   PUBLIC_BASE_URL=https://bot.yourdomain.com

   # Neon Database
   DATABASE_URL=postgresql+asyncpg://user:pass@ep-xyz-pooler.region.neon.tech/neondb?ssl=require
   DIRECT_DATABASE_URL=postgresql://user:pass@ep-xyz.region.neon.tech/neondb?sslmode=require

   # Cryptography & Security (Generate 32-byte base64 keys)
   # Python: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
   ENCRYPTION_KEY=<generated-fernet-key>
   # Python: python -c "import secrets; print(secrets.token_urlsafe(32))"
   SECRET_KEY=<generated-secret-key>
   ```

---

## 4. Run Migrations & Build Containers

1. **Run Database Migrations:**
   You can run migrations via Docker or the initial setup wizard on first visit:
   ```bash
   docker compose run --rm api alembic upgrade head
   ```

2. **Create Initial Owner User (via CLI or UI):**
   ```bash
   docker compose run --rm api python -m app.cli create-business \
       --name "My Store" \
       --email "admin@yourdomain.com" \
       --password "SecurePassword123!"
   ```
   *(Alternatively, visit the web dashboard at `https://bot.yourdomain.com` to use the Setup Wizard)*

3. **Launch the Stack:**
   ```bash
   docker compose up -d --build
   ```

4. **Verify Health:**
   ```bash
   curl -f https://bot.yourdomain.com/api/health
   # Response: {"status":"ok","version":"0.1.0"}
   ```

---

## 5. Configure WhatsApp Webhook in Meta Dashboard

1. Navigate to **Meta Developer Portal** → **Your App** → **WhatsApp** → **Configuration**.
2. Click **Edit** under **Callback URL**:
   - **Callback URL:** `https://bot.yourdomain.com/webhook/<YOUR_WEBHOOK_KEY>`
   - **Verify Token:** The verify token configured in your dashboard under Settings.
3. Click **Verify and Save**.
4. In Webhook fields, subscribe to **`messages`**.
