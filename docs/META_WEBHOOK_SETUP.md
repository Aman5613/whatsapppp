# Meta WhatsApp Cloud API Webhook Setup Guide

This guide walks you through registering your local or production WhatsApp Bot webhook with Meta.

---

## 1. Local Development Tunnels (ngrok or cloudflared)

Meta requires a publicly accessible HTTPS URL to deliver webhook events.

### Option A: ngrok
```bash
ngrok http 8000
# Output example: Forwarding https://abcd-1234.ngrok-free.app -> http://localhost:8000
```

### Option B: Cloudflare Tunnel (cloudflared)
```bash
cloudflared tunnel --url http://localhost:8000
# Output example: https://random-name.trycloudflare.com
```

Copy your public HTTPS forwarding URL (e.g. `https://abcd-1234.ngrok-free.app`).

---

## 2. Locate Your Business Webhook URL

Each business has a unique, secure `webhook_key`.
- In the dashboard or CLI, find your business `webhook_key`.
- Your full webhook callback URL is:
  ```
  https://<your-domain-or-tunnel>/webhook/<your-webhook-key>
  ```
- Example: `https://abcd-1234.ngrok-free.app/webhook/Vz61j_X_9LpQ...`

---

## 3. Register in Meta App Dashboard

1. Log in to [Meta for Developers](https://developers.facebook.com).
2. Select your app and navigate to **WhatsApp** -> **Configuration**.
3. Under **Webhook**, click **Edit**.
4. Enter:
   - **Callback URL:** `https://<your-tunnel-domain>/webhook/<your-webhook-key>`
   - **Verify Token:** The exact `verify_token` configured in your `whatsapp_numbers` table / Settings.
5. Click **Verify and Save**. Meta will send a `GET` request with `hub.challenge`. Your server will return it with `200 OK`.
6. Under **Webhook fields**, click **Manage** and subscribe to:
   - `messages` (required for incoming chats, reads, deliveries)

---

## 4. Testing Your Webhook

Send a WhatsApp message from any personal phone to your WhatsApp Business test number.
- In **Phase 2**, the bot responds automatically with: `Echo: <your message>`.
- Duplicate messages received from Meta retries are safely ignored via `wa_message_id` deduplication.
