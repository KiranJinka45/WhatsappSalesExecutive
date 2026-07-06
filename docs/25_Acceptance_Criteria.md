# Closely AI - Acceptance Criteria (AC)

This document translates the MVP User Stories into testable, Given-When-Then criteria to verify correct system execution.

---

## 1. Catalog Upload Pipeline (US-102)
* **ID**: AC-102-A (CSV Validation check)
* **Scenario**: Uploading a file with invalid elements.
  - **Given**: A merchant has logged into the dashboard and navigated to the catalog panel.
  - **When**: The merchant uploads a CSV catalog file where row 14 contains an empty price column and row 32 contains a duplicate SKU.
  - **Then**: The database transaction is rolled back, the upload status is set to `FAILED`, and the dashboard displays validation errors specifically identifying row 14 (Price missing) and row 32 (Duplicate SKU).

---

## 2. Inbound Product Search (US-201)
* **ID**: AC-201-A (Size & Stock constraint enforcement)
* **Scenario**: Filtering out out-of-stock sizes.
  - **Given**: The product catalog has a blue silk Kurti (SKU-1) where sizes `['S', 'M']` are in stock, but size `'L'` has `stock_count = 0`.
  - **When**: A customer messages the WhatsApp number: *"Do you have the blue silk Kurti in size L?"*
  - **Then**: The AI checks stock, does not pitch size L as available, and responds: *"The blue silk Kurti is currently out of stock in size L, but we have S and M sizes available immediately. Would you like me to show you similar styles in L?"*

---

## 3. Human Takeover Escalation (US-103)
* **ID**: AC-103-A (Intent-driven silent escalation)
* **Scenario**: Intercepting discount requests.
  - **Given**: A conversation has the status `ai_active`.
  - **When**: The customer messages: *"I want a custom bulk rate, give me 30% discount or let me talk to the manager."*
  - **Then**: The NLU classifies the message as `human_negotiation`, updates the database conversation status to `human_takeover`, posts a WebSockets alert to the dashboard, and silences further automated replies from the webhook.

---

## 4. Checkout Payment Link Generation (US-203)
* **ID**: AC-203-A (In-chat checkout links)
* **Scenario**: Customer confirms checkout parameters.
  - **Given**: A conversation is in the `Qualified` state and the customer has stated their address.
  - **When**: The customer sends: *"Yes, please generate the payment link for the green dress."*
  - **Then**: The system inserts an order record with status `PENDING`, calls the Razorpay/Stripe API, creates the checkout URL, and sends a WhatsApp template card containing the item details, total price, and the checkout link.
