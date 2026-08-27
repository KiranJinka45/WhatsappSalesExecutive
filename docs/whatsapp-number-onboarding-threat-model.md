# WhatsApp Number Onboarding — Threat Model

## Overview
Security threat matrix for the WhatsApp Business phone-number onboarding feature in Closely AI.

---

## T1: Verification Code Theft
- **Threat:** An attacker intercepts or brute-forces the SMS/voice verification code.
- **Mitigation:** Codes are handled in transient memory only. Never stored in DB, audit logs, API responses, or browser storage. 5-attempt lockout with 15-minute cooldown. `autoComplete="off"` on input.

## T2: Registration PIN Leakage
- **Threat:** The 6-digit two-step verification PIN used in `POST /register` is exposed.
- **Mitigation:** PIN is generated cryptographically via `secrets.choice()`. Never stored in DB, logs, or audit metadata. Sanitization filter in `_log_audit_event` explicitly strips `pin`, `code`, `access_token` keys.

## T3: BOLA / Resource ID Swapping
- **Threat:** Attacker substitutes another tenant's WABA ID or Phone Number ID.
- **Mitigation:** All resource IDs are resolved from the authenticated tenant's database session, never accepted from frontend request body. Tenant-scoped RLS on all queries.

## T4: Toll Fraud / SMS Pumping
- **Threat:** Attacker triggers excessive SMS code requests to run up costs.
- **Mitigation:** Local 5-minute cooldown between requests. Provider `Retry-After` header honored when available. Separate local abuse-control cooldown documented distinctly from Meta's own rate limits.

## T5: Test Number Misidentification
- **Threat:** A Meta sandbox test number (e.g., +1 555...) is accidentally treated as a live merchant number.
- **Mitigation:** `_is_test_number()` detects known sandbox patterns. Test numbers are flagged with `META_TEST_NUMBER_CONNECTED` state and cannot be promoted to live.

## T6: Token Leakage
- **Threat:** Meta access tokens appear in API responses, frontend, or logs.
- **Mitigation:** `get_connection_status()` never includes token fields. Audit log sanitization strips `access_token`, `waba_id`, `phone_number_id` keys.

## T7: Unauthorized Role Access
- **Threat:** A staff-role user triggers verification or activation endpoints.
- **Mitigation:** All mutation endpoints require `owner` role via `require_role("owner")` middleware.

## T8: Automatic Number Alteration
- **Threat:** The system auto-deletes, migrates, or deregisters a merchant's existing number.
- **Mitigation:** No endpoint or service function performs deletion, migration, or deregistration. Coexistence flow routes to Meta's own UI. Manual migration guidance never defaults to "delete your account."

## T9: Stale Graph API Version
- **Threat:** Configured `META_API_VERSION` becomes deprecated, causing silent failures.
- **Mitigation:** `validate_meta_version()` checks at activation time that the version is >= v19.0. Version is configurable but validated.
