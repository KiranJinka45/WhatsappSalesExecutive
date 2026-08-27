# Meta Embedded Signup Integration Plan (Technical Specification)

## 1. Overview

This document specifies the technical architecture, security boundaries, and integration plan for official Meta WhatsApp Embedded Signup within Closely AI.

> **Safety Notice:** This plan is a technical specification only. No live Meta API calls, OTP generation, or real number mutations are executed during this specification phase.

---

## 2. Frontend Integration (Meta JavaScript SDK)

### 2.1 SDK Initialization & Configuration
- Load Meta JavaScript SDK asynchronously with tenant-safe configurations:
  ```javascript
  window.fbAsyncInit = function() {
    FB.init({
      appId: '<META_APP_ID>',
      autoLogAppEvents: true,
      xfbml: true,
      version: 'v20.0'
    });
  };
  ```
- **Security Rule:** Meta App ID is public configuration; no App Secret or System User tokens are included in client bundles.

### 2.2 Embedded Signup Popup Launch
- Trigger Meta Embedded Signup popup via `FB.login()` with required scopes and config ID:
  ```javascript
  FB.login(function(response) {
    if (response.authResponse) {
      const code = response.authResponse.code;
      // Send code securely to tenant-authenticated backend
      handleAuthorizationCodeExchange(code);
    } else {
      // User cancelled or login failed
      handleSignupDismissal(response);
    }
  }, {
    config_id: '<META_CONFIG_ID>',
    response_type: 'code',
    override_default_response_type: true,
    extras: {
      setup: {},
      featureType: '',
      sessionInfoVersion: '3'
    }
  });
  ```

### 2.3 Session Info Listener (WABA & Phone Discovery)
- Listen to `message` events dispatched from Meta's popup iframe:
  ```javascript
  window.addEventListener('message', (event) => {
    if (event.origin !== 'https://www.facebook.com' && event.origin !== 'https://web.facebook.com') return;
    try {
      const data = JSON.parse(event.data);
      if (data.type === 'WA_EMBEDDED_SIGNUP') {
        // data.data contains waba_id, phone_number_id, current_step
        handleEmbeddedSignupEvent(data.data);
      }
    } catch (e) {}
  });
  ```

---

## 3. Backend Secure Exchange & Tenant Binding

### 3.1 Token Exchange Flow
1. **Endpoint:** `POST /api/brand/whatsapp/embedded-signup-callback` (Owner-only).
2. **Payload:** `{ "code": "<authorization_code>" }`
3. **Backend Exchange:**
   - Call Meta Graph API:
     ```http
     GET https://graph.facebook.com/v20.0/oauth/access_token?
       client_id={APP_ID}&
       client_secret={APP_SECRET}&
       code={CODE}
     ```
   - Server-side only: `APP_SECRET` never leaves backend environment.

### 3.2 WABA & Phone Resource Verification
1. Inspect token scope and debug token info (`GET /debug_token`).
2. Fetch registered phone numbers for the WABA:
   ```http
   GET https://graph.facebook.com/v20.0/{waba_id}/phone_numbers
   ```
3. Extract `phone_number_id`, `display_phone_number`, and `code_verification_status`.
4. Run `_is_test_number()` safeguard check. If sandbox test number, mark `is_test_number=True` and flag state `META_TEST_NUMBER_CONNECTED`.

---

## 4. Existing Business App User Coexistence Flow

### 4.1 Coexistence Detection
- When Meta's Embedded Signup session reports that the number is already active in WhatsApp Business App:
  - If eligible: Meta presents the **QR code / in-app confirmation modal** directly inside Embedded Signup iframe.
  - Closely AI does not intervene or request OTP.
  - Upon successful confirmation, Meta registers Cloud API permissions while maintaining the merchant's app capabilities.

### 4.2 Fallback Routing
- If coexistence is unavailable for the merchant's tier/region:
  - Backend records state `BLOCKED_MIGRATION_REQUIRED` or `MANUAL_META_ACTION_REQUIRED`.
  - Frontend displays official Meta WhatsApp Manager guidance: *"Choose the Meta-supported path shown for your account."*
  - **Strict Prohibition:** Closely AI will never advise blanket deletion as a default action.

---

## 5. Security & Isolation Matrix

| Boundary | Enforcement Mechanism |
|---|---|
| **Tenant Binding** | Token exchange binds WABA and Phone ID strictly to `current_user.organization_id`. |
| **Secret Protection** | Meta App Secret and System User tokens stored only in encrypted environment configs. |
| **PIN & Code Zero-Leakage** | Registration PIN generated server-side in ephemeral process memory. Never logged or audited. |
| **Audit Immutability** | `whatsapp_onboarding_audit_logs` protected by PostgreSQL RLS with SELECT/INSERT-only grants. |
| **Test Number Isolation** | Sandbox numbers prohibited from receiving live customer dispatches. |
