# ADR 0004: PostgreSQL + pgvector for Catalog & Embeddings

## Context
Apparel commerce requires searching product databases across both structured criteria (sizing, pricing, brand tags) and unstructured semantic criteria (styling descriptions, customer prompts like "Show me wedding wear").

## Decision
Utilize a single **PostgreSQL** database with the **pgvector** extension.
* Store relational models (Organizations, Products, Orders) and search embeddings within the same database engine.
* Perform hybrid queries (combining SQL `WHERE` clauses with cosine distance vector lookups) in a single database round-trip.

## Alternatives Considered
* **Separate Vector Database (Pinecone/Qdrant) + Relational DB (Postgres)**: Rejected due to operational complexity, data synchronization lag, and high multi-tenant setup cost.

## Consequences
* High operational simplicity and transaction consistency.
* Easy schema migrations using standard SQL tools (Alembic).
* Index parameters (e.g. HNSW) must be configured directly within PostgreSQL.

## Status
Accepted
