# Closely AI - Architecture Decision Records (ADRs)

This document records the foundational architectural decisions made for the Closely AI platform, detailing context, decisions, alternatives, and consequences.

---

## ADR 01: Core Web Framework (FastAPI)
* **Decision**: Use FastAPI as the core backend web framework.
* **Status**: Accepted
* **Alternatives Considered**: Django (Django REST Framework), Flask.
* **Rationale**: 
  - **Asynchronous Execution**: FastAPI is built on ASGI (uvicorn/starlette), allowing asynchronous webhook handling. This prevents blocking during concurrent external API calls (e.g., Gemini API, Meta Cloud API).
  - **Type Safety**: Integrates Pydantic for request/response serialization, matching our strict catalog validation needs.
  - **Speed of Development**: Automatic OpenAPI (Swagger) documentation generation simplifies team alignment.
* **Consequences**: Fast response times for Webhooks. Requires async database drivers (e.g., `asyncpg`) or thread-pooled executors for synchronous DB code.

---

## ADR 02: Database & Vector Search (PostgreSQL + pgvector)
* **Decision**: Store structured metadata and vector search embeddings in a single PostgreSQL database using the `pgvector` extension.
* **Status**: Accepted
* **Alternatives Considered**: Separate Vector Database (Pinecone, Weaviate, Qdrant) + separate Relational DB (Postgres).
* **Rationale**:
  - **Operational Simplicity**: Avoids the architectural overhead of syncing data across two distinct database systems.
  - **Hybrid Querying**: Simplifies complex metadata filtering (e.g., color, size, price) blended with semantic search inside a single SQL query.
  - **Relational Consistency**: Direct foreign key relations between products, categories, orders, and vector tables.
* **Consequences**: Requires managing vector indexing parameters (like HNSW indices) directly in SQL. Heavy vector similarity queries may compete with operational transactions for CPU/Memory, requiring resource separation at scale.

---

## ADR 03: Session Store & Message Broker (Redis)
* **Decision**: Deploy Redis to handle transient conversation state caching, token rate limiting, and task broker queues.
* **Status**: Accepted
* **Alternatives Considered**: PostgreSQL for state + RabbitMQ for task queues.
* **Rationale**:
  - **Speed**: In-memory speeds are required to sustain a < 2-second WhatsApp response loop.
  - **Multi-functional**: Serves as both the Celery task broker and the transient cache for conversation states and vector results, reducing resource count.
* **Consequences**: Transient state is lost if Redis crashes (mitigated by configuring Redis AOF/RDB persistence). Core conversational history remains durable in PostgreSQL.

---

## ADR 04: Integration API Channel (Direct Meta Cloud API)
* **Decision**: Standardize integrations directly on Meta Cloud API instead of third-party Business Solution Provider (BSP) wrappers like Twilio.
* **Status**: Accepted
* **Alternatives Considered**: Twilio WhatsApp API, Gupshup.
* **Rationale**:
  - **Interactive Support**: Direct access to native WhatsApp UI formats (Multi-Product Messages, List Messages, interactive buttons) which are often delayed or limited on third-party wrappers.
  - **Cost Optimization**: Eliminates per-message markup fees charged by third-party wrappers.
* **Consequences**: Requires managing raw JSON webhook parsing and token storage directly in the application.

---

## ADR 05: AI Grounding Model (Retrieval-Augmented Generation - RAG)
* **Decision**: Ground the sales bot using RAG over the product catalog rather than fine-tuning an LLM.
* **Status**: Accepted
* **Alternatives Considered**: LLM Fine-tuning on brand catalog.
* **Rationale**:
  - **Real-Time Data**: Fine-tuning cannot handle real-time inventory count modifications or instant price edits.
  - **Fact Grounding**: RAG enforces deterministic grounding, preventing the bot from recommending non-existent items.
  - **Cost**: Eliminates expensive GPU training run fees.
* **Consequences**: Requires robust vector retrieval and chunk formatting rules in the pipeline to prevent context window bloat.

---

## ADR 06: Multi-Tenancy Architecture (Logical Column Partitioning)
* **Decision**: Implement multi-tenancy using an `organization_id` column on all tenant tables (Logical Partitioning) rather than physical Postgres Schemas.
* **Status**: Accepted
* **Alternatives Considered**: Schema-per-tenant, Database-per-tenant.
* **Rationale**:
  - **Low Overhead**: Simplifies connection pool sizing and migrations.
  - **Resource Sharing**: Faster onboarding of new self-serve boutiques.
* **Consequences**: Requires developer discipline to ensure all queries filter by `organization_id` to prevent cross-tenant data leaks. (Mitigated by implementing SQLAlchemy default query filters).

---

## ADR 07: Front-End UI Library (React + Vite)
* **Decision**: Build the merchant dashboard using React with Vite.
* **Status**: Accepted
* **Alternatives Considered**: Next.js, Vue.js.
* **Rationale**:
  - **Single Page Application (SPA)**: The merchant console is a heavy real-time tracking application rather than a public-facing website requiring SEO.
  - **Fast HMR**: Vite speeds up development loop significantly compared to webpack.
* **Consequences**: No server-side rendering (SSR), which is acceptable for a private operations console.
