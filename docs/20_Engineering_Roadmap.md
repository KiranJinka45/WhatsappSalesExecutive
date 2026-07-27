# Closely AI - Engineering & Release Roadmap

This document maps out the engineering path to pivot the current prototype into a production-grade retail conversational engine.

---

## Engineering Roadmap

```
[ Milestone 1: Specs ] ──► [ Milestone 2: Core Engine ] ──► [ Milestone 3: Integrations ] ──► [ Milestone 4: Moats ]
 (Completed)                   (2 Weeks)                       (2 Weeks)                       (3 Weeks)
```

---

## Milestones & Deliverables

### Milestone 1: Alignment & Core Specifications
* **Status**: Released
* **Goal**: Transition from pure architecture-centric prototype to a customer-conversion centered spec.
* **Deliverables**: Complete 20 product and architecture specifications defining the product blueprint.

---

### Milestone 2: Modular Pipeline & Database Schema Setup
* **Status**: Released
* **Goal**: Deconstruct the generic AI service into specialized components, deploy DB changes, and implement catalog validation.
* **Deliverables**:
  - Implement Alembic migrations to deploy `customer_memory`, `orders`, and lead scoring column updates to PostgreSQL.
  - Implement the **Catalog Validation Pipeline** to reject CSV files with missing prices, duplicate SKUs, or blank fabrics.
  - Refactor `ai_service.py` to separate `Intent Engine`, `Entity Extractor`, and `Policy Validator`.
  - Add deterministic validation rules for out-of-stock and price-missing items.

---

### Milestone 3: WhatsApp cloud API & Checkout Lifecycle
* **Status**: Released
* **Goal**: Move from simple text webhooks to interactive Meta Cloud API templates and Razorpay/Stripe checkout payments.
* **Deliverables**:
  - Build Meta Cloud API client supporting Multi-Product Messages (MPM catalog carousel lists).
  - Implement payment gateway links generator and webhook integration (`POST /api/webhooks/payments`).
  - Deploy Celery tasks to process outbound message queues and retry on rate limits.
  - Implement the **Conversational State Machine** (need discovery, checkout, payment, confirmation).

---

### Milestone 4: Customer Profiling, Visual Moat & Analytics
* **Status**: Released
* **Goal**: Implement the long-term customer preference store, visual search index, and dashboard charts.
* **Deliverables**:
  - Build the **Visual Similarity Search** engine using Gemini vision embeddings to process customer-uploaded style images.
  - Implement long-term customer preference profiles in `customer_memory` for personalization.
  - Implement analytics REST APIs for dashboard statistics (conversion funnel, revenue influenced).
  - Deploy recovery scheduler task to message customers with abandoned checkout items.

---

### Sprint 7: Customer Validation Sprint
* **Status**: Released
* **Goal**: Pivot focus to real-world customer validation and pilot execution.
* **Deliverables**:
  - Connect to the Meta Cloud API.
  - Onboard `merchant_real_01` with custom catalog configuration.
  - Ingest catalog and process 100+ real customer conversations.
  - Collect structured pre/post pilot feedback.
  - Generate evaluation scorecard and metrics.

---

### Sprint 8: Pilot Iteration
* **Status**: In Progress
* **Goal**: Lock down system architecture and harden the codebase based on active pilot observations.
* **Workflow**:
  - Zero new feature work or prompt refactoring.
  - Implement observer-driven fixes based on active pilot logs.
  - Enforce the bug remediation lifecycle:
    ```
    Pilot → Issue → Severity → Root Cause → Fix → Regression Test → Golden Added
    ```
  - **Rule**: Every bug fix must generate exactly **one automated regression test** and **one golden test data file** to prevent regression.

---

## Post-Pilot Technical Priorities
* **Status**: Planned

To scale the platform reliably beyond initial boutique pilots:

### A. Durable Asynchronous Jobs
* **Current State**: FastAPI `BackgroundTasks` processes outbound webhook queues and vector indexes. While acceptable for low-volume pilots, it is susceptible to message loss during server/process restarts.
* **V2 Target**: Migrate async tasks to **Celery** or **RQ** with a persistent queue backend (Redis/RabbitMQ) to ensure durable, retry-capable background executions.

### B. Recommendation Quality Tracking
* **Objective**: Track granular customer interaction metrics per recommendation to build a dataset for V2 ranking optimization:
  - `recommended`: Product SKU displayed.
  - `clicked`: Product card or link opened by customer.
  - `purchased`: Checkout link paid.
  - `merchant approved`: AI recommendation sent without changes.
  - `merchant rejected`: Takeover activated and recommendation overridden.
  - `reason`: Feedback category logged for rejections.

* **Database Replay Logging Schema**:
  To support offline model evaluation, fine-tuning, and full conversation replays, write the following fields to the feedback dataset:
  - `conversation_id`: Unique identifier for the customer chat.
  - `merchant_id`: Tenant identification code.
  - `customer_id`: Unique buyer identifier (phone hash).
  - `intent`: Active intent class parsed by the Intent Engine.
  - `entities`: JSON representation of parsed filters (budget, sizes, colors).
  - `retrieved_ids`: List of product IDs returned from vector semantic search.
  - `ranked_ids`: Ordered list of product IDs after Ranker sorting.
  - `shown_ids`: Exact product SKUs displayed to the shopper on WhatsApp.
  - `clicked_ids`: Product SKUs clicked/opened by the buyer.
  - `purchased_ids`: Product SKUs paid via checkout.
  - `feedback`: User thumbs up/down and text explanation.
  - `latency`: Pipeline processing duration in milliseconds.
  - `timestamp`: UTC execution time.
  - `model_version`: Active Gemini model version string.
  - `prompt_version`: Version string of the active system instructions block.

---

## MVP Architecture Freeze

> **Architecture Freeze Notice – Effective Immediately**
>
> The MVP architecture is now frozen.
>
> No new architectural layers, AI modules, database tables, or core APIs will be introduced unless justified by observed pilot evidence.
>
> Engineering effort is now directed toward customer validation, operational stability, merchant experience, and measurable business outcomes.


