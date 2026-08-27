# Manual Meta Business Manager — WhatsApp Registration Guide

## Important: Choose the Meta-Supported Path for Your Account

Meta offers multiple paths depending on your number's current status. **Do not** default to deleting your WhatsApp account. Choose the path that Meta presents for your specific situation.

---

## Path 1: New Number (No Prior WhatsApp Registration)

1. Log into [Meta Business Suite](https://business.facebook.com/) → **All Tools** → **WhatsApp Manager**.
2. Click **Add Phone Number**.
3. Enter your display name, category, and phone number.
4. Select verification method (SMS or Voice Call).
5. Enter the verification PIN in WhatsApp Manager.
6. Number status will update to **REGISTERED**.
7. Save the Phone Number ID and WABA ID in Closely AI Settings.

---

## Path 2: Existing WhatsApp Business App Number — Coexistence Flow

If your number is currently active in the WhatsApp Business mobile app, Meta may offer a **coexistence/onboarding flow**:

1. Start Meta Embedded Signup from your Closely AI dashboard.
2. Meta detects your number is active in the Business app.
3. If eligible, Meta presents a **QR code / app-confirmation** process.
4. Complete the confirmation on your phone's WhatsApp Business app.
5. Your number gains platform capabilities while maintaining mobile app access (where supported).
6. **You do NOT need to delete your WhatsApp Business app account.**

Reference: [Meta Embedded Signup — Onboarding Business App Users](https://developers.facebook.com/docs/whatsapp/embedded-signup/custom-flows/onboarding-business-app-users/)

---

## Path 3: Migration Required

If Meta indicates your number requires migration before Cloud API use:

1. Review the specific migration guidance Meta provides for your account.
2. **Backup your chat history** before any migration: WhatsApp Business app → **Settings** → **Chats** → **Chat backup**.
3. Follow Meta's documented migration steps in [WhatsApp Manager](https://business.facebook.com/).
4. Only proceed with account changes (including deletion) if Meta explicitly requires it for your specific migration path.
5. Understand the consequences: deleting the mobile account erases message history unless backed up.

Reference: [Meta Official Migration Guide](https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/migrate-existing-whatsapp-number-to-a-business-account/)

---

## What Closely AI Will Never Do

- ❌ Automatically delete, migrate, deregister, or re-register your number
- ❌ Advise blanket account deletion as a default
- ❌ Bypass Meta's official migration or coexistence rules
- ❌ Store your verification code or registration PIN
