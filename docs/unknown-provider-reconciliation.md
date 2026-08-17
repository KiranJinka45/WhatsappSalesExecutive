# Unknown Provider Outcome Reconciliation Guide

**Date:** 2026-08-16  
**Document Version:** 1.1  
**Target Environment:** Limited Live Boutique Pilot & Staging Operations

---

## 1. Core Principles & Idempotency Rules

When an outbound HTTP call to the WhatsApp Business Service Provider (BSP) times out or experiences an unconfirmed network drop:
1. **Outbox State:** Set to `UNKNOWN_PROVIDER_OUTCOME`.
2. **Approval Request State:** Set to `SEND_FAILED`.
3. **Conversation State:** Escalated immediately to `HUMAN_TAKEOVER`.
4. **STRICT PROHIBITION:** **NO AUTOMATIC RETRIES AND NO "RESEND" BUTTON**.
   - Resending automatically risks delivering duplicate messages to the customer if Meta actually accepted the payload.
5. **Internal Idempotency Key:** `provider_idempotency_key` is preserved strictly as an internal outbox correlation ID. Do NOT attempt to query Meta Graph API using internal idempotency keys (Meta WhatsApp Cloud API does not support status lookup by internal idempotency keys).

---

## 2. Documented Reconciliation Sources

Operators must reconcile ambiguous outcomes using official provider mechanisms:
- Documented Meta provider message IDs (`wamid....`)
- Delivery status webhooks (`sent`, `delivered`, `read`, `failed`)
- Official Meta WhatsApp Business Manager dashboard logs
- Customer's actual WhatsApp conversation thread

---

## 3. Operator Manual Reconciliation Workflow

When an item appears in the reconciliation queue:

### Step 1: Manual Verification Without Resending
If no provider message ID was returned before the timeout:
1. Operator inspects the Meta WhatsApp Business Manager messaging log or customer conversation thread.
2. Checks whether the message text was delivered to the customer.

### Step 2: Select Reconciliation Action

The reconciliation UI offers strictly 4 safe, manual actions (with NO resend option):

| Action | Action Taken | Result |
|---|---|---|
| **1. Mark Confirmed Sent** | Operator confirms message delivered in Meta Manager | `outbound_messages.status = 'RECONCILED_SENT'`; Audit logged `RECONCILED_CONFIRMED_SENT`. |
| **2. Mark Confirmed Failed** | Operator confirms message was not received | `outbound_messages.status = 'RECONCILED_FAILED'`; Merchant can manually reply in `HUMAN_TAKEOVER`. |
| **3. Add Reconciliation Note** | Operator enters investigation details | Audit logged `RECONCILIATION_NOTE_ADDED` with operator ID & note. |
| **4. Open Human-Takeover Conv** | Opens direct chat window for merchant | Merchant communicates directly with customer. |

---

## 4. Audit Trail Completeness

Every reconciliation action writes an append-only audit event to `approval_audit_logs` capturing operator ID, timestamp, outcome, and justification note.
