# WhatsApp Number Onboarding — API Contract

## Base URL & Authentication
- **Base URL:** `/api/brand/whatsapp/`
- **Authentication:** Bearer JWT required on all endpoints.
- **Authorization:** `GET` endpoints require authenticated user; all mutation (`POST`) endpoints require `owner` role.

---

## Endpoints

### 1. `GET /api/brand/whatsapp/connection-status`
Returns sanitized onboarding and connection readiness status for the caller's tenant.

**Headers:**
`Authorization: Bearer <jwt_token>`

**Response (200 OK):**
```json
{
  "onboarding_state": "NOT_CONNECTED | COEXISTENCE_FLOW_AVAILABLE | BLOCKED_NUMBER_ACTIVE_IN_APP | BLOCKED_MIGRATION_REQUIRED | VERIFICATION_CODE_REQUESTED | VERIFICATION_CODE_VERIFIED | CONNECTED | META_TEST_NUMBER_CONNECTED | RATE_LIMITED | ERROR",
  "is_test_number": false,
  "masked_display_number": "+9179 ***** 58",
  "verification_method_available": ["SMS", "VOICE"],
  "cooldown_until": null,
  "manual_action_required": false,
  "safe_next_step": "Complete Embedded Signup or connect your WhatsApp Business Account.",
  "latest_error_category": null,
  "coexistence_flow_available": false
}
```

**Guaranteed Exclusions:**
`whatsapp_access_token`, `whatsapp_business_account_id`, `whatsapp_phone_number_id`, `pin`, `code`, and raw provider response bodies are strictly excluded.

---

### 2. `POST /api/brand/whatsapp/request-verification-code`
Requests an SMS or Voice verification code from Meta for programmatic verification flows.

**Headers:**
`Authorization: Bearer <owner_jwt_token>`

**Request Body:**
```json
{
  "method": "SMS"
}
```
*(method: `"SMS"` or `"VOICE"`)*

**Response (200 OK):**
```json
{
  "status": "code_requested",
  "onboarding_state": "VERIFICATION_CODE_REQUESTED",
  "method": "SMS",
  "cooldown_seconds": 300,
  "cooldown_until": "2026-08-25T14:15:00+00:00",
  "message": "Verification code requested successfully via SMS."
}
```

**Error Responses:**
- `400 Bad Request`: Configuration incomplete or method invalid.
- `403 Forbidden`: Non-owner role caller.
- `429 Too Many Requests`: Cooldown active or Meta rate limit reached.

---

### 3. `POST /api/brand/whatsapp/verify-registration-code`
Verifies a received verification code against Meta Cloud API.

**Headers:**
`Authorization: Bearer <owner_jwt_token>`

**Request Body:**
```json
{
  "code": "123456"
}
```
*(Validation: numeric string. Code is processed in volatile memory only and never persisted or logged.)*

**Response (200 OK):**
```json
{
  "status": "verified",
  "onboarding_state": "VERIFICATION_CODE_VERIFIED",
  "authoritative_resource_status": "VERIFIED",
  "message": "Phone number successfully verified with Meta."
}
```

**Error Responses:**
- `400 Bad Request`: Verification code invalid or expired.
- `403 Forbidden`: Non-owner role caller.
- `423 Locked`: Too many failed attempts (5-attempt lockout for 15 minutes).

---

### 4. `POST /api/brand/whatsapp/activate-live-number`
Executes server-side registration with Meta and activates live sending for the verified phone resource.

**Headers:**
`Authorization: Bearer <owner_jwt_token>`

**Request Body:**
*Empty body. No PIN is accepted from the client. Server generates a cryptographically secure 6-digit PIN in volatile memory.*

**Response (200 OK):**
```json
{
  "status": "activated",
  "onboarding_state": "CONNECTED",
  "is_whatsapp_connected": 1,
  "message": "Official WhatsApp Business Number is now active for automated sales messaging."
}
```

**Error Responses:**
- `400 Bad Request`: Meta registration failed, resource ID mismatch, test number blocked, or configuration incomplete.
- `403 Forbidden`: Non-owner role caller.
