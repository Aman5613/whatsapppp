# Progress Tracker

## Phase 0: Foundation ✅
- Monorepo skeleton created
- FastAPI app with `/api/health` endpoint
- Vite React (JavaScript) placeholder with Tailwind CSS
- Docker Compose (api, web build, caddy)
- `.env.example` with all required variables
- Structured logging (structlog)
- Async database setup with Neon-friendly pool settings
- ruff + pytest + eslint configured
- README with setup instructions
- Makefile with dev shortcuts

### Decisions & Feedback Incorporated
- UUID7 for primary keys (time-ordered, multi-business ready)
- Inter font for dashboard with WhatsApp green/teal theme
- No fixed domain required: Settings page will display dynamic webhook URL based on current base URL / ngrok / tunnel.
- Frontend Settings page & First-Run Wizard:
  - Setup Wizard shown if DB is unconfigured on first launch (inputs Neon connection, initializes schema, creates owner).
  - Ability to test and update DB connection strings anytime from UI (updates `.env`, runs migrations, rebinds engine dynamically).
  - Meta WhatsApp credentials (`phone_number_id`, `waba_id`, `access_token`, `app_secret`, `verify_token`) + Test Connection.
  - AI API keys (OpenAI, Anthropic, Gemini) + model selector + Test Connection.


## Phase 1: Database & Models ✅
- All SQLAlchemy 2 models with UUID7 primary keys and timestamps with timezone:
  - `businesses`, `whatsapp_numbers`, `users`, `customers`, `conversations`, `messages`, `products`, `orders`, `order_items`, `tool_calls`, `usage_log`.
- All foreign keys, cascade deletes, and composite indexes:
  - `messages(conversation_id, created_at)`
  - `conversations(business_id, last_customer_message_at)`
  - `customers(business_id, phone)` unique constraint.
- Fernet symmetric encryption helper (`app/core/crypto.py`) with secret masking.
- Multi-tenant scoped repository layer (`BaseRepository`, `CustomerRepository`, `ConversationRepository`, `MessageRepository`, `ProductRepository`, `OrderRepository`).
- CLI command `create-business` with Argon2 password hashing.
- Alembic configuration with initial migration `001_initial_schema.py`.
- Dynamic database reconnection and in-app migration runner (`app/core/database.py`).
- 16 tests passing across models, crypto roundtrip, tenant isolation, and CLI.

---

## Phase 2: WhatsApp Webhook & Sending ✅
- `GET /webhook/{webhook_key}` verification handshake with Meta (`hub.mode`, `hub.verify_token`, `hub.challenge`).
- `POST /webhook/{webhook_key}` with per-business `X-Hub-Signature-256` HMAC-SHA256 signature verification (403 on invalid).
- Background event handling:
  - Deduplication via `wa_message_id` (safely drops duplicate retries).
  - Customer and Conversation upserting.
  - Inbound message persistence with role `customer`.
  - 24-hour customer service window validation.
  - Temporary echo response handler with `send_text` and `mark_as_read`.
  - Status updates (`delivered`, `read`).
  - Human mode check (suppresses bot echo when `mode == "human"`).
- WhatsApp Cloud API client (`app/services/whatsapp/client.py`) with v21.0 Graph API integration.
- Setup guide for local tunneling (ngrok/cloudflared) and Meta configuration (`docs/META_WEBHOOK_SETUP.md`).
- 31 automated tests passing across verification, HMAC signatures, deduplication, echo handling, and client requests.

---

## Phase 3: AI Provider Layer ✅
- Provider-agnostic normalized types: `Msg`, `ToolSpec`, `ToolCall`, `ToolResult`, `LLMResult`, `Usage`, `StopReason`.
- Thin vendor adapters:
  - `OpenAIAdapter`: Chat Completions API with function calling and usage tracking.
  - `AnthropicAdapter`: Messages API with tool_use / tool_result blocks.
  - `GeminiAdapter`: REST API with functionDeclarations and system_instruction.
- Standardized error hierarchy: `LLMError`, `AuthError`, `RateLimitError`, `ProviderUnavailableError`, `InvalidRequestError`.
- Exponential backoff retry helper (`call_with_retry`) and automatic fallback provider execution (`generate_with_fallback`).
- Provider registry and business builder (`app/services/ai/registry.py`).
- Live key smoke-testing CLI script (`apps/api/scripts/try_providers.py`).
- 51 total tests passing, including comprehensive contract tests across all three providers.

---

## Phase 4: Memory & Reply Pipeline ✅
- Token-budget memory loader (`app/services/memory/loader.py`) with chronological ordering, heuristic token trimming, and latest message preservation.
- System prompt builder (`app/services/pipeline/system_prompt.py`) incorporating business system prompt, language adaptation (Hindi/English/Hinglish), tone, and tool truthfulness rules.
- Customer sliding window rate limiter (`app/services/pipeline/rate_limit.py`).
- Reply pipeline orchestrator (`app/services/pipeline/orchestrator.py`):
  - Per-conversation async locking (`asyncio.Lock`) guaranteeing ordered processing of rapid messages.
  - Multi-turn context loading.
  - Full WhatsApp sending via Meta Graph API.
  - Usage log persistence into `usage_log` table.
  - Graceful single error fallback message on LLM failures (no loops).
- Integrated into webhook event background handler (`app/webhook/handlers.py`).
- 62 automated tests passing across memory trimming, system prompt, rate limiting, and multi-turn pipeline orchestration.

---

## Phase 5: Business Data & Tools ✅
- Abstract `ProductSource` interface (`app/tools/interfaces.py`) decoupling data sources (local DB, Shopify, WooCommerce).
- `DatabaseProductSource` (`app/tools/product_source.py`) tenant-scoped implementation.
- Built-in LLM tools:
  - `search_products`: Case-insensitive partial name & category search with stock visibility.
  - `get_order_status`: Customer phone and tenant isolated order lookup.
  - `handoff_to_human`: Mode switcher setting `conversation.mode = "human"` and `flagged_for_human = True`.
- Tool registry (`app/tools/registry.py`) providing automatic specs, audit persistence to `tool_calls` table, and schema conversion.
- Multi-turn tool execution loop in `ReplyOrchestrator` (up to 5 iterations).
- Bulk CSV import service (`app/services/csv_import.py`) with dry-run validation and error reporting.
- REST endpoints for products and orders (`/api/products`, `/api/orders`).
- 69 automated tests passing covering tools, registry, tool loop, CSV import, and SQL injection safety.

---

## Phase 6: Human Handoff ✅
- Multi-trigger handoff architecture:
  - LLM tool trigger (`handoff_to_human`).
  - Proactive keyword/intent heuristic detection (`detect_handoff_intent`) in inbound webhook.
  - Operator manual takeover via REST API.
- Silent bot enforcement: Bot auto-replies completely suppressed whenever `conversation.mode == "human"`.
- Handoff service (`app/services/handoff/service.py`):
  - `transition_to_human` & `transition_to_bot`.
  - `auto_return_inactive_conversations`: Reverts idle human-mode conversations to bot mode after inactivity timeout.
  - `send_human_reply`: Validates 24-hour WhatsApp service window, dispatches via Graph API, and records message with `role="human"`.
- REST API endpoints:
  - `GET /api/handoff`: Handoff queue inbox with message summaries, unread status, and customer details.
  - `POST /api/handoff/auto-return`: Periodic or manual trigger for auto-return.
  - `GET /api/conversations`: List conversations with mode and filter options.
  - `GET /api/conversations/{id}`: Detailed conversation view with full message history.
  - `POST /api/conversations/{id}/take-over`: Operator takes over conversation.
  - `POST /api/conversations/{id}/return-to-bot`: Operator returns conversation to bot.
  - `POST /api/conversations/{id}/messages`: Operator sends live reply to customer via WhatsApp.
- 80 automated tests passing across triggers, transitions, queue filtering, 24h service window enforcement, and tenant isolation.

---

## Phase 7: Auth & Dashboard ✅
- Backend Security & Auth:
  - Argon2id password hashing and JWT token operations (`app/core/security.py`).
  - HttpOnly, SameSite=Lax cookie-based authentication with `get_current_user` dependency.
  - Setup & Auth API (`/api/auth/status`, `/api/auth/setup`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`).
- Settings & Dynamic Database Wizard API:
  - Settings retrieval with Fernet-masked secrets (`/api/settings`).
  - Secure credential patching (`PATCH /api/settings`).
  - Live AI model test endpoint (`POST /api/settings/test-ai`).
  - Live WhatsApp Graph API test endpoint (`POST /api/settings/test-whatsapp`).
  - Runtime database status, connection testing, and dynamic Alembic migration runner without server restart (`/api/settings/database/*`).
- Usage & Analytics API (`/api/usage`):
  - Aggregated KPI cards, token metrics, cost estimations, model breakdowns, and recent call logs.
- React Frontend Dashboard (`apps/web`):
  - Sleek modern responsive dashboard UI with dark theme and custom SVG iconography.
  - Views built:
    - `LoginView` & `SetupView` (First-run wizard).
    - `ConversationsView`: Real-time chat list, message thread with role bubbles (Customer/Bot/Operator), takeover & return toggles, 24h window badge, and live operator messaging input.
    - `HandoffView`: Priority inbox for human intervention with auto-return trigger.
    - `ProductsView`: Searchable inventory catalog with Add modal and CSV import dry-run tester.
    - `OrdersView`: Order tracking and breakdown with CSV import.
    - `UsageView`: Analytics dashboard with KPI cards and model consumption breakdown.
    - `SettingsView`: Dynamic Webhook URL copy box, WhatsApp credentials with test button, AI provider key manager with test ping, and Neon database migration wizard.
  - Vite production build passing cleanly (`dist/`); ESLint passing with zero errors.
  - 84 automated tests passing across the backend.

---

## Phase 8: Hardening & Deploy ✅
- Security & Middleware:
  - `SecurityHeadersMiddleware` (`app/core/middleware.py`) injecting `X-Request-ID`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection`, `Referrer-Policy`, and conditional HSTS.
  - Automated tests in `tests/test_security_headers.py`.
- Management CLI additions:
  - `cleanup-retention --days <N> [--dry-run]` for purging historical messages, logs, and tool calls.
  - `delete-data --business-id <UUID> --customer-phone <PHONE> [--dry-run]` for GDPR/DPDP data privacy compliance.
  - Unit tests in `tests/test_cli.py`.
- Concurrency & Load Hardening:
  - Webhook burst stress testing script (`scripts/load_test_webhook.py`).
  - ASGI concurrent webhook burst test (`tests/test_load.py`) executing 20 concurrent signed requests without contention.
- Production Containerization & Proxy:
  - Multi-stage `apps/api/Dockerfile` with non-root `appuser`, forwarded proxy headers, and slim Python base.
  - Multi-stage `apps/web/Dockerfile` with Node build stage.
  - Production `Caddyfile` with automated Let's Encrypt / ZeroSSL TLS via `{$DOMAIN}`, Zstandard & Gzip compression, and SPA routing.
  - `docker-compose.dev.yml` for local hot-reload development.
- Documentation:
  - `docs/DEPLOY.md`: VPS setup, UFW firewall, Docker Compose launch, and Meta Webhook setup.
  - `docs/RUNBOOK.md`: Routine deployments, retention cron jobs, secret/key rotation, and Neon PITR recovery.
  - `docs/SECURITY.md`: Fernet encryption, Argon2id auth, HMAC-SHA256 verification, and multi-tenant isolation.
- Quality Gates:
  - 89 automated backend tests passing (`pytest -v`).
  - Ruff linter passing with 0 warnings (`ruff check .`).
  - ESLint passing with 0 errors (`npm run lint`).
  - Vite production build passing (`npm run build`).



