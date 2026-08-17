# Live Pilot Operational Runbook

**Date:** 2026-08-17  
**Document Version:** 1.2  
**Target Environment:** Limited Live Boutique Pilot (1 Merchant Only)  
**Mode:** Mandatory Merchant Approval (`HUMAN_APPROVAL` Mode Active)

---

## 1. Pilot Scope & Operational Boundaries

### Strict Operational Boundaries
- **Merchant Count:** Exactly 1 named pilot boutique. Multi-tenant onboarding is strictly disabled.
- **WhatsApp Sender Number:** Exactly 1 Meta-verified WhatsApp Business Account (WABA) phone number ID.
- **Allowed Roles:** 1 merchant owner account + 1 optional manager account.
- **Initial Approval Restriction:** Owner approval is **mandatory for the first 10 outbound messages** (manager approval is disabled for sends 1–10).
- **Autonomous Messaging:** **STRICTLY DISABLED**. Every outbound message requires explicit merchant review and approval.
- **Out of Scope (Forced Escalation to `HUMAN_TAKEOVER`):**
  - Payment links or processing
  - Refund or return requests
  - Unapproved price discounts or bargaining
  - Custom tailoring requests
  - Bulk order inquiries (> 10 items)
  - Customer complaints
- **Catalog Terminology & Truth Standard:**
  - **Tenant-scoped catalog retrieval and grounding:** PostgreSQL/SQL is the strict source of truth for all catalog facts (price, stock, SKU, availability).
  - Vector retrieval is used ONLY for semantic discovery or approved FAQ knowledge material, never as the factual source of price or inventory.

---

## 2. 12-Item Pre-Activation Checklist

### Part A: Human Operational Verification (Must be personally confirmed by human operators)
- [ ] **Item 1:** Written merchant pilot consent and data-retention agreement exist and are archived.
- [ ] **Item 2:** Merchant owner and manager training completed (review, edit, reject, takeover, kill switch, reconciliation, rollback).
- [ ] **Item 3:** Mobile dashboard usability verified with real merchant owner account on mobile viewport (touch targets ≥ 48px).

### Part B: Automated Code & System Verification
- [ ] **Item 4:** Runtime database identity is `closely_app` (non-superuser, RLS forced across 14 tables).
- [ ] **Item 5:** Alembic revision is `a2f4c9b0e8d1` (clean baseline chain, forward-only security policy).
- [ ] **Item 6:** Global default mode remains `SHADOW_MODE`.
- [ ] **Item 7:** `HUMAN_APPROVAL` is enabled ONLY for the named pilot tenant UUID.
- [ ] **Item 8:** Pilot tenant kill switch is **ON** during preflight validation.
- [ ] **Item 9:** Merchant owner performs test verification and manually turns kill switch **OFF** with reason: *"Authorized limited live pilot activation."*
- [ ] **Item 10:** System logs `KILL_SWITCH_DEACTIVATED` audit event with user ID, timestamp, reason, tenant ID, and audit event ID.
- [ ] **Item 11:** UI confirmation displayed stating that turning it OFF permits only owner-approved sends, never autonomous replies.
- [ ] **Item 12:** Programmatic evidence calculated and displayed per live send:
  - `approved_text_character_count` (`len(text)`)
  - `approved_text_utf8_byte_count` (`len(text.encode("utf-8"))`)
  - `content_sha256` (`hashlib.sha256(text.encode("utf-8")).hexdigest()`)
  - `message_version`, `outbox_id`, `provider_message_id_hash`, `audit_event_ids`.

---

## 3. Launch Sequence & First Live Message Verification

1. **Schedule Activation:** Conduct activation during staffed boutique operating hours with owner, merchant manager, and on-call engineer present.
2. **Owner Login & Readiness:** Confirm owner is logged into dashboard and WhatsApp, with ability to manually message customers if AI is paused.
3. **Preflight Inquiry (Kill Switch ON):**
   - Send one low-risk catalog test inquiry to the live pilot WhatsApp number.
   - Confirm draft state is `WAITING_APPROVAL`.
   - Confirm **0** outbound provider requests were initiated.
4. **Owner Kill Switch Deactivation:**
   - Owner manually toggles kill switch to **OFF** with reason: *"Authorized limited live pilot activation."*
   - Verify `KILL_SWITCH_DEACTIVATED` audit event is logged.
5. **First Live Message Verification:**
   - Display SKU, live price, stock count, message text, version, and SHA-256 hash.
   - Require a second explicit owner confirmation before sending.
   - Dispatch approved message.
   - Verify provider acceptance ("Provider accepted outbound message and returned a provider message ID"), outbox state `SENT`, approval state `SENT`, and complete audit trail.
   - If any check fails, immediately restore kill switch to **ON** and transition conversation to `HUMAN_TAKEOVER`.
6. **First 10 Messages Protocol:**
   - Keep messages 1–10 under owner-only approval. Monitor each send outcome and delivery status callback individually.

---

## 4. Stop Conditions & Immediate Response Protocol

### Stop Conditions (Zero Tolerance)
- Any unapproved outbound send
- Any duplicate customer message
- Any price or stock mismatch
- Any unknown provider outcome without immediate manual resolution
- Any cross-tenant / RLS / BOLA incident
- Any token, secret, or unredacted customer PII in logs
- Any kill-switch failure

### Emergency Response Procedure
1. **Toggle Kill Switch to ON** immediately in dashboard or via API.
2. **Stop all live outbound sends.**
3. **Transition active conversations to `HUMAN_TAKEOVER`.**
4. **Preserve sanitized audit evidence.**
5. **Notify merchant owner and engineering team.**
6. **Investigate using [`docs/live-pilot-rollback.md`](file:///c:/whatsapp_AI%20Sales%20Employee/docs/live-pilot-rollback.md).**
7. **Do NOT resume live sending without explicit corrective review and approval.**
