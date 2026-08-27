# WhatsApp Number Onboarding — Staging Checklist

This checklist defines the rigorous verification steps required prior to enabling WhatsApp number onboarding in staging and production.

---

## 1. Environment & Migration Prerequisites

- [ ] Staging PostgreSQL / Supabase instance active.
- [ ] Alembic migration `1d644d678b5e` (`add_whatsapp_onboarding_and_audit_logs`) applied.
- [ ] Database credentials verified for `closely_app` role.
- [ ] `META_API_VERSION` set to an approved version (`v20.0` or `v21.0`).
- [ ] Meta Developer Sandbox test number and whitelisted test recipient configured.

---

## 2. PostgreSQL Row-Level Security & Privilege Gates

- [ ] **RLS Verification:**
  - Execute `SELECT relrowsecurity, relforcerowsecurity FROM pg_class WHERE relname = 'whatsapp_onboarding_audit_logs';`
  - Assert both `relrowsecurity` and `relforcerowsecurity` return `TRUE`.
- [ ] **Policy Verification:**
  - Assert explicit `onboarding_audit_logs_tenant_select_policy` (FOR SELECT) and `onboarding_audit_logs_tenant_insert_policy` (FOR INSERT) exist.
  - Assert no broad `FOR ALL` policy exists.
- [ ] **Privilege Restrictions:**
  - Verify role `closely_app` has `SELECT` and `INSERT` grants.
  - Directly attempt `UPDATE` on `whatsapp_onboarding_audit_logs` using `closely_app` role → assert `42501 permission denied`.
  - Directly attempt `DELETE` on `whatsapp_onboarding_audit_logs` using `closely_app` role → assert `42501 permission denied`.
- [ ] **Cross-Tenant Isolation:**
  - Under `SET LOCAL app.current_tenant = '<tenant_a_uuid>'`, assert Tenant B audit rows return 0 results.

---

## 3. Staging Functional & Security Gates (Test Number Only)

- [ ] **Step 3.1: Connection Status Discovery**
  - Execute `GET /api/brand/whatsapp/connection-status`.
  - Verify sandbox test number (`+1 555...`) is flagged with `is_test_number: true`.
  - Verify UI shows developer sandbox warning.
  - Verify access tokens, WABA IDs, phone IDs, and PINs are completely absent from payload.

- [ ] **Step 3.2: Coexistence Detection Flow**
  - Simulate active Business App number response with coexistence capability.
  - Verify state transitions to `COEXISTENCE_FLOW_AVAILABLE`.
  - Verify UI displays official Meta Embedded Signup QR/confirmation guidance.
  - Verify no automated account deletion advice is given.

- [ ] **Step 3.3: Migration Required Flow**
  - Simulate account migration required response.
  - Verify state transitions to `BLOCKED_MIGRATION_REQUIRED`.
  - Verify UI displays Meta WhatsApp Manager official guidance.

- [ ] **Step 3.4: Rate Limiting & Cooldown**
  - Request code twice in under 5 minutes.
  - Assert second request returns `429 Too Many Requests`.

- [ ] **Step 3.5: Lockout Enforcement**
  - Submit 5 consecutive invalid codes.
  - Assert backend locks verification for 15 minutes (`423 Locked`).
  - Assert no verification codes are logged or stored.

- [ ] **Step 3.6: Server-Side Registration & Activation Gate**
  - Call `POST /api/brand/whatsapp/activate-live-number` with no request body.
  - Verify server generates 6-digit numeric PIN in ephemeral memory.
  - Verify registration POST is sent with `messaging_product: "whatsapp"`.
  - Verify authoritative status check from Meta (`id` match, `verified_name`).
  - Verify test number cannot be activated as live merchant number.
  - Assert zero PIN leakage in audit logs, database, response, or application logs.

- [ ] **Step 3.7: Owner-Only RBAC Gate**
  - Access mutation endpoints using `staff` role token → assert `403 Forbidden`.

---

## 4. Go / No-Go Decision Criteria

| Gate | Status | Blocker for Staging? | Blocker for Live Merchant? |
|---|---|---|---|
| 33/33 Unit, Security, BOLA, and RLS tests passing | ✅ PASSED | No | No |
| Frontend build passing (`0` errors) | ✅ PASSED | No | No |
| Staging PostgreSQL RLS & privilege verification | ✅ PASSED | No | No |
| Meta Embedded Signup SDK Integration (Full JS SDK) | ⏳ SPEC READY | No (Staging uses mock/sandbox) | **YES (Required for live self-serve)** |
| Somu Sekhar explicit approval | ⏳ PENDING | No | **YES (Do not connect without Somu present)** |
