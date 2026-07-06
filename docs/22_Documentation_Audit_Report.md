# Closely AI - Documentation Audit Report (Version 0.9)

This audit report identifies inconsistencies, scope leaks, and design defects across the 20 generated product and architecture specifications (v0.9). It proposes resolutions to freeze the architecture before implementation.

---

## Audit Findings & Risk Categories

```
┌────────────────────────────────────────────────────────┐
│                   Audit Alert Summary                  │
├───────────────────────────────┬────────────────────────┤
│ Inconsistencies / Conflict   │ 3 Critical             │
│ Unrealistic MVP Scope         │ 2 High                 │
│ Gaps / Undefined Spec         │ 4 Medium               │
└───────────────────────────────┴────────────────────────┘
```

---

## 1. Critical Contradictions & Inconsistencies

### Finding C1: Discount Handling vs. Immediate Takeover
- **Source Files**: `01_PRD.md` (Stage 5), `08_Conversation_Flows.md` (State machine), `10_Sales_Playbook.md` (Objections), `backend/app/routers/webhooks.py`
- **Inconsistency**: 
  - `webhooks.py` and `01_PRD.md` immediately trigger a `human_takeover` when the NLU detects `human_negotiation` (which includes asking for discounts).
  - `10_Sales_Playbook.md` provides an AI script to handle discount requests (*"We don't do custom discounts, but you can use code FIRST10..."*).
  - **Result**: The AI playbook script will never execute because the conversation is handed over to a human before the generator runs.
- **Resolution**: Adjust the `Intent Engine` classification. Split `human_negotiation` into:
  1. `discount_inquiry`: AI attempts to offer standard active promo codes (playbook rules).
  2. `human_escalation`: Escalates directly when the user rejects the code, asks for wholesale pricing, or complains.

### Finding C2: Sizing Entity mismatch
- **Source Files**: `03_Database_Design.md` vs. `07_Prompt_Engineering.md`
- **Inconsistency**:
  - `03_Database_Design.md` defines sizes in the database as an array of strings: `sizes VARCHAR(50)[]`.
  - `07_Prompt_Engineering.md` extracts size as a single variable: `"size": "M"`.
  - **Result**: There is no schema definition mapping single size request constraints to complex multi-size configurations (e.g., European chest size 38 mapping to "M").
- **Resolution**: Define a lookup dictionary inside the `Recommendation Engine` configuration mapping numeric size inputs (e.g., 38, 40) to standard labels (S, M, L) before running the database query.

---

## 2. Unrealistic MVP Scope (Risk of Delay)

### Finding R1: Visual Similarity Search
- **Source Files**: `11_Product_Recommendation_Engine.md` (Section 3), `15_Deployment.md`
- **Risk**: Setting up multimodal vision vector indices and downloading binary images from Meta to feed into Gemini API introduces substantial latency (5s+) and development overhead (storing image embeddings, scaling vector dimensions).
- **Resolution**: **Defer to Phase 2.** For the MVP, if a user uploads an image, the system should trigger a `human_takeover` or respond: *"I can't look at photos yet, but you can describe what you're looking for, or our store staff will assist you shortly!"*

### Finding R2: Automatic Cart-Recovery Scheduler
- **Source Files**: `09_Customer_Journey.md`, `15_Deployment.md` (Celery setups)
- **Risk**: Running a background scheduler loop that evaluates cart states, formats templates, and sends outbound marketing messages requires complex opt-out tracking and increases API costs before product validation.
- **Resolution**: **Defer to Phase 2.** Focus the MVP solely on the *inbound sales loop* (User initiates, AI replies, user buys).

---

## 3. Gaps & Undefined Specifications

### Finding G1: Asynchronous Payment Confirmation
- **Source Files**: `04_API_Specification.md`, `08_Conversation_Flows.md`
- **Gap**: When a payment is completed, the Razorpay/Stripe webhook updates the database, but there is no mechanism to push the "Order Confirmed" WhatsApp message back to the customer automatically without an incoming message.
- **Resolution**: The payment webhook handler must invoke the `WhatsApp Sender` module asynchronously inside a Celery background task to dispatch the confirmation template directly using the stored `customer_phone`.

### Finding G2: Multi-Tenancy Data Leak Isolation
- **Source Files**: `03_Database_Design.md`, `21_Architecture_Decision_Record.md`
- **Gap**: Relies entirely on developer discipline to filter by `organization_id`. A single missed `filter()` call in SQLAlchemy can leak catalogs or customer conversations across brands.
- **Resolution**: Implement SQLAlchemy custom base queries or database-level row-level security (RLS) policies that automatically append `WHERE organization_id = current_org_id()` to all statements.

---

## 4. Phase 1 & 2 Execution Freeze Plan

### Phase 1: Core Architecture Freeze (MVP Core)
We freeze the following structures to lock the foundations:
- **Database Schema**: Organizations, Users, Categories, Products, Conversations, Messages, Orders (excluding `image_embedding` vector column).
- **API Contracts**: `/api/webhooks/whatsapp`, `/api/catalog/upload`, and `/api/auth`.
- **Orchestration**: Intent Engine (JSON schema output) -> Catalog Filter -> Generator -> Outbound Sender.

### Phase 2: MVP Feature Scope
We restrict implementation to this minimal loop:
1. Brand registers and configures general policies.
2. Brand uploads catalog (basic CSV schema validator).
3. Inbound user message classified (discovery, logistics, checkout, handoff).
4. Grounded response generated and sent using Gemini 2.5 Flash.
5. In-chat manual takeover option.
