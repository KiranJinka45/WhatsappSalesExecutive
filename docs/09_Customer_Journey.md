# Closely AI - Customer Journey Map

This document outlines the end-to-end customer journey from initial discovery to retention, defining the user experience and backend automations at each milestone.

---

## 1. Customer Journey Flowchart

```
[ Discovery ] ──→ [ Qualification ] ──→ [ Recommendation ] ──→ [ Decision ]
                                                                     │
[ Retention ] ←── [ Post-Purchase ] ←── [ Fulfillment ] ←── [ Conversion ]
```

---

## 2. Journey Milestones & Touchpoints

### Step 1: Discovery
- **Action**: Customer clicks an Instagram story ad ("Chat to Buy"), scans a QR code on a boutique hangtag, or clicks a website widget.
- **Touchpoint**: The link opens WhatsApp with a pre-filled message (e.g., *"Hi, I want to see your new festive collection"*).
- **Backend Action**: System instantiates a `Conversation` in the `Visitor` stage.

### Step 2: Qualification
- **Action**: AI greets the customer and runs occasion discovery.
- **Touchpoint**: AI asks for size (e.g., XS, S, M, L) and color/style preferences.
- **Backend Action**: Extracts entities and updates `customer_memory` sizing profile.

### Step 3: Recommendation
- **Action**: Customer views product recommendations.
- **Touchpoint**: AI sends a WhatsApp Catalog carousel (Multi-Product Message) containing high-res product photos, descriptions, and sizes in stock.
- **Backend Action**: Executes a hybrid search using extracted entities + pgvector.

### Step 4: Decision
- **Action**: Customer evaluates options and checks policy/fit.
- **Touchpoint**: AI shares sizing charts, fabric details (e.g. *"This Banarasi is pure silk, lightweight, and dry-clean only"*), and shipping rates.
- **Backend Action**: References `Organization.policies` JSON for exact grounding facts.

### Step 5: Conversion
- **Action**: Customer selects their size and initiates checkout.
- **Touchpoint**: AI generates the order list, asks for delivery details, and sends a secure online payment link.
- **Backend Action**: Inserts a pending record into `orders`, creates the payment gateway link (Razorpay/Stripe), and polls for payment webhook updates.

### Step 6: Fulfillment
- **Action**: Payment confirmed.
- **Touchpoint**: AI sends an automated receipt confirmation and tracking code.
- **Backend Action**: Webhook catches `payment.captured`, changes status to `PAID`, updates conversation stage to `PAID`, and triggers shipping partner API integrations.

### Step 7: Post-Purchase & Retention
- **Action**: Order delivered.
- **Touchpoint**: 48 hours after delivery, AI asks: *"How did the outfit fit? We'd love to see a photo!"*
- **Backend Action**: Scheduler runs follow-up jobs. If customer returns, starts conversation in `REPEAT` stage, proposing items matching historical sizes.
