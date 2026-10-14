# Operational Runbook

This document describes routine maintenance, incident response, data retention policies, key rotation, and disaster recovery procedures.

---

## 1. Routine Deployment & Updates

### Deploying a New Release
```bash
cd /opt/whatsapp-bot
git pull origin main
docker compose run --rm api alembic upgrade head
docker compose up -d --build
```

### Checking Container Health and Logs
```bash
# View running status
docker compose ps

# View API logs
docker compose logs -f --tail=100 api

# View Caddy access / TLS logs
docker compose logs -f --tail=100 caddy
```

---

## 2. Data Retention & Privacy Compliance

### Running Automated Retention Cleanup
Purge message logs older than 90 days (or custom period):
```bash
# Preview what will be purged without deleting
docker compose run --rm api python -m app.cli cleanup-retention --days 90 --dry-run

# Execute purge
docker compose run --rm api python -m app.cli cleanup-retention --days 90
```

### Automated Nightly Cron
Add to the server's crontab (`crontab -e`):
```bash
0 3 * * * cd /opt/whatsapp-bot && docker compose run --rm api python -m app.cli cleanup-retention --days 90 >> /var/log/bot-cleanup.log 2>&1
```

### Handling Customer Data Deletion Requests (GDPR / DPDP)
To purge all conversations and records for a customer:
```bash
# Dry-run
docker compose run --rm api python -m app.cli delete-data \
    --business-id "<BUSINESS_UUID>" \
    --customer-phone "+919876543210" \
    --dry-run

# Commit deletion
docker compose run --rm api python -m app.cli delete-data \
    --business-id "<BUSINESS_UUID>" \
    --customer-phone "+919876543210"
```

---

## 3. Secret and Key Rotation

### Rotating `SECRET_KEY` (JWT Session Invalidation)
1. Generate new secret:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
2. Update `SECRET_KEY` in `.env`.
3. Restart API: `docker compose restart api`.
4. *Effect:* Existing user sessions will expire; users must log in again.

### Rotating `ENCRYPTION_KEY` (Fernet)
1. Generate new Fernet key.
2. In production, re-encrypt existing credentials (`access_token_enc`, `app_secret_enc`, `ai_api_key_enc`) using dual-key migration script or update them via Settings UI.
3. Update `ENCRYPTION_KEY` in `.env` and restart containers.

---

## 4. Disaster Recovery & Database Backup

### Neon Point-in-Time Restore (PITR)
- Neon maintains continuous Write-Ahead Log (WAL) backups.
- To restore from an accidental data deletion or incident:
  1. Open the **Neon Console** → Select your Project.
  2. Navigate to **Branches** → Click **Create Branch**.
  3. Select **Point in Time** and choose the timestamp prior to the incident.
  4. Point `.env` to the restored branch's connection URL.

---

## 5. Troubleshooting Incidents

| Issue | Diagnostic | Resolution |
|---|---|---|
| **Meta Webhook Signature Failed (403)** | `docker compose logs api \| grep signature_invalid` | Check App Secret in Settings against Meta Developer Portal App Secret. |
| **Meta 24h Window Expired** | Outbound message rejected or skipped | Customer last messaged over 24 hours ago. A business-initiated template message is required to re-open the window. |
| **High Database Latency** | `pool_pre_ping` retry logs | Check if Neon branch was sleeping (cold start). The engine auto-reconnects with exponential retry. |
| **LLM Provider Outage** | 503 / 429 from OpenAI/Anthropic/Gemini | Fallback provider will be attempted automatically if configured in Settings. |
