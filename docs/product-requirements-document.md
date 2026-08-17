# Closely AI - Product Requirements Document (PRD)

> [!IMPORTANT]
> **MVP Scope Definition**: Version 1 is a **WhatsApp Catalog-Response Copilot** operating in **Shadow Mode** first, **Human-Approval Mode** second, and **Autonomous Mode** (for low-risk queries only) post-pilot.

---

## 1. Operating Modes & Funnel Architecture

Closely AI tracks conversation states and enforces human oversight through three distinct operating modes:

```
                  ┌──────────────────────────────────────────┐
                  │ 1. Inbound Customer WhatsApp Message     │
                  └────────────────────┬─────────────────────┘
                                       │
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │ 2. Intent Classification & Entity Parse │
                  └────────────────────┬─────────────────────┘
                                       │
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │ 3. Deterministic SQL/Catalog Search      │
                  └────────────────────┬─────────────────────┘
                                       │
                                       ▼
                  ┌──────────────────────────────────────────┐
                  │ 4. Policy Check & Draft Response Gen     │
                  └────────────────────┬─────────────────────┘
                                       │
           ┌───────────────────────────┴───────────────────────────┐
           ▼                                                       ▼
┌──────────────────────────┐                             ┌──────────────────────────┐
│ Exception / Bargaining   │                             │ Low-Risk Catalog Query   │
│ Status: WAITING_APPROVAL │                             │ Status: DRAFT_READY      │
└──────────┬───────────────┘                             └──────────┬───────────────┘
           │                                                        │
           ▼                                                        ▼
┌───────────────────────────────────────────────────────────────────────────────────┐
│ Merchant Dashboard Inbox: Human Staff Reviews, Edits, and Clicks "Approve & Send" │
└───────────────────────────────────────────────────────────────────────────────────┘
```

### Funnel Stages Tracked
1. **Inquiry / Discovery**: Customer asks for catalog items (e.g., *"Do you have silk sarees in red under ₹5,000?"*).
2. **Product Detail**: Customer requests price, fabric, size, or close-up details for a specific SKU.
3. **Availability & Stock**: Customer checks if an item is available for immediate purchase.
4. **Policy FAQ**: Customer inquires about shipping, delivery timelines, or return rules.
5. **Order Intent Collection**: Customer states intent to buy (*"I want to order SKU-1024"*). Copilot collects name, address, size, and passes to merchant for payment link dispatch.
6. **Exception & Escalation**: Customer asks for price discounts, custom tailoring, refunds, or reports a complaint. System halts automated replies and routes 100% to Human Takeover.

---

## 2. NLU Payload Schema & Validation Rules

Incoming WhatsApp messages pass through strict Pydantic parsing:

```json
{
  "intent": "product_search | product_info | stock_inquiry | store_faq | order_intent | discount_inquiry | refund | complaint | human_request | unknown",
  "entities": {
    "product_type": "saree | kurti | lehenga | dress | blouse",
    "color": ["red", "blue", "maroon", "gold", "green"],
    "size": ["S", "M", "L", "XL", "Free Size"],
    "fabric": ["silk", "cotton", "georgette", "linen"],
    "budget_max": 15000.0,
    "quantity": 1
  },
  "confidence": 0.96,
  "language": "en | te | hi",
  "script": "latin | telugu | devanagari"
}
```

### Schema Validation Rules
* If `confidence < 0.85` or `intent == "unknown"`, the copilot flags the message as `EXPLICIT_UNCERTAINTY` and presents a draft requesting clarification or routes to human takeover.
* All extracted numeric values (`budget_max`, `quantity`) are cast to explicit typed parameters before SQL query execution.

---

## 3. Deterministic Decision Engine Rulesets

To enforce safety, the Decision Engine applies strict rule checks:

### A. Grounding & Price Check Rule
- **Rule**: Generated draft prices MUST match the SQL database snapshot exactly.
- **Enforcement**: Uses deterministic validation to prevent unsupported price, stock, and policy claims. If a draft response contains a price discrepancy, it fails validation, triggers `GROUNDING_ERROR`, and requires human edit.

### B. Out-of-Stock Rule
- **Rule**: Items with `stock_count == 0` are flagged as unavailable.
- **Enforcement**: Copilot drafts: *"SKU-1024 is currently out of stock. Would you like to see similar sarees in maroon?"* (Never promises delivery of out-of-stock items).

### C. Discount & Bargaining Rule
- **Rule**: Discount queries or bargaining terms (e.g., *"Konchem thagginchandi"*) are strictly prohibited from receiving automated price reductions.
- **Enforcement**: Status immediately changes to `WAITING_APPROVAL`. The draft informs the customer that the manager will review the request, and alerts the merchant dashboard.

### D. Refund & Complaint Escalation Rule
- **Rule**: Intents matching `refund` or `complaint` are classified as high-risk.
- **Enforcement**: 100% escalation recall required. Status changes to `HUMAN_AGENT`, silencing automated draft sending until staff manually resolves the thread.

---

## 4. Acceptance Criteria & Quality Metrics

Rather than promising unverified absolute metrics, Version 1 adheres to precise quantitative acceptance criteria:

| Metric | Target | Verification Method |
|---|---|---|
| **Price Correctness** | **100%** | Deterministic SQL database cross-check on all generated drafts |
| **Stock Availability Correctness** | **100%** | SQL database stock count assertion |
| **Unsupported Product Claims** | **0** | Golden dataset RAG evaluation suite |
| **Escalation Recall (High-Risk Queries)** | **100%** | Automated test suite covering discounts, refunds, and complaints |
| **Intent Classification Accuracy** | **≥95%** | Benchmark test on initial golden dataset (`n=200`) |
| **Draft-Generation Latency (Simple Queries)** | **<3.0 seconds** | Telemetry from webhook arrival to draft ready in dashboard |
| **p95 Latency (Draft Generation)** | **<5.0 seconds** | Telemetry logs |

---

## 5. Governance, Privacy & Security Requirements

### A. Multi-Tenant Isolation & Authentication
* Tenant isolation enforced by RLS and verified through concurrency tests.
* Every database query MUST execute within an explicit transaction context setting `SET LOCAL app.current_tenant = '<org_id>'`.
* Unauthenticated requests are strictly restricted from executing database reads/writes without org resolution.

### B. Secret Management & Non-Disclosure
* No hardcoded tokens, API keys, or database credentials. All credentials managed via environment variables / Secret Manager.
* Logs MUST sanitize customer phone numbers, personal details, and security tokens.

### C. Data Privacy, Consent & Retention
* **Consent Logging**: Incoming customer messages store explicit opt-in timestamps for WhatsApp communication.
* **Data Deletion (Right to be Forgotten)**: API endpoint provided for merchants to purge customer chat history upon request.
* **Message Retention**: Raw customer chat logs purged after 90 days; anonymized metrics retained for telemetry.
* **Immutable Audit Trail**: All merchant draft edits, approvals, and AI decisions are stored in an append-only `decision_audit_logs` table.

---

## 6. Explicit Non-Goals for Version 1 MVP

1. No automated credit card, UPI, or Stripe payment link generation.
2. No automated processing of customer returns or monetary refunds.
3. No automated approval of price discounts or custom bargaining terms.
4. No multi-tenant cross-industry expansion in V1 (Apparel Retail only).
5. No visual image similarity search or multimodal matching in V1.
6. No claim of HIPAA, DISHA, SOC 2, KYC, or AML compliance until formally implemented and assessed.
