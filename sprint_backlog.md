# Closely AI - Sprint Backlog & Issue Tracker (V1.0)

This is the developer-facing sprint backlog and task tracker for the Closely AI MVP. It deconstructs the frozen design specifications into actionable tasks across 7 key epics. 

---

## Epic 1: Authentication & Organization Management
*Focus: Secure onboarding of merchant brands, user credentials, and brand-specific business policy configurations.*

- [x] **TSK-1.01: Database Tables for Organizations & Users**
  * **Description**: Create SQL models and migration scripts for `organizations` and `users`.
  * **Acceptance Criteria**: Organization holds details (ID, name, WhatsApp number, policies JSON). User holds (ID, organization_id, email, password_hash, role, name).
  * **Priority**: High

- [x] **TSK-1.02: User Registration Endpoint**
  * **Description**: Implement `POST /api/auth/register` to register a new tenant owner and their organization.
  * **Acceptance Criteria**: Validates email format, hashes password using bcrypt, prevents duplicate emails, returns registered user details.
  * **Priority**: High

- [x] **TSK-1.03: User Login & JWT Generation**
  * **Description**: Implement `POST /api/auth/login` to authenticate users and return a JWT access token.
  * **Acceptance Criteria**: Matches credentials, issues JWT containing user ID and organization ID, signs with `JWT_SECRET`, enforces expiration.
  * **Priority**: High

- [x] **TSK-1.04: JWT Authentication Middleware**
  * **Description**: Create dependency function `get_current_user` to secure API routes.
  * **Acceptance Criteria**: Decodes JWT, validates signature, retrieves user from database, raises 401 Unauthorized for expired/invalid tokens.
  * **Priority**: High

- [x] **TSK-1.05: Organization Details CRUD API**
  * **Description**: Implement endpoints `GET` and `PUT` at `/api/brand/settings` to manage tenant metadata.
  * **Acceptance Criteria**: Only authenticated users belonging to the organization can access or modify its profile.
  * **Priority**: Medium

- [x] **TSK-1.06: Business Policies Configuration API**
  * **Description**: Implement `PUT /api/brand/policies` to store return, shipping, and payment policy text blocks.
  * **Acceptance Criteria**: Validates JSON structure, stores text securely in Organization's `policies` column.
  * **Priority**: High

- [x] **TSK-1.07: Role-Based Access Control (RBAC)**
  * **Description**: Restrict specific settings endpoints to the `owner` role, blocking `staff` accounts.
  * **Acceptance Criteria**: Returns 403 Forbidden if a user with role `staff` attempts to modify organization configurations.
  * **Priority**: Low

- [x] **TSK-1.08: User List & Management API**
  * **Description**: Implement CRUD endpoints under `/api/brand/users` for managing additional staff accounts.
  * **Acceptance Criteria**: Owner can list, add, and revoke access for staff users under their organization.
  * **Priority**: Medium

- [x] **TSK-1.09: Auth & Org Unit Tests**
  * **Description**: Write pytest unit tests covering register, login, authorization headers, and policy updates.
  * **Acceptance Criteria**: Runs in test environment, tests pass successfully, uses mocked database.
  * **Priority**: High

---

## Epic 2: Multi-Tenancy & Database Foundation
*Focus: Secure logical partitioning of data across all database tables using tenant isolation query filters.*

- [x] **TSK-2.01: Alembic DB Migrations Setup**
  * **Description**: Initialize Alembic in the backend repository and map database schemas to historical migrations.
  * **Acceptance Criteria**: Running `alembic upgrade head` constructs the entire relational structure from scratch.
  * **Priority**: High

- [x] **TSK-2.02: Automatic Tenant Query Filtering in SQLAlchemy**
  * **Description**: Configure SQLAlchemy's query context to automatically inject `organization_id` filters for all read operations.
  * **Acceptance Criteria**: Prevents manual filter omissions; querying `db.query(Product).all()` as an authenticated tenant user only returns that tenant's products.
  * **Priority**: High

- [x] **TSK-2.03: Tenant Isolation Interceptor on Write Operations**
  * **Description**: Write event listeners or service layer wrappers that enforce the user's `organization_id` on all `insert`, `update`, and `delete` statements.
  * **Acceptance Criteria**: Raises an exception if a user tries to modify or associate a record to a different tenant's `organization_id`.
  * **Priority**: High

- [x] **TSK-2.04: Database Connection Pool Tuning**
  * **Description**: Configure PostgreSQL connection pooling parameters in SQLAlchemy (`pool_size`, `max_overflow`, `pool_recycle`).
  * **Acceptance Criteria**: Ensures connections are closed safely under high concurrency without leaking connections.
  * **Priority**: Medium

- [x] **TSK-2.05: Multi-Tenant Data Leak Integration Test**
  * **Description**: Write integration test simulating two concurrent tenant sessions.
  * **Acceptance Criteria**: Asserts that Tenant A cannot read or write Tenant B's data under any endpoint.
  * **Priority**: High

- [x] **TSK-2.06: DB Seed Scripts**
  * **Description**: Create utility scripts to populate initial seed organizations, users, and dummy catalogs.
  * **Acceptance Criteria**: Can be executed via command line for development and local testing.
  * **Priority**: Medium

---

## Epic 3: Catalog Ingestion & Management
*Focus: Bulk catalog uploads, metadata parsing, formatting validation, and vector embedding indexing.*

- [x] **TSK-3.01: CSV Schema Validator Engine**
  * **Description**: Build a validation parser that scans uploaded files for column headers and values.
  * **Acceptance Criteria**: Rejects CSVs missing `sku`, `name`, `price`, or `category`. Returns clear line-by-line feedback on formatting errors.
  * **Priority**: High

- [x] **TSK-3.02: Catalog CSV Upload Endpoint**
  * **Description**: Implement `POST /api/catalog/upload` accepting multipart file uploads.
  * **Acceptance Criteria**: Validates schema, processes rows, inserts categories and products, deletes old products or performs upserts based on SKU.
  * **Priority**: High

- [x] **TSK-3.03: Asynchronous Product Vector Indexing**
  * **Description**: Implement background embedding generation for products using Gemini `text-embedding-004`.
  * **Acceptance Criteria**: Ingested products are added to an embedding generation queue. pgvector column is updated with the 768-dimension vector.
  * **Priority**: High

- [x] **TSK-3.04: Product Search & Filter API**
  * **Description**: Implement `GET /api/catalog/products` with pagination and query parameters.
  * **Acceptance Criteria**: Filters by category, price range, color, size, and gender.
  * **Priority**: Medium

- [x] **TSK-3.05: Hybrid Product Retrieval Endpoint (Text + Vector)**
  * **Description**: Implement internal service function `retrieve_products` performing pgvector similarity search combined with SQL filtering.
  * **Acceptance Criteria**: Matches semantic meaning of queries (e.g. "red silk saree") and filters by size/price boundaries.
  * **Priority**: High

- [x] **TSK-3.06: Product Edit & Deletion APIs**
  * **Description**: Implement CRUD endpoints `PUT` and `DELETE` at `/api/catalog/products/{id}`.
  * **Acceptance Criteria**: Updates product parameters, updates embedding vector if text descriptions change, deletes record safely.
  * **Priority**: Medium

- [x] **TSK-3.07: Out-of-Stock and Inventory API**
  * **Description**: Implement inventory updates endpoint to change stock counts.
  * **Acceptance Criteria**: Modifying stock to 0 is instantly reflected in retrieval contexts to trigger stock guardrails.
  * **Priority**: High

- [x] **TSK-3.08: Ingestion & Vector Retrieval Unit Tests**
  * **Description**: Write unit tests for CSV ingestion, schema validation, and pgvector cosine similarity queries.
  * **Acceptance Criteria**: Mocks the Gemini embedding API to return deterministic vectors, validates correct product list ordering.
  * **Priority**: High

---

## Epic 4: AI & Conversation Pipeline
*Focus: Message processing state machine, NLU classification, structured entity extraction, context grounding, and response generation.*

- [x] **TSK-4.01: Asynchronous Conversation Message Handler Queue**
  * **Description**: Decouple webhook ingestion from processing. Webhook responds with `200 OK` instantly, and pushes message metadata to an execution queue.
  * **Acceptance Criteria**: Message processing runs in a non-blocking background context.
  * **Priority**: High

- [x] **TSK-4.02: Intent Engine Refactoring**
  * **Description**: Implement intent classification using Gemini 2.5 Flash.
  * **Acceptance Criteria**: Classifies inputs into `product_discovery`, `product_info`, `logistics`, `store_info`, `availability`, `human_negotiation`. Enforces structured JSON output.
  * **Priority**: High

- [x] **TSK-4.03: Entity Extractor Implementation**
  * **Description**: Extract size, color, budget boundaries, and fabric preferences using Pydantic schema constraints on Gemini.
  * **Acceptance Criteria**: Returns structured object (e.g. `{"size": "XL", "max_price": 2000}`).
  * **Priority**: High

- [x] **TSK-4.04: Deterministic Policy & Stock Guardrails**
  * **Description**: Write pre-response checking logic.
  * **Acceptance Criteria**: Overrides LLM output path if matching product has `price` missing, `stock_count` = 0, or if query hits policy boundaries.
  * **Priority**: High

- [x] **TSK-4.05: Context Builder (Catalog + Policies)**
  * **Description**: Retrieve history, products, and policies, formatting them into clear markdown text for the LLM system prompt.
  * **Acceptance Criteria**: Keeps prompt context window compact and handles missing attributes gracefully.
  * **Priority**: High

- [x] **TSK-4.06: Grounded Response Generator**
  * **Description**: Call Gemini 2.5 Flash with the grounded system prompt and conversation history.
  * **Acceptance Criteria**: Generates warm, brand-aligned responses. Restricts output to catalog facts.
  * **Priority**: High

- [x] **TSK-4.07: Safety & Formatting Validator**
  * **Description**: Create outbound validation checker to scan generated output before sending.
  * **Acceptance Criteria**: Blocks placeholders, filters toxic words, checks formatting, triggers fallback if check fails.
  * **Priority**: Medium

- [x] **TSK-4.08: Conversation Pipeline Integration Tests**
  * **Description**: Test the end-to-end pipeline execution from raw message to final reply.
  * **Acceptance Criteria**: Asserts correct intent routing and database state changes.
  * **Priority**: High

---

## Epic 5: WhatsApp Gateway & Webhooks
*Focus: Parsing incoming payloads, Meta webhook handshakes, signature verification, and outbound message dispatch.*

- [x] **TSK-5.01: Webhook Signature Verification Middleware**
  * **Description**: Validate Meta webhook payloads using the shared app secret hash.
  * **Acceptance Criteria**: Computes HMAC-SHA256 signature of request body and verifies it against the `X-Hub-Signature-256` header.
  * **Priority**: High

- [x] **TSK-5.02: WhatsApp Webhook Handshake Endpoint**
  * **Description**: Implement `GET /api/webhooks/whatsapp` verification endpoint.
  * **Acceptance Criteria**: Echoes `hub.challenge` if `hub.verify_token` matches the configured server environment variable.
  * **Priority**: High

- [x] **TSK-5.03: Payload Parsing & Standardization**
  * **Description**: Parse incoming messages from WhatsApp Cloud API, Twilio, and sandbox testing payloads.
  * **Acceptance Criteria**: Extracts phone number, sender name, message body, message type, and media links into a uniform JSON schema.
  * **Priority**: High

- [x] **TSK-5.04: Outbound WhatsApp Message Dispatcher**
  * **Description**: Build Meta Cloud API client using `httpx` to send text, template messages, and media.
  * **Acceptance Criteria**: Dispatches payloads asynchronously, reads access tokens from config, logs response status.
  * **Priority**: High

- [x] **TSK-5.05: Webhook Status Tracking (Delivered/Read)**
  * **Description**: Implement status update webhook parsing to log message delivery and read events.
  * **Acceptance Criteria**: Updates database record of messages with correct status flag (`sent`, `delivered`, `read`).
  * **Priority**: Low

- [x] **TSK-5.06: Rate Limiting & Outbound Retry Policy**
  * **Description**: Implement exponential backoff retry logic for outbound message dispatches.
  * **Acceptance Criteria**: Automatically retries on Meta rate limits (429 status codes), max retries set to 3.
  * **Priority**: Medium

- [x] **TSK-5.07: Media Download & Storage Service**
  * **Description**: Handle incoming media attachments (images/videos) from customers.
  * **Acceptance Criteria**: Fetches file from Meta media server, stores URL metadata in Message record.
  * **Priority**: Low

---

## Epic 6: Merchant Console & Human Takeover Dashboard
*Focus: Merchant-facing single page app for live conversation monitoring, inbox controls, catalog management, and takeover mechanics.*

- [x] **TSK-6.01: React Dashboard Scaffold & Routing**
  * **Description**: Set up the Vite + React workspace structure, install routing (react-router-dom) and styling configurations.
  * **Acceptance Criteria**: Creates standard layouts, layout navbar, sidebar, and page routing.
  * **Priority**: High

- [x] **TSK-6.02: JWT Authentication Pages (Login/Register)**
  * **Description**: Implement login and tenant onboarding forms.
  * **Acceptance Criteria**: Sends credentials to API, stores JWT token in LocalStorage, redirects to dashboard, handles auth errors.
  * **Priority**: High

- [x] **TSK-6.03: Conversation List Dashboard Component**
  * **Description**: Build live conversations panel showing customer names, phone numbers, last message text, and status tags.
  * **Acceptance Criteria**: Updates automatically, filters list by status (`ai_active`, `human_takeover`, `resolved`).
  * **Priority**: High

- [x] **TSK-6.04: Live Chat Interface (Inbox)**
  * **Description**: Build interactive messaging screen displaying message histories with bubbles color-coded by sender type.
  * **Acceptance Criteria**: Displays text and media correctly, scroll-to-bottom behavior, input text field for agents.
  * **Priority**: High

- [x] **TSK-6.05: Real-time Live Takeover Toggle Mechanism**
  * **Description**: Implement UI controls to toggle conversation status between AI control and manual control.
  * **Acceptance Criteria**: Clicking toggle sends status update to API, silences AI responses instantly, updates visual tag on screen.
  * **Priority**: High

- [x] **TSK-6.06: Catalog Management Interface**
  * **Description**: Build view to inspect current products, stock counts, and upload new CSV catalogs.
  * **Acceptance Criteria**: Shows table of items, file-upload field with drag-and-drop, displays CSV validation errors on-screen.
  * **Priority**: Medium

- [x] **TSK-6.07: Basic Analytics Dashboard View**
  * **Description**: Render metrics cards (Conversion Funnel, Human Takeover Rate, AI Resolution Rate) using charts (Recharts or custom CSS).
  * **Acceptance Criteria**: Displays counts fetched from API.
  * **Priority**: Medium

- [x] **TSK-6.08: Real-Time Event System (WebSockets/SSE)**
  * **Description**: Connect the UI to a real-time message stream (Server-Sent Events or WebSockets) for instant chat updates.
  * **Acceptance Criteria**: New messages show up in the chat window immediately without page reloading.
  * **Priority**: Medium

---

## Epic 7: Analytics, Operations & Deployment
*Focus: Container configurations, logging services, health check APIs, and deployment pipelines.*

- [x] **TSK-7.01: Health Check & Diagnostics API**
  * **Description**: Implement `/api/health` checking database connections, Redis status, and model API key configurations.
  * **Acceptance Criteria**: Returns `200 OK` if all services are reachable, returns `503 Service Unavailable` with details on failures.
  * **Priority**: High

- [x] **TSK-7.02: Operational Metrics Tracker (Technical)**
  * **Description**: Implement database logs for API latency, LLM response times, webhook processing time, and token usage.
  * **Acceptance Criteria**: Exposes structured JSON metrics in logs for Prometheus/Grafana or basic ingestion.
  * **Priority**: Medium

- [x] **TSK-7.03: Business Metrics Ingestion Engine**
  * **Description**: Track sales conversion funnels and revenue influenced in the Database.
  * **Acceptance Criteria**: Logs custom events when a user reaches a funnel stage or when a webhook payment is processed.
  * **Priority**: High

- [x] **TSK-7.04: Docker Compose Production Environment Configuration**
  * **Description**: Create production-grade docker-compose configuration separating state volumes, networks, and secure secret mounting.
  * **Acceptance Criteria**: Configures restart policies, logging limits, and spins up PostgreSQL, Redis, and FastAPI container nodes.
  * **Priority**: High

- [x] **TSK-7.05: API Rate-Limiter Engine**
  * **Description**: Deploy IP-based and token-based rate limiting on public facing endpoints (auth, webhooks) using Redis.
  * **Acceptance Criteria**: Rejects requests exceeding thresholds (e.g. 100 requests/minute) with a 429 status code.
  * **Priority**: Medium

- [x] **TSK-7.06: Webhook Payment Confirmation Webhook**
  * **Description**: Implement mock payment gateway endpoint `POST /api/webhooks/payments` simulating payment events.
  * **Acceptance Criteria**: Updates conversation funnel stage to "Paid" and log order value on webhook receipt.
  * **Priority**: High
