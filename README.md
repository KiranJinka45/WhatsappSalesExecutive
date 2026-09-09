# Closely AI ⚡
### Production-Grade Human-in-the-Loop AI Sales Orchestration Engine

[![Python 3.12](https://img.shields.io/badge/Python-3.12+-3776AB.svg?style=flat&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16_pgvector-4169E1.svg?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org)
[![React 19](https://img.shields.io/badge/React-19.0-61DAFB.svg?style=flat&logo=react&logoColor=black)](https://react.dev)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg?style=flat&logo=docker&logoColor=white)](https://www.docker.com)
[![Tests](https://img.shields.io/badge/Tests-325+_Passing-10B981.svg?style=flat&logo=pytest&logoColor=white)](https://docs.pytest.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Closely AI** is an enterprise-grade AI sales orchestration platform designed for retail apparel boutiques and high-friction commerce environments. Unlike naive LLM chatbots that hallucinate prices and promise phantom inventory, Closely AI decouples natural language reasoning from deterministic database truth. 

It mathematically guarantees zero-hallucination pricing through immutable SQL snapshots, protects customer communication via a cryptographically hashed transactional outbox, and recovers from transient network drops via an operational reconciliation queue.

---

## 🏗️ System Architecture

```
                                  INBOUND META WHATSAPP WEBHOOK
                                                │
                                    (HMAC-SHA256 Validated)
                                                ▼
                                    ┌───────────────────────┐
                                    │ AI CONVERSATION ENGINE│
                                    │ - Intent Extraction   │
                                    │ - pgvector Search     │
                                    └───────────┬───────────┘
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │ DETERMINISTIC SQL     │
                                    │ EVIDENCE LAYER        │
                                    │ - Price Snapshot      │
                                    │ - Stock Snapshot      │
                                    └───────────┬───────────┘
                                                │
                         ┌──────────────────────┴──────────────────────┐
                         │                                             │
            [Risk < Threshold: Auto]                      [Risk >= Threshold: Escalate]
                         │                                             │
                         ▼                                             ▼
            ┌────────────────────────┐                    ┌─────────────────────────┐
            │  TRANSACTIONAL OUTBOX  │                    │     APPROVAL INBOX      │
            │  - Idempotency Key     │                    │  - Real-Time SSE Stream │
            │  - SHA-256 Hash        │                    │  - SQL Evidence Display │
            │  - Atomic Insert       │                    │  - Inline Draft Editor  │
            └────────────┬───────────┘                    └────────────┬────────────┘
                         │                                             │
                         │                                    (Approve / Edit / Takeover)
                         │                                             │
                         └──────────────────────┬──────────────────────┘
                                                │
                                                ▼
                                    ┌───────────────────────┐
                                    │  TRANSACTIONAL OUTBOX │
                                    │  - Redis Idempotency  │
                                    │  - Background Worker  │
                                    │  - Status Webhooks    │
                                    └───────────┬───────────┘
                                                │
                                (Transient Network Timeout?)
                                                ▼
                                    ┌───────────────────────┐
                                    │ RECONCILIATION QUEUE  │
                                    │ - UNKNOWN_OUTCOME     │
                                    │ - 1-Click Allow Retry │
                                    │ - Manual Delivery Ack │
                                    └───────────────────────┘
```

---

## 🛡️ Core Engineering Differentiators

### 1. Deterministic SQL Grounding (Anti-Hallucination Layer)
- **The Problem**: Language models frequently hallucinate discounts, outdated pricing, or claim out-of-stock SKUs are available, creating catastrophic legal liability.
- **The Solution**: The LLM is restricted from inventing catalog facts. A deterministic SQL query extracts live inventory data into immutable `price_snapshot` and `stock_snapshot` JSONB payloads.
- **Drift Revalidation**: Upon merchant approval, the backend executes a pessimistic database lock (`SELECT ... FOR UPDATE`) to revalidate live prices and stock. If inventory changed while the merchant was reviewing the draft, dispatch aborts cleanly.

### 2. Cryptographically Hashed Transactional Outbox
- **The Problem**: Issuing external HTTP requests to Meta's WhatsApp API inside the database transaction causes dual-write failures, race conditions, and duplicate billing on network drops.
- **The Solution**: Outbound messages are atomically committed to an append-only `outbound_messages` table inside PostgreSQL.
  - **SHA-256 Integrity Hash**: Confirms the exact bytes dispatched match what the human merchant approved.
  - **Provider Idempotency Key**: Prevents duplicate billing or double-dispatch during retries.

### 3. Dedicated Network Reconciliation Queue
- **The Problem**: Network timeouts during external API dispatches leave messages in an ambiguous state: did Meta receive the message or was it dropped before receipt? Blind retries result in duplicate customer messages.
- **The Solution**: Ambiguous dispatches transition to `UNKNOWN_PROVIDER_OUTCOME` and appear in the merchant's **Reconciliation Queue**. Merchants can audit provider error logs and execute one-click idempotent retries or manual delivery confirmations.

### 4. Database-Enforced Row-Level Security (RLS)
- Multi-tenant data isolation is enforced at the PostgreSQL engine level using session variables (`SET LOCAL app.current_tenant`).
- Policies are **FAIL-CLOSED**: unauthenticated or misconfigured queries return zero rows, eliminating application-level leakage vulnerabilities across merchants.

### 5. High-Throughput Bulk Catalog Ingestion
- Ingestion endpoint (`POST /api/catalog/import/csv`) accepts multi-thousand row CSVs.
- Uses native PostgreSQL `INSERT ... ON CONFLICT (organization_id, sku) DO UPDATE` bulk upsert semantics with Pydantic validation, processing thousands of rows in milliseconds with atomic rollback.

---

## 💻 Tech Stack

| Layer | Technologies | Purpose |
| :--- | :--- | :--- |
| **API Gateway** | Python 3.12, FastAPI, Pydantic v2 | High-concurrency async webhook reception & SSE streaming |
| **Database** | PostgreSQL 16, pgvector, SQLAlchemy Core | Relational data, RLS multi-tenancy, vector similarity search |
| **Caching & Queues** | Redis 7, Celery / ARQ background worker | Idempotency locks, outbox dispatch worker, kill-switches |
| **Frontend Dashboard** | React 19, Vite, CSS Modules, EventSource | Real-time Approval Inbox, Catalog Manager, Outbox Queue |
| **External APIs** | Meta WhatsApp Business Cloud API, Google Gemini | Inbound/outbound messaging, multi-modal semantic embeddings |
| **Infrastructure** | Docker Compose, Terraform, AWS ECS / RDS | Local container orchestration and cloud IaC blueprints |

---

## 🚀 Quickstart (Local Development)

### 1. Clone & Environment Setup
```bash
git clone https://github.com/your-username/closely-ai.git
cd closely-ai
cp .env.example .env
```

### 2. Launch Multi-Container Orchestration (Docker Compose)
Spins up PostgreSQL 16 (pgvector), Redis 7, FastAPI Backend, Celery Worker, and React Frontend:
```bash
docker-compose up --build
```
- **React Frontend**: `http://localhost:3000`
- **FastAPI API Docs**: `http://localhost:8005/docs`
- **Health Check**: `http://localhost:8005/health`

### 3. Run Test Suite
Run the 325+ integration test suite including RLS bypass tests, drift revalidation, and reconciliation:
```bash
# In backend directory or container
python -m pytest backend/tests/
```

---

## 📂 Repository Layout

```text
closely-ai/
├── backend/
│   ├── app/
│   │   ├── approval_service.py     # Pessimistic locking & drift revalidation
│   │   ├── catalog_service.py      # PostgreSQL ON CONFLICT bulk upsert engine
│   │   ├── outbox_dispatcher.py    # Transactional outbox & status webhooks
│   │   ├── routers/
│   │   │   ├── approvals.py        # Human-in-the-loop approval endpoints
│   │   │   ├── catalog.py          # CSV upload & product management
│   │   │   ├── outbox.py           # Reconciliation queue & retry endpoints
│   │   │   └── webhooks.py         # Meta WhatsApp webhook ingestion
│   │   ├── models.py               # SQLAlchemy ORM + RLS DDL triggers
│   │   └── database.py             # Tenant context & fail-closed engine
│   └── tests/                      # 325+ unit and integration tests
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Conversations.jsx   # Approval Inbox with SQL Evidence Panel
│   │   │   ├── Catalog.jsx         # CSV Ingestion Manager & error reporting
│   │   │   └── ReconciliationQueue.jsx # Outbox timeout management
│   │   └── App.jsx                 # Main navigation & lazy-loaded views
│   ├── Dockerfile                  # Multi-stage Nginx production build
│   └── nginx.conf                  # Reverse proxy with SSE streaming support
├── infrastructure/
│   └── terraform/                  # Production AWS ECS, RDS, and ElastiCache IaC
├── docs/                           # Architectural ADRs & Meta Onboarding guides
├── docker-compose.yml              # Unified multi-container local stack
└── PORTFOLIO_CASE_STUDY.md         # Technical case study & video demo scripts
```

---

## 📜 License
Distributed under the MIT License. See `LICENSE` for more information.
