# Closely AI - Project Glossary

This document defines core product, business, engineering, and AI terminology used across the Closely AI specifications.

---

## Glossary Definitions

* **Average Order Value (AOV)**: Retail metric calculated by dividing total revenue by the number of orders.
* **Business Solution Provider (BSP)**: Upstream companies (e.g., Twilio, Gupshup) that intermediate access to Meta's WhatsApp Business API infrastructure.
* **Customer Memory**: Long-term database state storing customer sizing profiles, fabric preferences, color preferences, and purchasing history.
* **Definition of Done (DoD)**: A set of strict quality checkpoints that a developer must pass before a feature branch is merged to production.
* **Grounding**: The technique of restricting an LLM's answers strictly to factual documents (catalog and policies) passed in the prompt context.
* **HNSW (Hierarchical Navigable Small World)**: An index structure in pgvector that speeds up high-dimensional vector similarity searches.
* **Human Takeover / Handoff**: The process of pausing automated AI conversation loops to let human store staff respond manually.
* **Lead Score**: A real-time probability rating (0.0 to 1.0) assessing a customer's likelihood of completing a purchase based on chat actions.
* **Multi-Product Message (MPM)**: A native WhatsApp interactive UI layout that displays a catalog carousel of up to 30 products.
* **Multi-Tenancy**: Software architecture where a single instance of the application serves multiple brands (tenants), keeping data isolated.
* **pgvector**: A PostgreSQL extension that stores vector embeddings (e.g. from Gemini) and runs fast cosine distance query similarity matches.
* **Retrieval-Augmented Generation (RAG)**: An AI architecture that fetches matching database files (the catalog) and injects them into the prompt before generating the final reply.
