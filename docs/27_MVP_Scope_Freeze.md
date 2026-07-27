# Closely AI - MVP Scope Freeze

This document freezes the MVP features list to prevent scope creep during the initial build cycle.

---

## 1. MVP Core Objective
To deliver a functional, secure, multi-tenant AI Sales Assistant on WhatsApp that parses merchant catalog uploads, answers user questions grounded strictly in catalog/policy context, generates checkout payment links, and provides a dashboard console for human agent takeover.

---

## 2. In-Scope Feature Set (Core MVP)

- **Tenant Authentication**: Register organization, register owner, log in to dashboard.
- **Catalog Ingestion**: CSV uploader with strict validation (rejects rows missing SKU, name, price, category, fabric, or stock counts).
- **Core Database Schemas**: Organizations, Users, Categories, Products, Conversations, Messages, Orders.
- **AI Processing Pipeline**:
  - Intent Classifier (classifies search, info, checkouts, and escalation requests).
  - Entity Extractor (extracts size, category, price boundaries).
  - Vector search indexing (pgvector cosine similarity).
  - Grounding validation (ensures facts are sourced strictly from catalog).
- **WhatsApp Webhook Gateway**: Ingestion of incoming text messages, verify webhook signatures.
- **Human Takeover Lifecycle**: Dashboard toggle switch, real-time alerts, silences automated replies on takeover.
- **Basic Merchant Inbox**: Viewing active conversations and sending manual replies.
- **Basic Analytics Dashboard**: Counter values for revenue influenced, AI-closed orders, and conversion stages.

---

## 3. Out-of-Scope (Deferred to Phase 2+)

- **Visual Similarity Search**: No parsing of images sent by customers (triggers support handoff).
- **Automated Cart-Recovery Notifications**: No Celery background scheduler task sending active outreach to shoppers.
- **Shopify / WooCommerce Direct Sync**: No external database polling; catalog management relies entirely on CSV uploads.
- **Multilingual OCR & Voice AI**: No voice messages processing or handwritten invoice scans.
- **Instagram / Facebook DM Integrations**: The system integrates solely with WhatsApp Business API webhooks.
- **Multi-Brand Catalog Aggregator**: Each store manages isolated, independent multi-tenant catalogs.
- **Marketing Automation / Campaigns**: No bulk message broadcast lists or promotion newsletters dispatch.

---

## 4. Architecture Freeze Agreement

> **Architecture Freeze Notice – Effective Immediately**
>
> The MVP architecture is now frozen.
>
> No new architectural layers, AI modules, database tables, or core APIs will be introduced unless justified by observed pilot evidence.
>
> Engineering effort is now directed toward customer validation, operational stability, merchant experience, and measurable business outcomes.

---

## 5. Version 1.0 Exit Criteria

Before transitioning from Pilot/Iteration to Public Beta, the product must satisfy the following qualitative and quantitative criteria:

### A. Technical Gates
* **CI/CD Integration**: Clean, passing automated build pipeline.
* **Test Suite**: All required CI gates pass.
* **Goldens**: AI evaluation regression tests and goldens pass with no drift.
* **Static Analysis**: Code checks (Ruff, Mypy) pass with zero errors.
* **Security & Vulnerabilities**: Dependency scan, secret scan, container image scan, and license compliance check are clean.

### B. AI Engine Gates
* **Intent Accuracy**: Target `> 90%` classification accuracy across test datasets.
* **Hallucination Rate**: No verified catalog or order fact discrepancies in release-blocking evaluation datasets and production pilot reviews:
  - `0` hallucinated catalog attributes.
  - `0` hallucinated prices.
  - `0` hallucinated inventory levels.
  - `0` fabricated order statuses.
* **Replay logs**: Successfully exported JSON/PDF templates verified.
* **Explainability**: AI Recommendation Inspector verified in the merchant dashboard.

### C. Product & Business Gates (Real Metrics)
* **Real Merchants**: $\ge 3$ active, non-synthetic merchants onboarded.
* **Conversation Corpus**: $\ge 500$ real customer conversations processed.
* **Merchant Satisfaction**: Average score of $> 8/10$ (Simulated evaluation: $9.2/10$).
* **AI Containment Rate**: Containment of $> 70\%$ of conversations without emergency handover.
* **Setup & Onboarding Time**: Average setup time $< 30$ minutes per merchant.

---

## 6. The 9-Phase Roadmap

```
[ Phase 1: Engineering ] ──► [ Phase 2: Architecture ] ──► [ Phase 3: AI Eval ] ──► [ Phase 4: Dashboard ]
      (Complete)                   (Complete)                  (Complete)             (Complete)
                                                                                          │
┌─────────────────────────────────────────────────────────────────────────────────────────┘
│
└──► [ Phase 5: Real Pilot ] ──► [ Phase 6: Pilot Learning ] ──► [ Phase 7: Design Partner ]
        (Active)
           │
┌──────────┘
│
└──► [ Phase 8: First Paying Customer ] ──► [ Phase 9: Public Beta ]
```

