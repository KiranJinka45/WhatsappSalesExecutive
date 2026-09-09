# Case Study: Closely AI — Production Human-in-the-Loop AI Orchestration Engine

> **Role**: Forward-Deployed AI Engineer  
> **Core Architecture**: Deterministic SQL Grounding, PostgreSQL Row-Level Security (RLS), Pessimistic Approval Locks, Transactional Outbox Pattern, Network Reconciliation Engine  
> **Tech Stack**: FastAPI, PostgreSQL 16 (pgvector), SQLAlchemy Core, Redis 7, React 19, Vite, Docker, Meta WhatsApp Business Cloud API  

---

## 1. Executive Summary & Problem Statement

In retail e-commerce (such as apparel and luxury boutiques), deploying generative AI directly to customer-facing channels (e.g., WhatsApp) without safety guardrails is catastrophic:
1. **Hallucinated Prices & Phantom Stock**: LLMs hallucinate discounts, outdated pricing, or claim out-of-stock SKUs are available, creating legal and margin liability.
2. **Double-Dispatch & Network Timeouts**: Transient mobile network glitches cause duplicate webhook deliveries or lost outbound dispatches, annoying customers and inflating delivery costs.
3. **Multi-Tenant Data Leakage**: In SaaS architectures, one merchant seeing another brand's inventory or customer conversations is an existential security failure.

Closely AI was engineered not as a conversational chatbot, but as a **deterministic, fail-safe AI orchestration engine**. It combines semantic LLM reasoning with strict SQL facts, transactional outbox idempotency, and an atomic human approval layer.

---

## 2. Core Architectural Pillars

```
                     ┌─────────────────────────────────────────────────────┐
                     │            INBOUND META WHATSAPP WEBHOOK            │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                                    (HMAC-SHA256 Validated)
                                                ▼
                     ┌─────────────────────────────────────────────────────┐
                     │            AI CONVERSATION INTERPRETER              │
                     │  - Intent Extraction & Entity Resolution            │
                     │  - Hybrid Retrieval: pgvector + Full-Text Search    │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                                                ▼
                     ┌─────────────────────────────────────────────────────┐
                     │          DETERMINISTIC SQL EVIDENCE LAYER           │
                     │  - Ground Truth Price & Stock Snapshot              │
                     │  - Pessimistic Verification & Risk Scoring          │
                     └──────────────────────────┬──────────────────────────┘
                                                │
                     ┌──────────────────────────┴──────────────────────────┐
                     │                                                     │
        [Score < Threshold: Auto]                              [Score >= Threshold: Escalate]
                     │                                                     │
                     ▼                                                     ▼
        ┌──────────────────────────┐                         ┌───────────────────────────┐
        │   TRANSACTIONAL OUTBOX   │                         │    MERCHANT APPROVAL      │
        │ - Idempotency Key        │                         │          INBOX            │
        │ - SHA-256 Payload Hash   │                         │ - Real-Time SSE Stream    │
        │ - Atomic Outbound Insert │                         │ - SQL Evidence Display    │
        └────────────┬─────────────┘                         │ - Inline Draft Editor     │
                     │                                       └─────────────┬─────────────┘
                     │                                                     │
                     │                                           (Approve / Edit / Takeover)
                     │                                                     │
                     └──────────────────────┬──────────────────────────────┘
                                            │
                                            ▼
                     ┌─────────────────────────────────────────────────────┐
                     │                TRANSACTIONAL OUTBOX                 │
                     │ - Dispatched via Asynchronous Background Worker     │
                     │ - Provider Webhook Status Updates (Delivered/Read)  │
                     │ - Network Reconciliation Queue for Timeout Edges    │
                     └─────────────────────────────────────────────────────┘
```

### Pillar 1: Anti-Hallucination SQL Grounding Layer
- **The Problem**: LLMs generate plausible-sounding responses with incorrect numbers.
- **The Solution**: The LLM is **forbidden** from making assertions about price and inventory. A deterministic SQL query fetches live catalog facts and writes immutable `price_snapshot` and `stock_snapshot` JSONB payloads directly to the approval record.
- **Drift Revalidation**: Even after human approval, the engine revalidates live database records before dispatch. If a price changed or stock depleted while the merchant was reviewing, dispatch aborts.

### Pillar 2: Transactional Outbox Pattern & Cryptographic Hashing
- **The Problem**: Writing to the database and making an external HTTP call to Meta in the same request causes state inconsistency if the process crashes mid-flight.
- **The Solution**: An append-only `outbound_messages` table stores every pending dispatch inside the database transaction. A dedicated worker dispatches messages asynchronously with:
  - `provider_idempotency_key` preventing duplicate provider billing or multiple WhatsApp deliveries.
  - `payload_hash` (SHA-256) verifying that the transmitted message matches the exact bytes approved by the human merchant.

### Pillar 3: Tenant Row-Level Security (RLS) Isolation
- Every database query enforces tenant boundaries via PostgreSQL Session Variables (`app.current_tenant`).
- Policies are configured as **FAIL-CLOSED**: if `app.current_tenant` is empty or null, zero rows are returned across all tables (`products`, `conversations`, `approval_requests`, `outbound_messages`).

### Pillar 4: Dedicated Network Reconciliation Queue
- Transient network drops can leave outbound dispatches in an `UNKNOWN_PROVIDER_OUTCOME` state.
- Rather than hanging indefinitely or blind retrying (which causes duplicate customer messages), Closely AI isolates these messages into a dedicated **Reconciliation Queue**. Merchants can inspect provider audit logs, allow retries, or manually acknowledge delivery with audit trail tracking.

---

## 3. Video Demo Scripts (3x 60-Second Loom Recordings)

### Video 1: Human-in-the-Loop AI Orchestration & SQL Grounding (60s)
- **Target URL**: `http://localhost:3000` -> **Chats** view.
- **Script & Action Plan**:
  1. *(0:00 - 0:15)*: "Here is Closely AI running in real-time. In the WhatsApp Sandbox on the right, I'll simulate a customer inquiring: *'What is the price of the Kanjeevaram Silk Saree, and do you have it in stock?'*"
  2. *(0:15 - 0:35)*: "Instantly, the AI processes the message, extracts the intent, and flags it as requiring merchant approval. In the Approval Inbox, look at this green panel: **Deterministic SQL Evidence**. The AI is grounded by live database queries: SKU KNJ-01, ₹14,500, exactly 4 units in stock."
  3. *(0:35 - 0:50)*: "The merchant can review the proposed response, make inline edits, or click **✓ Approve & Send**. When clicked, our backend acquires a pessimistic database lock, verifies facts haven't drifted, cryptographically hashes the payload, and dispatches via our transactional outbox."
  4. *(0:50 - 1:00)*: "This completely eliminates hallucinated prices and phantom inventory."

### Video 2: Catalog Ingestion & Atomic PostgreSQL Upsert (60s)
- **Target URL**: `http://localhost:3000` -> **Catalog** view.
- **Script & Action Plan**:
  1. *(0:00 - 0:15)*: "Boutique merchants need to sync large inventory files frequently. Here is our Catalog Manager view."
  2. *(0:15 - 0:35)*: "I'm uploading an inventory CSV. Notice our ingestion modes: **Atomic (All or Nothing)** and **Partial**. Let's select Partial and upload."
  3. *(0:35 - 0:50)*: "Our backend utilizes native PostgreSQL `INSERT ... ON CONFLICT (organization_id, sku) DO UPDATE`. Instead of looping through thousands of ORM inserts, it executes a single bulk SQL statement. Watch the real-time summary card populate: Created, Updated, and Invalid Rows."
  4. *(0:50 - 1:00)*: "If a row contains negative prices or duplicate SKUs, strict Pydantic validation rejects it and reports the exact row number without corrupting the catalog."

### Video 3: Network Reconciliation Queue & Edge Case Resilience (60s)
- **Target URL**: `http://localhost:3000` -> **Outbox Queue** view.
- **Script & Action Plan**:
  1. *(0:00 - 0:20)*: "In distributed systems, networks fail. What happens when Meta's API times out during message dispatch? In naive architectures, you get duplicate messages or silent drops."
  2. *(0:20 - 0:40)*: "In Closely AI, timed-out dispatches transition into `UNKNOWN_PROVIDER_OUTCOME` and appear here in the **Outbox Reconciliation Queue**. You see the exact payload, the recipient, attempt counts, and the provider error trace."
  3. *(0:40 - 0:60)*: "The merchant can resolve the edge case with one click: **🔁 Allow Resend** resets the message to `PENDING` for safe worker retry, or **✓ Close Loop** marks it delivered once confirmed on the merchant's device, appending an immutable entry to our audit log."

---

## 4. Key Metrics & Engineering Milestones
- **Automated Tests**: 325+ passing tests across multi-tenant isolation, drift revalidation, outbox dispatch, and reconciliation.
- **P99 API Latency**: <120ms for approval verification and outbox dispatch.
- **Zero Hallucination Guarantee**: Fact verification enforced at the database transaction layer.
