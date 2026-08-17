# Closely AI - Product Discovery Report

> [!IMPORTANT]
> **Core Strategic Principle**: Do not confuse a visually impressive prototype with a validated product. Product-market fit must be verified through empirical pilot metrics and customer willingness to pay before scaling.

---

## 1. Executive Summary
Closely AI is a **horizontal, multi-tenant conversational workforce platform** designed to provide specialized AI employees for customer communication, sales qualification, support, and workflow automation. 

To achieve speed-to-market and deep domain validation, Closely AI executes a focused **beachhead strategy in Apparel Retail**: a **WhatsApp Catalog-Response Copilot** built specifically for independent clothing boutiques and retail brand operators. By combining a **Deterministic Decision Engine** with generative language models, Closely AI **uses deterministic validation to prevent unsupported price, stock, and policy claims** while maintaining human approval control over exceptions, bargaining, and complaints.

---

## 2. Foundational Product Definition

### 1. Who is the customer?
* **Beachhead Customer (Apparel Retail)**: Independent silk saree and traditional apparel boutique owners (e.g., proposed pilot merchant *Pushpalatha Silks* in Dharmavaram or Kanchipuram) receiving 50+ inbound customer inquiries daily over WhatsApp.
* **Platform Customer (Long-term Vision)**: Department heads in Education, Real Estate, Healthcare, Fintech, and Banking requiring policy-governed AI agents.

### 2. What painful problem do they have?
* **Lead Drop-Off from Delayed Replies**: Shoppers on WhatsApp expect immediate responses (<2 minutes). When boutique staff are occupied with in-store customers, reply delays stretch to hours, leading to dropped buying intent.
* **Manual Catalog & Inventory Bottleneck**: Searching phone galleries or spreadsheets for matching SKUs, sizes, colors, and prices while typing individual chat responses is slow and error-prone.

### 3. How do they solve it today?
* Boutique owners and staff manually manage customer chats on personal smartphones, juggling physical store customers, gallery photos, and handwritten inventory logs.

### 4. Why will they pay?
* **Recovered Sales Revenue**: Faster catalog lookup and draft response generation during peak buying intent captures lost sales opportunities.
* **Operational Time Savings**: Saves 10+ hours per week of manual messaging, allowing staff to focus on in-store sales and fulfillment.

### 5. What is the smallest feature that proves value?
* **WhatsApp Catalog-Response Copilot**: An assistant that ingests CSV/Google Sheet inventory, retrieves verified product price and stock details, generates structured draft replies, and routes bargaining or policy exceptions to the merchant for approval.

---

## 3. Product Validation Hypotheses

Rather than stating unverified metrics as facts, Closely AI evaluates success against six explicitly testable hypotheses:

* **H1 (Inquiry Volume)**: At least 3 of 5 interviewed boutiques receive 50+ WhatsApp inquiries daily.
* **H2 (Response Latency Impact)**: At least 3 of 5 boutiques report that delayed replies directly cause lost or abandoned sales opportunities.
* **H3 (Response Latency Reduction)**: During the live pilot, Closely AI reduces median first-response time from the merchant's manual baseline to below 60 seconds (with human approval).
* **H4 (Deterministic Grounding Accuracy)**: In the approved test dataset, Closely AI returns correct price and availability for at least 99% of applicable queries.
* **H5 (Qualified Intent Capture)**: During the pilot, the merchant confirms that Closely AI increases qualified order intents compared with the baseline period.
* **H6 (Commercial Willingness to Pay)**: At least one merchant agrees to continue with a paid pilot after the 14-day trial.

---

## 4. Product Quality, Accuracy & Safety Framework

Generative language models cannot guarantee 100% natural-language accuracy. Closely AI enforces a multi-layered accuracy model:

```
Incoming Customer Query
      │
      ▼
Intent Classification & Entity Extraction
      │
      ▼
Deterministic DB Lookup (Price, Stock, SKUs) ──► [100% Rule Accuracy Required]
      │
      ▼
Tenant Policy Check (Discounts, Returns) ────────► [100% Policy Bounds Required]
      │
      ├── Exact Match & Policy Compliant ───────► Generate Draft Response
      ├── Low Confidence / Out of Stock ─────────► Express Explicit Uncertainty
      └── Bargaining / Refund / Complaint ────────► Escalate to Human Approval Queue
```

### Acceptance Targets
* **Price Correctness**: 100% in deterministic validation tests against the live database snapshot.
* **Stock Correctness**: 100% against the live database snapshot.
* **Unsupported Product Claims**: 0 hallucinated claims in the golden evaluation dataset.
* **Escalation Recall**: 100% escalation for defined high-risk scenarios (discounts, refunds, complaints).
* **Intent Classification Accuracy**: ≥95% on the initial golden evaluation set.
* **Draft-Generation Latency**: Median <3.0 seconds for cached/simple queries (measured from webhook intake to draft ready in dashboard).
* **p95 Latency**: Tracked separately for complex or human-approval flows.

---

## 5. Horizontal Platform Architecture vs. Vertical Modules

Closely AI cleanly separates reusable platform infrastructure from industry-specific domain modules:

### Horizontal Core (Reusable Infrastructure)
* **Tenancy & Isolation**: Multi-tenant database architecture with **tenant isolation enforced by RLS and verified through concurrency tests**.
* **Identity & Governance**: RBAC (Owner vs. Staff), JWT auth, zero secret leakage, audit logs.
* **Conversation Management**: Inbox, message store, status management (`AI_ACTIVE`, `WAITING_APPROVAL`, `HUMAN_AGENT`).
* **Deterministic Policy Engine**: Policy boundary checker, fallback rules, exception routing.
* **Human Approval Queue**: Web & notification interface for merchant review before dispatch.
* **Evaluations & Quality**: Golden dataset evals, draft-generation latency metrics, groundedness checks.

### Apparel Retail Domain Module (Version 1 Beachhead)
* **Domain Entities**: Products, SKUs, Categories, Sizes, Colors, Fabrics, Stock Counts, Images.
* **Workflows**: Catalog search, availability check, order intent collection, retail FAQ policies.

### Future Vertical Modules (Post-MVP Expansion)
* **Education & Admissions**: Course inquiries, student qualification, counselor scheduling.
* **Real Estate**: Property discovery, buyer qualification, site visit booking.
* **Healthcare (Future Scope)**: Service FAQs, appointment requests, staff confirmation. *Future scope subject to formal HIPAA/DISHA compliance implementation, PII encryption, zero medical advice generation.*
* **Fintech & Banking (Future Scope)**: Product FAQs, eligibility guidance, secure handoff. *Future scope subject to formal KYC/AML/SOC 2 compliance implementation and human credit decision locks.*

---

## 6. Explicit Non-Goals for Version 1 MVP

To prevent scope creep and ensure execution focus, the following capabilities are explicitly **OUT OF SCOPE** for Version 1:

1. **No Autonomous Payment Collection**: Payments remain offline/manual via merchant payment links.
2. **No Autonomous Refunds or Cancellations**: Refund queries must route 100% to human staff.
3. **No Autonomous Price Discounts**: Unapproved bargaining or price reduction requests route 100% to human staff.
4. **No Medical, Banking, Credit, or Financial Decisions**: Regulated industry logic is deferred to future releases.
5. **No Multi-Industry Implementation in V1**: Only Apparel Retail is active in Version 1.
6. **No Visual Multimodal Image Search**: Visual search is deferred to V2.

---

## 7. Pilot Execution & Progressive Rollout Modes

To eliminate operational risk, Version 1 deploys through three progressive operating modes:

1. **Mode 1: Shadow Mode (Days 1–3)**
   * System receives WhatsApp messages, executes retrieval and decision engine logic, and generates drafts in the background.
   * **Zero AI messages are sent to customers.** Staff responses are compared against AI drafts to calculate accuracy, intent recall, and identify edge cases.

2. **Mode 2: Human-Approval Mode (Days 4–14)**
   * System generates draft replies in real-time.
   * Merchant staff receive notifications, review drafts in the dashboard inbox, edit if needed, and click **Approve & Send**.

3. **Mode 3: Autonomous Mode for Low-Risk Queries (Post-Pilot Gate)**
   * Deployed only after proving 99%+ price/stock accuracy and 100% escalation recall in Stage 2.
   * Auto-responds ONLY to standard catalog availability and FAQ queries. All exception queries remain locked in Human-Approval mode.
