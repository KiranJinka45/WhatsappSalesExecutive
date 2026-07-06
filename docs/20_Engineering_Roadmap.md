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

### Milestone 1: Alignment & Core Specifications (Completed)
- **Goal**: Transition from pure architecture-centric prototype to a customer-conversion centered spec.
- **Deliverables**: Complete 20 product and architecture specifications defining the product blueprint.

---

### Milestone 2: Modular Pipeline & Database Schema Setup (Est: 2 Weeks)
- **Goal**: Deconstruct the generic AI service into specialized components, deploy DB changes, and implement catalog validation.
- **Deliverables**:
  - Implement Alembic migrations to deploy `customer_memory`, `orders`, and lead scoring column updates to PostgreSQL.
  - Implement the **Catalog Validation Pipeline** to reject CSV files with missing prices, duplicate SKUs, or blank fabrics.
  - Refactor `ai_service.py` to separate `Intent Engine`, `Entity Extractor`, and `Policy Validator`.
  - Add deterministic validation rules for out-of-stock and price-missing items.

---

### Milestone 3: WhatsApp cloud API & Checkout Lifecycle (Est: 2 Weeks)
- **Goal**: Move from simple text webhooks to interactive Meta Cloud API templates and Razorpay/Stripe checkout payments.
- **Deliverables**:
  - Build Meta Cloud API client supporting Multi-Product Messages (MPM catalog carousel lists).
  - Implement payment gateway links generator and webhook integration (`POST /api/webhooks/payments`).
  - Deploy Celery tasks to process outbound message queues and retry on rate limits.
  - Implement the **Conversational State Machine** (need discovery, checkout, payment, confirmation).

---

### Milestone 4: Customer Profiling, Visual Moat & Analytics (Est: 3 Weeks)
- **Goal**: Implement the long-term customer preference store, visual search index, and dashboard charts.
- **Deliverables**:
  - Build the **Visual Similarity Search** engine using Gemini vision embeddings to process customer-uploaded style images.
  - Implement long-term customer preference profiles in `customer_memory` for personalization.
  - Implement analytics REST APIs for dashboard statistics (conversion funnel, revenue influenced).
  - Deploy recovery scheduler task to message customers with abandoned checkout items.
