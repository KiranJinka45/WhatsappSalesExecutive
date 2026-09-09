# Meta App Verification & WhatsApp Business Onboarding Playbook

This document details the step-by-step procedure to transition Closely AI from Meta sandbox/test numbers to live commercial WhatsApp Business API production dispatches.

---

## Pillar 1: Meta Business Verification (WABA)

To dispatch WhatsApp messages to arbitrary customer phone numbers worldwide without template/sandbox tier limits, your organization must complete **Meta Business Verification**:

### Required Documents:
1. **Official Business Registration**:
   - Certificate of Incorporation, GST Registration (India), or Articles of Organization.
   - The legal entity name on the document **must match** the name entered into Meta Business Manager.
2. **Proof of Business Address**:
   - Utility bill (electricity, water, landline), bank statement, or lease agreement under the business name.
3. **Domain Verification**:
   - Add a Meta TXT DNS verification record to your domain (e.g. `closely.ai` or your brand's root domain).
   - Verify business email address (e.g. `admin@closely.ai`). Public emails (@gmail.com, @yahoo.com) are rejected.

### Step-by-Step Submission:
1. Navigate to [Meta Business Settings](https://business.facebook.com/settings).
2. Go to **Security Center** -> **Business Verification** -> Click **Start Verification**.
3. Fill in the exact business details as printed on your legal tax documents.
4. Upload official documents and choose **Email Verification** or **Domain Verification**.
5. Typical review SLA: 24 to 72 hours.

---

## Pillar 2: Meta App Review & Required Permissions

Under your Meta Developer App (Type: **Business**):

### 1. Required Graph API Permissions:
- `whatsapp_business_messaging`: Enables sending and receiving WhatsApp messages.
- `whatsapp_business_management`: Enables managing WABA, phone numbers, and webhooks.

### 2. App Review Submission Checklist:
- **Privacy Policy URL**: Must be hosted and publicly reachable (e.g. `https://closely.ai/privacy`).
- **Terms of Service URL**: Must be publicly reachable.
- **App Icon**: 1024x1024 PNG with transparent or clean background.
- **Screencast Video Requirement**:
  - Record a 2-minute video demonstrating the business login, webhook reception, human approval inbox, and WhatsApp message dispatch.
  - Show clearly that customer consent is respected and that dispatches relate strictly to sales, orders, or explicit customer inquiries.

---

## Pillar 3: Meta Embedded Signup Integration

For merchants to onboard their own phone numbers without manual token sharing, Closely AI integrates Meta's **Embedded Signup** flow:

```
Merchant clicks "Connect WhatsApp" -> Meta Embedded Modal opens ->
Merchant selects WABA & Phone -> Meta issues authorization code ->
Frontend sends code to /api/brand/whatsapp/embedded-callback ->
Backend exchanges code for System User Access Token ->
Stored encrypted in Organization settings
```

### 1. Frontend Integration:
The Facebook SDK is loaded dynamically with `whatsapp_business_management` and `whatsapp_business_messaging` scopes. Once the merchant finishes the modal, the `onmessage` listener captures:
```javascript
window.addEventListener('message', (event) => {
  if (event.origin !== 'https://www.facebook.com') return;
  const data = JSON.parse(event.data);
  if (data.type === 'WA_EMBEDDED_SIGNUP') {
    // Send code and waba_id to backend
    apiFetch('/api/brand/whatsapp/embedded-callback', {
      method: 'POST',
      body: JSON.stringify({
        code: data.data.code,
        waba_id: data.data.waba_id,
        phone_number_id: data.data.phone_number_id
      })
    });
  }
});
```

### 2. Webhook Subscription:
Configure the Webhook URL in Meta Developer Dashboard:
- **Callback URL**: `https://api.yourdomain.com/api/webhooks/whatsapp`
- **Verify Token**: Configured in `settings.WHATSAPP_VERIFY_TOKEN`
- **Subscribed Fields**: `messages`, `message_deliveries` (statuses)
