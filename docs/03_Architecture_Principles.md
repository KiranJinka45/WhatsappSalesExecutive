# Closely AI - Architecture Principles

*Status: **FROZEN** (Changes require clear production evidence demonstrating a platform-level limitation).*

---

## AI Workforce Architecture

```
                     Customer
                         │
              WhatsApp / Website / Instagram
                         │
                 Conversation Engine
                         │
              Context & Memory Layer
                         │
             Retrieval + Knowledge Base
                         │
               AI Reasoning Pipeline
                         │
           Deterministic Decision Engine
                  │                 │
          Autonomous         Approval Queue
                  │                 │
           Send Response      Merchant Review
                  │                 │
                 Customer ←──────────┘
```

---

## Platform Layers

To maintain code separation and security, the system is strictly organized into four layers:

### Layer 1 — SaaS Platform
Shared by every customer.
* Authentication, Organizations, Multi-tenancy, Billing, Audit Logs, and Analytics.

### Layer 2 — AI Platform
Reusable intelligence modules.
* Intent Classification, Memory, RAG Retrieval, Prompt Orchestration, Decision Engine, and Approval Queue.

### Layer 3 — Commerce Engine
Apparel-specific logic.
* Product Catalog, Inventory, Shipping Rules, Returns, Recommendations, and Checkout flows.

### Layer 4 — Merchant Knowledge
Private parameters belonging to each tenant.
* Store inventory, custom policy boundaries, store personality config, and catalog files.

*Rule*: Subsystems cannot bypass layers (e.g. SaaS UI communicating directly with Raw LLM state).

---

## Core Product Modules

* **Merchant Dashboard**: Direct catalog ingestion, onboarding setup, and the approval queue.
* **AI Sales Employee**: Chat parsing, context assembly, grounding checks, and response generation.
* **Human Approval System**: Intermediate queue intercepting risky messages to send alerts to merchants.

---

## Architecture Freeze Policy

The core platform will not be redesigned or re-architected due to speculative requirements or new ideas. Customer evidence outweighs theoretical improvements.

Changes to:
* **Multi-Tenancy isolation schemas**
* **Decision Engine logic rules**
* **Conversation lifecycle stages**
* **Approval workflow routing**
* **Audit system models**

require production telemetry or pilot logs showing a distinct structural limitation.

---

## Technology Strategy

* **Frontend**: Next.js, TypeScript, Tailwind CSS
* **Backend**: FastAPI, Python
* **Database**: PostgreSQL, pgvector (for semantic catalog matching)
* **Caching & Messaging**: Redis, Celery (for asynchronous webhook jobs)
* **AI Providers**: Model-agnostic layer (Gemini, Groq, OpenAI)
* **Deployment**: Docker, Linux (Kubernetes deferred until operational scale warrants it)

---

## Security Principles

* **Multi-Tenant Isolation**: Row-Level Security (RLS) or absolute database schema segmentation.
* **Audit Logging**: Every incoming query and outbound response is permanently logged.
* **Prompt Injection Protection**: Input sanitization and system prompt hardening.
* **Human Override**: Merchant can intervene to take control of any conversation at any time.
