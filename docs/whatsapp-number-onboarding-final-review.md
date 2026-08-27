# WhatsApp Number Onboarding — Final Review (Staging-Readiness Pass)

## 1. Executive Summary

This document confirms the completion of the staging-readiness security hardening pass for the official Meta WhatsApp Business Phone Number Onboarding flow in Closely AI.

---

## 2. Hardening Measures Implemented

### 2.1 Complete Removal of Browser PIN Input
- `POST /api/brand/whatsapp/activate-live-number` endpoint strictly takes an empty request body. No `pin` parameter is accepted via JSON, query params, or headers.
- Two-step verification PIN is generated server-side using `secrets.choice("0123456789")` in volatile process memory for the duration of the `POST /{phone_id}/register` call and immediately cleared (`pin = None`).
- Zero PIN leakage guaranteed across API responses, error messages, trace logs, database models, and audit records.

### 2.2 Authoritative Resource Readiness Evaluation
- `CONNECTED` state gate does not rely on generic strings. It verifies:
  1. Resource `id` from Meta matches stored `phone_number_id` (anti-BOLA).
  2. `verified_name` is present from Meta.
  3. `code_verification_status` is `VERIFIED`.
  4. Number is not a Meta developer sandbox number (`is_test_number == False`).
  5. Registration endpoint responded HTTP 200.
  6. Action was authorized by an authenticated tenant owner.

### 2.3 Explicit Graph API Version Allowlist Governance
- Replaced loose version comparison with explicit allowlist: `SUPPORTED_META_API_VERSIONS = {"v20.0", "v21.0", "v22.0"}`.
- Validated via `validate_meta_version()` before any Graph API interaction.
- Documented quarterly review cycle.

### 2.4 Staging Database RLS & Privilege Verification
- Migration `1d644d678b5e` (`add_whatsapp_onboarding_and_audit_logs.py`) verified:
  - `ALTER TABLE whatsapp_onboarding_audit_logs ENABLE ROW LEVEL SECURITY;`
  - `ALTER TABLE whatsapp_onboarding_audit_logs FORCE ROW LEVEL SECURITY;`
  - Explicit tenant `SELECT` and `INSERT` policies only (no broad `FOR ALL` policy).
  - Role `closely_app` granted `SELECT, INSERT` only; `UPDATE, DELETE` strictly revoked.
  - Cross-tenant test proves Tenant A cannot select Tenant B audit rows.

### 2.5 Dedicated Onboarding BOLA & Security Tests
- `test_08_onboarding_connection_status_tenant_isolation`: PASS.
- `test_09_onboarding_mutation_endpoints_role_security`: PASS (staff receives 403 Forbidden).
- `test_10_onboarding_audit_logs_rls_isolation`: PASS.
- `test_11_onboarding_api_response_zero_secret_leakage`: PASS.

---

## 3. Full Test Suite Results (33/33 Tests Passing)

```
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
collected 33 items

backend/tests/test_whatsapp_registration_service.py::test_request_code_sms_success PASSED [  3%]
backend/tests/test_whatsapp_registration_service.py::test_request_code_voice_success PASSED [  6%]
backend/tests/test_whatsapp_registration_service.py::test_verify_code_success PASSED [  9%]
backend/tests/test_whatsapp_registration_service.py::test_verify_code_invalid PASSED [ 12%]
backend/tests/test_whatsapp_registration_service.py::test_cooldown_enforcement PASSED [ 15%]
backend/tests/test_whatsapp_registration_service.py::test_number_active_in_app PASSED [ 18%]
backend/tests/test_whatsapp_registration_service.py::test_migration_required_error PASSED [ 21%]
backend/tests/test_whatsapp_registration_service.py::test_manual_meta_action_required PASSED [ 24%]
backend/tests/test_whatsapp_registration_service.py::test_meta_config_incomplete PASSED [ 27%]
backend/tests/test_whatsapp_registration_service.py::test_unexpected_provider_error PASSED [ 30%]
backend/tests/test_whatsapp_registration_service.py::test_verification_attempt_lockout PASSED [ 33%]
backend/tests/test_whatsapp_registration_service.py::test_activate_live_number_success PASSED [ 36%]
backend/tests/test_whatsapp_registration_service.py::test_activate_live_number_resource_mismatch PASSED [ 39%]
backend/tests/test_whatsapp_registration_service.py::test_activate_live_number_test_number_blocked PASSED [ 42%]
backend/tests/test_whatsapp_registration_service.py::test_coexistence_flow_detection PASSED [ 45%]
backend/tests/test_whatsapp_registration_service.py::test_security_zero_code_leakage PASSED [ 48%]
backend/tests/test_whatsapp_registration_service.py::test_security_no_token_exposure PASSED [ 51%]
backend/tests/test_whatsapp_registration_service.py::test_security_test_number_detection PASSED [ 54%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_01_bola_get_approval_detail_cross_tenant_denied PASSED [ 57%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_02_bola_respond_approval_cross_tenant_denied PASSED [ 60%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_03_bola_get_audit_trail_cross_tenant_denied PASSED [ 63%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_04_bola_unauthorized_role_approval_respond_forbidden PASSED [ 66%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_05_bola_unauthenticated_requests_unauthorized PASSED [ 69%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_06_kill_switch_role_security PASSED [ 72%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_07_outbound_messages_rls_isolation PASSED [ 75%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_08_onboarding_connection_status_tenant_isolation PASSED [ 78%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_09_onboarding_mutation_endpoints_role_security PASSED [ 81%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_10_onboarding_audit_logs_rls_isolation PASSED [ 84%]
backend/tests/test_08_bola_authorization.py::TestBOLAAuthorization::test_11_onboarding_api_response_zero_secret_leakage PASSED [ 87%]
backend/tests/test_staging_onboarding_rls_privileges.py::test_01_rls_and_force_rls_enabled PASSED [ 90%]
backend/tests/test_staging_onboarding_rls_privileges.py::test_02_tenant_select_insert_policies_exist PASSED [ 93%]
backend/tests/test_staging_onboarding_rls_privileges.py::test_03_tenant_isolation_under_rls PASSED [ 96%]
backend/tests/test_staging_onboarding_rls_privileges.py::test_04_no_tenant_context_returns_zero_rows PASSED [100%]

============================= 33 passed in 48.2s ==============================
```

---

## 4. Secret Scan Results

- `EAAG` token prefix: **0 occurrences** across repository.
- Hardcoded PIN patterns: **0 occurrences** (only `secrets.choice` generator).
- No real merchant number, OTP, or production credentials in code or test fixtures.

---

## 5. Decision & Recommendations

| Environment | Recommendation | Rationale |
|---|---|---|
| **Staging Environment** | **GO** | All 33 unit, BOLA, and PostgreSQL RLS tests passing cleanly; migration ready; frontend builds with 0 errors. |
| **Connecting Somu's Live Number** | **NO-GO** (for self-service endpoint) | Continue using official Meta Embedded Signup / WhatsApp Manager manually with Somu present. Do not use the self-service endpoint until the full frontend JS SDK Embedded Signup flow is implemented and Somu explicitly approves. |
