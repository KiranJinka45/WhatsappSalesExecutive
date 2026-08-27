# WhatsApp Number Onboarding — Test Plan

## Test Matrix

| ID | Test | Category | Status |
|---|---|---|---|
| UT-01 | Request code SMS success | Unit | ✅ PASS |
| UT-02 | Request code VOICE success | Unit | ✅ PASS |
| UT-03 | Verify code success | Unit | ✅ PASS |
| UT-04 | Invalid verification code | Unit | ✅ PASS |
| UT-05 | Cooldown enforcement | Unit | ✅ PASS |
| UT-06 | Number active in WhatsApp Business app | Unit | ✅ PASS |
| UT-07 | Migration required error | Unit | ✅ PASS |
| UT-08 | Manual Meta action required | Unit | ✅ PASS |
| UT-09 | Meta configuration incomplete | Unit | ✅ PASS |
| UT-10 | Unexpected provider error | Unit | ✅ PASS |
| UT-11 | Verification attempt lockout (5 failures) | Unit | ✅ PASS |
| UT-12 | Activate live number with server-side PIN generation | Unit | ✅ PASS |
| UT-13 | Zero PIN leakage in audit logs after activation | Security | ✅ PASS |
| UT-13B | Activation Resource ID Mismatch Rejection | Unit | ✅ PASS |
| UT-13C | Blocked Sandbox Test Number Activation Rejection | Security | ✅ PASS |
| UT-14 | Coexistence flow detection | Unit | ✅ PASS |
| ST-01 | Zero code leakage (response, metadata, audit) | Security | ✅ PASS |
| ST-02 | No token exposure in status API | Security | ✅ PASS |
| ST-03 | Test number safeguard detection | Security | ✅ PASS |
| BOLA-08 | Onboarding connection status tenant isolation | Security | ✅ PASS |
| BOLA-09 | Onboarding mutation endpoints owner-only role security | Security | ✅ PASS |
| BOLA-10 | Onboarding audit logs RLS isolation | Security | ✅ PASS |
| BOLA-11 | Onboarding API zero secret leakage | Security | ✅ PASS |
| RLS-01 | RLS and FORCE RLS enabled on whatsapp_onboarding_audit_logs | Database Security | ✅ PASS |
| RLS-02 | Tenant SELECT and INSERT policies exist (no FOR ALL) | Database Security | ✅ PASS |
| RLS-03 | Tenant A cannot SELECT Tenant B audit rows under RLS | Database Security | ✅ PASS |
| RLS-04 | No-tenant context returns 0 rows | Database Security | ✅ PASS |

## Test Rules
- All unit and security tests use 100% mocked Meta Graph API responses.
- No real phone number, OTP, WABA credentials, or live token was used.
- Verification codes and registration PINs are never passed to audit log metadata or persisted.
- Registration PINs are verified in mock payload but never stored.
- Database tests run under real PostgreSQL RLS contexts (`SET LOCAL app.current_tenant`).
