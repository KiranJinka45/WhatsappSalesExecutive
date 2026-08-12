# Closely AI - MVP Roadmap & Execution Plan

This roadmap outlines the plan to progress Closely AI from its current MVP state to a highly scalable, production-hardened platform.

---

## Milestone 1: Core Webhook Stability & RLS Hardening (Completed)
Ensure robust multitenancy separation and high-availability webhook ingestion.

- [x] **RLS Fixes for Global Queries**: Bypass database Row-Level Security during webhook organization and settings queries.
- [x] **Webhooks Endpoint Deduping**: Implement Redis-based message idempotency inside `receive_whatsapp_message` to ignore duplicate retries from Meta.
- [x] **Robust Error Handling**: Save incoming messages and keep conversation status alive even when downstream AI services fail.
- **Verification (UAT)**:
  - Run the full test suite to guarantee 100% of the 170+ tenant isolation, webhook, and grounding tests pass.
  - Verify that a test message sent to the WhatsApp API is registered in the database and shows up on the merchant dashboard.

---

## Milestone 2: WhatsApp Sandbox-to-Production Migration (In Progress)
Transition from developer sandbox testing to permanent production numbers.

- [/] **Add Production Business Numbers**: Register and verify live business phone numbers in the Meta Developer portal.
- [/] **Permanent Access Token Integration**: Generate non-expiring System User access tokens and verify them in the settings panel.
- [ ] **Webhook Fields Subscription**: Ensure the `messages` subscription is enabled inside the Meta App configurations.
- **Verification (UAT)**:
  - Confirm the "Test Meta Connection" diagnostic tool returns `Success`.
  - Send a WhatsApp message from a non-developer personal phone number and verify the AI replies without allowed-list restrictions.

---

## Milestone 3: Real-Time Sync & Dashboard Usability (Next)
Improve merchant interaction speed, notifications, and dashboard responsiveness.

- [ ] **SSE Reconnection Hardening**: Update the frontend connection manager to auto-reconnect with backoff on SSE dropouts.
- [ ] **Multi-Agent / Agent Roles UI**: Add login and dashboard view differences for `owners` (settings modification allowed) vs. `agents` (viewing/taking over chats only).
- [ ] **Web Push Notifications**: Integrate web push notifications using the browser API to alert merchants of pending approvals or human takeover requests in real-time.
- **Verification (UAT)**:
  - Manually disconnect network cables during an active dashboard session, verify it auto-reconnects, and ensure no incoming messages are lost.
  - Log in as a support agent, verify that organization settings fields are disabled, and check that notifications show up when an approval is requested.

---

## Milestone 4: Multimodal Ingestion & Advanced Apparel Search (Future)
Hardening the apparel-focused moat via visual search and profile memory.

- [ ] **Gemini Multimodal Saree Matching**: Update the ingestion engine to parse incoming customer image attachments and compare their embeddings against the catalog.
- [ ] **Customer Profile Preferences Store**: Automatically extract size, preferred fabric, and budget limit from previous chat history and save it to the customer profile metadata.
- [ ] **Outbound Marketing Drops**: Enable merchants to create target customer segments based on size/color preferences and broadcast WhatsApp message notifications when matching new arrivals are uploaded.
- **Verification (UAT)**:
  - Send an image of a red silk saree to the WhatsApp bot and verify the AI recommends the closest matching SKU from the database.
  - Query a customer profile and confirm that their preferred size is automatically updated based on their purchase history.
