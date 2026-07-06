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
