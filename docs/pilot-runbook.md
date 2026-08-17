# Milestone 4 – Merchant Pilot Staging Runbook

**Date:** 2026-08-14  
**Target Environment:** Staging / Controlled Pilot Sandbox  
**Classification:** Staging Operational Manual (Pre-Production)

---

## 1. Executive Summary & Operating Principles

This runbook defines the operational procedures for merchant onboarding, supervisor approval workflows, incident handling, emergency kill-switch activation, and manual reconciliation during the controlled staging pilot of the AI Sales Employee system.

### Core Operating Principles:
1. **Never Bypass the Approval Engine:** All high-risk proposals, discount requests exceeding policy thresholds, catalog exceptions, and refund inquiries must pass through the `WAITING_APPROVAL` workflow.
2. **Strict Multi-Tenant Isolation:** Every operation executes within an isolated PostgreSQL Row-Level Security (RLS) tenant boundary bound to `app.current_tenant`.
3. **Decoupled Outbox Dispatch:** Database locks are released and states are committed to `DISPATCHING` before initiating outbound network I/O with WhatsApp BSP providers.
4. **Fail-Safe Takeover:** Any unrecoverable provider timeout or rejection automatically shifts the conversation state to `HUMAN_TAKEOVER`.

---

## 2. Pre-Flight Checklist for Pilot Onboarding

Before enrolling a merchant organization into the staging pilot:

- [ ] **Organization Setup & Token Provisioning:**
  - Verify organization record in `organizations` table.
  - Configure WhatsApp Business Account ID (`whatsapp_business_account_id`), Phone Number ID (`whatsapp_phone_number_id`), and System User Token.
  - Set test webhook URL pointing to staging API: `https://staging-api.yourdomain.com/api/webhooks/whatsapp`.
- [ ] **Catalog Ingestion & Embedding Sync:**
  - Upload merchant product CSV via `/api/catalog/upload`.
  - Validate all product embeddings status are `completed` in `products` (`embedding_status = 'completed'`).
  - Verify zero discrepancies in SKU prices and initial `stock_count`.
- [ ] **Policy & Rule Tuning:**
  - Configure discount thresholds in `organizations.policies` (e.g., max auto discount `5%`, max owner discount `15%`).
  - Configure return/exchange windows, standard delivery timelines, and night delivery policies.
  - Set `emergency_kill_switch: false` in `organizations.policies`.
- [ ] **User Role Assignment:**
  - Designate at least one merchant `owner` and at least one `manager`/`staff` member.
  - Verify JWT authentication and BOLA role boundaries via `/api/auth/me`.

---

## 3. Approval Workflow Operations

### Approval Lifecycle Reference
```
[AI generates draft with risk/discount trigger]
                     │
                     ▼
             `WAITING_APPROVAL`
                     │
         ┌───────────┼───────────┐
         ▼           ▼           ▼
    [Approve]   [Edit & Send] [Reject / Takeover]
         │           │           │
         └─────┬─────┘           ▼
               │          `HUMAN_TAKEOVER`
               ▼          (Draft cancelled/silenced)
          `DISPATCHING`
               │
       ┌───────┴───────┐
       ▼               ▼
    [Success]     [Timeout / Err]
       │               │
       ▼               ▼
     `SENT`       `SEND_FAILED`
 (AI active)     (Escalates to HUMAN_TAKEOVER;
                  Outbox -> UNKNOWN_PROVIDER_OUTCOME / FAILED)
```

### Supervisor Approval Actions:
1. **Approve (`approve`):**
   - Live catalog facts (price/stock) are automatically revalidated against live SQL records.
   - SHA-256 message payload hash is calculated and stored.
   - Outbox record is created with monotonic version increment.
   - Outbound WhatsApp message is dispatched.
2. **Edit & Send (`edit_and_send`):**
   - Merchant edits draft message text directly in the dashboard.
   - New version number and SHA-256 hash are recorded.
   - Outbox dispatches edited text, updating audit trail.
3. **Reject (`reject`):**
   - Silences AI draft, marks approval as `REJECTED`.
   - Shifts conversation status immediately to `HUMAN_TAKEOVER`.
4. **Takeover (`takeover`):**
   - Merchant takes manual direct chat control over WhatsApp conversation.
   - AI draft marked `CANCELLED`.
5. **Snooze / Expire (`snooze` / `expire`):**
   - Marks request as `EXPIRED`. Stale drafts cannot be dispatched without re-generation.

---

## 4. Emergency Kill-Switch Protocol

If the AI generates anomalous responses, hallucinations, or catalog discrepancies during live merchant conversations:

### Step 1: Immediate Activation
Execute via Dashboard UI or API (Owner role required):
```http
POST /api/brand/kill-switch
Authorization: Bearer <OWNER_JWT_TOKEN>
Content-Type: application/json

{
  "active": true,
  "reason": "Suspected price hallucination on SKU-1049"
}
```

### Step 2: System Behavior Under Kill Switch
- All pending and in-flight approvals are blocked from dispatch.
- Calling `/api/approvals/{id}/respond` returns HTTP `400 Bad Request`:
  `"Emergency kill switch is currently active for this organization. Outbound dispatches are halted."`
- Audit log records `BLOCKED_BY_KILL_SWITCH`.
- Conversations default to `HUMAN_TAKEOVER` or manual staff handling.

### Step 3: Deactivation & Resumption
After root cause resolution:
```http
POST /api/brand/kill-switch
Authorization: Bearer <OWNER_JWT_TOKEN>
Content-Type: application/json

{
  "active": false,
  "reason": "Catalog corrected and verified"
}
```

---

## 5. Outbox Timeout Reconciliation Runbook

When network latency between our staging backend and WhatsApp BSP exceeds the timeout threshold (5 seconds):

1. **State Indicator:**
   - OutboundMessage status = `UNKNOWN_PROVIDER_OUTCOME`
   - ApprovalRequest status = `SEND_FAILED`
   - Conversation status = `HUMAN_TAKEOVER`
   - Audit action = `AMBIGUOUS_PROVIDER_OUTCOME` (`requires_reconciliation: true`)
2. **Operator Reconciliation Steps:**
   - Query pending ambiguous outbox records:
     ```sql
     SELECT id, approval_request_id, recipient_phone, provider_idempotency_key, created_at 
     FROM outbound_messages 
     WHERE status = 'UNKNOWN_PROVIDER_OUTCOME' 
     ORDER BY created_at DESC;
     ```
   - Check WhatsApp Business Manager or BSP portal for delivery of `provider_idempotency_key`.
   - If **Message Delivered:**
     ```sql
     UPDATE outbound_messages SET status = 'SENT', sent_at = NOW() WHERE id = '<OUTBOX_ID>';
     UPDATE approval_requests SET status = 'SENT', sent_at = NOW() WHERE id = '<APPROVAL_ID>';
     ```
   - If **Message Not Delivered:**
     - Contact customer directly via Human Takeover in dashboard.
     - Mark outbox message as `FAILED`:
       ```sql
       UPDATE outbound_messages SET status = 'FAILED', last_error = 'Reconciliation confirmed not delivered' WHERE id = '<OUTBOX_ID>';
       ```

---

## 6. Daily Staging Audit & Health Checks

1. **Check System Health:**
   - `GET /api/health/liveness` -> `{"status": "ok"}`
   - `GET /api/health/readiness` -> `{"status": "ready", "database": "connected", "redis": "connected"}`
2. **Review State Machine Consistency:**
   - Verify zero ApprovalRequests stuck in `DISPATCHING` > 5 minutes:
     ```sql
     SELECT id, organization_id, status, updated_at 
     FROM approval_requests 
     WHERE status = 'DISPATCHING' AND updated_at < NOW() - INTERVAL '5 minutes';
     ```
3. **Verify Audit Trail Integrity:**
   - Confirm all transitions have corresponding `approval_audit_logs` entries with valid `message_hash`.
