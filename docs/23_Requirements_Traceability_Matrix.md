# Closely AI - Requirements Traceability Matrix (RTM)

This matrix maps each core MVP functional requirement to its implementation points in the codebase and verification test cases.

---

## Requirements Traceability Table

| Requirement ID & Description | API Endpoints | DB Tables / Schema | UI Merchant Console | Verification & Test Cases |
| :--- | :--- | :--- | :--- | :--- |
| **REQ-01: Organization Setup**<br>Register brand name, owner account, policies config. | `POST /api/auth/register`<br>`PUT /api/brand/settings` | `organizations`<br>`users` | Settings Form / Profile Management | `tests/auth_test.py`<br>(assert JWT, password crypt) |
| **REQ-02: Catalog Sync & Validate**<br>Upload CSV catalog, validate schemas, reject failures. | `POST /api/catalog/upload` | `products`<br>`categories`<br>`catalog_validation_reports` | Catalog Upload Panel (Drag & Drop) | `tests/catalog_service_test.py`<br>(assert duplicate SKU reject, missing price block) |
| **REQ-03: Webhook Ingestion**<br>Verify webhook signatures, log inbound text. | `POST /api/webhooks/whatsapp`<br>`GET /api/webhooks/whatsapp` | `conversations`<br>`messages` | Inbound chat feed (real-time WebSockets) | `tests/webhooks_test.py`<br>(verify signature verification, mock Twilio payload) |
| **REQ-04: Intent & Entity Extract**<br>Classify message intent, extract category/size. | Orchestrated in Webhook router lifecycle | `conversations.current_state`<br>`conversations.metadata` | Lead Score Dashboard details | `tests/ai_service_test.py`<br>(verify intent classifier output matches test cases) |
| **REQ-05: Catalog Search**<br>Query database using metadata filters + pgvector similarity. | `GET /api/catalog/products` | `products.embedding`<br>`products` | Product view list | `tests/rag_test.py`<br>(assert size matches, out-of-stock items dropped) |
| **REQ-06: Response Generator**<br>Generate grounded replies based on brand voice. | Orchestrated in Webhook router lifecycle | `messages` | Inbox conversation log | `tests/generator_test.py`<br>(run LLM judge validation on grounding scores) |
| **REQ-07: Human Takeover**<br>Toggle AI control, alert operators of escalations. | `POST /api/conversations/{id}/takeover`<br>`POST /api/conversations/{id}/resolve` | `conversations.status` | Takeover Toggle Button / Real-time Alert Banner | `tests/takeover_test.py`<br>(verify silent logging status when status=takeover) |
| **REQ-08: Analytics Dashboard**<br>Calculate conversions, recovery rates, revenue influenced. | `GET /api/analytics/dashboard` | `orders`<br>`conversations` | Analytics funnel chart, sales KPI counters | `tests/analytics_test.py`<br>(assert query math matches transaction history) |
