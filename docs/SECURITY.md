# Security Architecture & Threat Model

This document outlines the security architecture, data protection controls, and defenses implemented across the application.

---

## 1. Secrets Management & Encryption at Rest

- **Fernet Symmetric Encryption:**
  - WhatsApp Graph API access tokens, App Secrets, and AI Provider keys (OpenAI, Anthropic, Gemini) are never stored in plaintext.
  - Encrypted at rest using Fernet (`cryptography` library) with `AES-128-CBC` and `HMAC-SHA256` authentication.
- **Write-Only Settings API:**
  - GET `/api/settings` returns masked values (e.g. `sk-...abcd`, `EAA...1234`).
  - Full keys are never returned to the frontend or exposed in logs.
- **Environment Isolation:**
  - Container runs under an unprivileged user (`appuser`, UID 1000).

---

## 2. Authentication & Session Security

- **Argon2id Password Hashing:**
  - User passwords hashed using memory-hard Argon2id via `argon2-cffi`.
- **JWT HttpOnly Cookies:**
  - Sessions issued as signed JWT cookies with `HttpOnly` and `SameSite=Lax`.
  - Immune to JavaScript XSS token theft.
  - `Secure` attribute automatically enforced in production environments (`https`).
- **CSRF Defense:**
  - State-modifying requests validate authentication cookie and origin headers.

---

## 3. Webhook Integrity & Replay Defense

- **HMAC-SHA256 Signature Verification:**
  - Every inbound Meta webhook payload is validated against `X-Hub-Signature-256` using the business's decrypted App Secret.
  - Invalid or missing signatures return an immediate `403 Forbidden`.
- **Deduplication:**
  - Every message is checked against the database index on `messages.wa_message_id`.
  - Replayed or retried webhook payloads from Meta are safely acknowledged with `200 OK` and discarded without triggering duplicate bot responses.

---

## 4. Multi-Tenant Data Isolation

- **Scoped Repositories:**
  - Every database query in the repository layer automatically appends `.where(Model.business_id == self.business_id)`.
  - Primary keys use UUID v7 (non-sequential, preventing ID enumeration attacks).
- **Customer Phone Boundary:**
  - Sensitive operations such as `get_order_status` require both `business_id` and the customer's verified WhatsApp sender phone.

---

## 5. Network & HTTP Hardening

- **Security Headers Middleware:**
  - `X-Content-Type-Options: nosniff` (prevents MIME sniffing).
  - `X-Frame-Options: DENY` (clickjacking protection).
  - `X-XSS-Protection: 1; mode=block`.
  - `Referrer-Policy: strict-origin-when-cross-origin`.
  - `Strict-Transport-Security` (HSTS enabled for production/HTTPS).
- **Caddy Reverse Proxy:**
  - Automated Let's Encrypt / ZeroSSL TLS certificates with TLS 1.3 and modern cipher suites.
  - Server tokens stripped from response headers.
