# WhatsApp Number Onboarding — Design & State Machine

## 1. Overview

This document specifies the safe, official Meta WhatsApp Business phone-number onboarding architecture for Closely AI.

The design implements:
1. **Server-Side-Only PIN Generation:** Two-step verification PIN is generated using cryptographically secure server-side randomness (`secrets.choice`). The browser/frontend is strictly prohibited from providing, inspecting, or receiving registration PINs.
2. **Authoritative Resource Readiness Gate:** `CONNECTED` state is reached only after verifying exact Meta Cloud API response fields (`id` match, `verified_name`, `code_verification_status`, non-test-number validation, and tenant WABA token ownership).
3. **Graph API Version Governance:** Replaces loose version inequality with an explicit deployment allowlist (`v20.0`, `v21.0`, `v22.0`).
4. **Official Coexistence Support:** Routes eligible WhatsApp Business mobile app users to Meta's Embedded Signup coexistence flow without advising account deletion.
5. **Database RLS & Immutability:** `whatsapp_onboarding_audit_logs` protected by Row-Level Security with `SELECT` and `INSERT` privileges only; `UPDATE` and `DELETE` strictly revoked for `closely_app`.

---

## 2. Onboarding Path Routing

```
                             [ Merchant Initiates Onboarding ]
                                            │
                                            ▼
                          [ Check Number & Account State ]
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               ▼                            ▼                            ▼
      [ Path A: New Number ]     [ Path B: Business App ]    [ Path C: Migration Required ]
               │                 (Coexistence Available)                 │
               ▼                            │                            ▼
    Meta Embedded Signup                    ▼                   Show WhatsApp Manager
    Verifies Number via OTP      Meta QR/App Confirmation       Official Migration Guidance
               │                 (No Account Deletion)                   │
               ▼                            │                            ▼
     Backend Token Exchange                 ▼                  Merchant Completes Action
               │                  Backend Validates WABA        in Meta Business Suite
               ▼                            │                            │
  Server Generates 6-Digit PIN              ▼                            ▼
  & Calls POST /{id}/register    Authoritative Status Confirmed  Authoritative Status Confirmed
               │                            │                            │
               └────────────────────────────┼────────────────────────────┘
                                            ▼
                               [ Authoritative Readiness Gate ]
                                            │
                              Is Resource ID == Tenant Phone ID?
                              Is Resource NOT Sandbox Test Number?
                              Is Registration Confirmed?
                              Is Owner Confirmation Received?
                                            │
                                            ▼
                                   [ CONNECTED (Live) ]
```

---

## 3. Authoritative Readiness Gate Evaluation

Before any number can transition to `CONNECTED` and activate live message sending (`is_whatsapp_connected = 1`), the service evaluates the following exact fields from `GET /{phone_number_id}`:

| Field | Requirement | Purpose |
|---|---|---|
| `id` | Must match tenant's `whatsapp_phone_number_id` | Prevents BOLA / resource ID swapping attacks |
| `verified_name` | Must be populated by Meta | Confirms business display name approval |
| `code_verification_status` | Must be `VERIFIED` when applicable | Confirms phone number possession verification |
| `is_test_number` check | Must evaluate to `False` | Blocks developer sandbox numbers from live activation |
| `token_scope` | Must belong to tenant's stored WABA | Ensures tenant ownership of WhatsApp Business Account |
| `register_response` | HTTP 200 from `POST /{id}/register` | Confirms Cloud API registration with server-generated PIN |
| `owner_approval` | Explicit owner JWT invocation | Enforces human-in-the-loop authorization |

---

## 4. API Version Governance Policy

- Supported versions are maintained in `SUPPORTED_META_API_VERSIONS = {"v20.0", "v21.0", "v22.0"}`.
- Requests using unapproved or deprecated versions fail safely with `ERROR_CAT_UNKNOWN` before dispatching any Meta calls.
- Scheduled review date for API version support: **Quarterly (Next review: 2026-11-20)**.

---

## 5. Security & Prohibited Actions

- ❌ Never accept registration PIN from frontend, query parameters, or request body.
- ❌ Never advise blanket WhatsApp account deletion as a default action.
- ❌ Never automatically delete, migrate, deregister, or alter merchant numbers.
- ❌ Never log, audit, cache, echo, or persist verification codes or registration PINs.
