# Closely AI - MVP User Stories

This document lists the core merchant-facing and customer-facing user stories that define the MVP scope.

---

## 1. Merchant User Stories

### US-101: Brand Registration & Setup
* **Story**: As a boutique shop owner, I want to create an organization profile and input my shipping/return policies, so that the AI sales assistant has the correct grounding rules.
* **Benefit**: Saves the shop owner from writing custom guidelines per customer, keeping brand voice unified.

### US-102: Catalog Synchronization
* **Story**: As a retail manager, I want to upload a CSV catalog of products and get immediate feedback on format errors, so that I don't accidentally index incomplete listings.
* **Benefit**: Guarantees database hygiene, preventing AI recommendation errors in chat.

### US-103: Human Takeover Intervention
* **Story**: As a customer support agent, I want to see a real-time list of chats flagged as `human_takeover` with sound alerts, so that I can step in immediately to close wholesale deals.
* **Benefit**: Leverages AI for volume queries while leaving agents focused on closing high-value sales.

---

## 2. Customer User Stories

### US-201: Product Discovery in Stock
* **Story**: As a WhatsApp shopper, I want to ask for clothes in my size (e.g. *"Show me silk Kurtis in size L"*) and see only available, in-stock options, so that I do not get frustrated by out-of-stock items.
* **Benefit**: Speeds up shopping decisions and limits cart-abandonment churn.

### US-202: Guided Sizing Query
* **Story**: As an apparel shopper, I want to ask sizing compatibility questions (e.g. *"Will size M fit a 38-inch bust?"*), so that I can feel confident about the fit before checking out.
* **Benefit**: Overcomes the physical fitting-room objection, reducing return/exchange overhead.

### US-203: Seamless Checkout Intent
* **Story**: As a customer ready to buy, I want to confirm my sizes and receive a secure payment link directly inside WhatsApp, so that I can pay instantly without downloading another shopping app.
* **Benefit**: Streamlines the checkout flow to a single tap, increasing order conversion rates.
