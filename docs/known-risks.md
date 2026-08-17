# Milestone 4 – Known Risks & Mitigations

**Date:** 2026-08-16  
**Milestone Status:** Staging-Complete

---

## Risk Registry

### HIGH – Provider Outcome Ambiguity

**Risk:** When the WhatsApp BSP HTTP call times out (`httpx.TimeoutException`), we cannot determine whether the message was actually delivered.

**Current Mitigation:**
- Outbox status set to `UNKNOWN_PROVIDER_OUTCOME`
- Approval status set to `SEND_FAILED`
- Conversation escalated to `HUMAN_TAKEOVER`
- Audit log records `AMBIGUOUS_PROVIDER_OUTCOME` with `requires_reconciliation: true`

**Residual Risk:** No automated reconciliation worker exists yet. A human operator must manually check WhatsApp Business Manager or provider webhook callbacks to resolve ambiguous outcomes.

**Recommended Before Production:**
- Implement a reconciliation cron job that queries the WhatsApp Business API for message status by `provider_message_id`
- Add a dashboard view for `UNKNOWN_PROVIDER_OUTCOME` records

---

### HIGH – No Real WhatsApp Sandbox Testing

**Risk:** All tests use a mock BSP service. The actual WhatsApp Cloud API may behave differently (rate limits, error codes, webhook delivery timing).

**Current Mitigation:** Mock BSP faithfully simulates success, failure, and timeout paths.

**Residual Risk:** Unknown edge cases in the real provider API (e.g., partial delivery, webhook reordering).

**Recommended Before Production:**
- Run end-to-end staging test against WhatsApp sandbox with a real phone number
- Validate webhook signature verification with real payloads

---

### MEDIUM – Row Lock Contention Under Load

**Risk:** `with_for_update()` on ApprovalRequest serializes concurrent approvals for the same record. Under high concurrency, this could cause lock wait timeouts.

**Current Mitigation:**
- Lock scope is minimal (fetch + state check + status update)
- DB transaction commits before HTTP call (lock released before network I/O)
- Idempotency check prevents double-processing

**Residual Risk:** No load testing has been performed. Lock contention characteristics under real merchant traffic patterns are unknown.

**Recommended Before Production:**
- Run `locust` or `k6` load test simulating concurrent approval actions
- Set PostgreSQL `lock_timeout` to a safe ceiling (e.g., 5s)

---

### LOW – Database Superuser Privilege Escalation

**Risk:** PostgreSQL RLS policies are bypassed by the database superuser role.

**Current Mitigation:**
- Created dedicated non-superuser application role `closely_app`
- Granted least-privilege permissions depending on table type (standard `SELECT, INSERT, UPDATE, DELETE` on operational tables, but strictly `SELECT, INSERT` only on `approval_audit_logs` to ensure append-only status)
- Verified that `closely_app` cannot bypass RLS policies and cannot execute UPDATE or DELETE on audit logs

---

### MEDIUM – Kill Switch Race Window

**Risk:** A narrow TOCTOU (time-of-check-time-of-use) window exists between the kill switch check and the actual HTTP dispatch.

**Current Mitigation:**
- Kill switch is checked twice: once at entry, once immediately before DISPATCHING transition
- Both checks occur within the same transaction holding the row lock

**Residual Risk:** If the kill switch is activated between the second check and the HTTP call (after lock release), one message could slip through.

**Recommended Before Production:**
- Accept this as a known edge case (single-message slip on kill switch activation)
- The audit trail will record the slip for post-incident review

---

### LOW – Expiration Clock Skew

**Risk:** Expiration checks use `datetime.now(timezone.utc)`. Clock skew between application servers could cause inconsistent expiration behavior.

**Current Mitigation:** Single-server deployment eliminates clock skew.

**Residual Risk:** If horizontally scaled, NTP synchronization is required.

---

### LOW – Duplicate Operation ID Warning

**Risk:** FastAPI emits `UserWarning: Duplicate Operation ID delete_brand_profile_api_brand_profile_delete`. This does not affect runtime but could confuse OpenAPI consumers.

**Current Mitigation:** Warning is logged but does not block functionality.

**Recommended:** Rename one of the duplicate route functions in `brand.py`.

---

## Summary

| Risk Level | Count | Blocking for Staging? | Blocking for Production? |
|-----------|-------|-----------------------|--------------------------|
| HIGH | 2 | No | Yes |
| MEDIUM | 3 | No | Yes (load test, RLS role) |
| LOW | 2 | No | No |
