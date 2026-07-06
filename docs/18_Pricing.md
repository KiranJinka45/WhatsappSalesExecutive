# Closely AI - Pricing & Monetization Strategy

This document defines the SaaS subscription tiers, operational cost structures (LLM tokens, WhatsApp BSP fees), and value metrics for Closely AI.

---

## 1. Subscription Tiers

### Growth Tier ($49 / month)
- **Target Audience**: Micro-boutiques and local fashion brands.
- **Limits**: 1,000 active conversations per month.
- **Features**: Basic CSV catalog upload, standard text-based recommendations, single-user takeover dashboard, standard analytics.

### Scale Tier ($149 / month)
- **Target Audience**: Established D2C clothing brands.
- **Limits**: 5,000 active conversations per month.
- **Features**: Visual similarity search, multi-product WhatsApp carousels, multi-agent human takeover dashboard, automated cart-recovery follow-ups.

### Enterprise Tier (Custom / starts at $499)
- **Target Audience**: Large apparel retail chains.
- **Limits**: Custom/Unlimited.
- **Features**: Direct Shopify/WooCommerce catalog sync, dedicated database instance, SLA support, customized fine-tuned tone settings.

---

## 2. Operational Cost Analysis

```
  [ Customer Message ] ────► [ Closely AI API ] ────► [ Gemini LLM API ]
           ▲                                                   │
     (Meta WhatsApp fee)                                  (Token cost)
           │                                                   ▼
     [ Outbound Message ] ◄── [ Celery Queue ] ◄─────── [ Output generated ]
```

### 1. Model Execution Costs (Gemini 2.5 Flash)
- **Cost**: $0.075 / million input tokens, $0.30 / million output tokens.
- **Average Conversation**: 15 messages (15,000 input tokens + 3,000 output tokens).
- **Cost per conversation**: `~ $0.002` (extremely high margin).

### 2. WhatsApp Business API Costs (Meta)
- **User-Initiated Conversation**: Meta charges a flat rate based on region (e.g., `~$0.01` per 24-hour session in India, `~$0.02` in USA).
- **Billing Strategy**: Brands connect their own Meta Business Manager credit cards to WhatsApp, leaving Closely AI's SaaS fee as pure software margin.

---

## 3. Monetization Proof Point: Revenue Influenced
To prevent churn and justify the subscription fee, the Closely AI dashboard tracks **Revenue Influenced**:
- **Definition**: Sum of all `orders.total_amount` records where payment was confirmed (`PAID`) and the order was initiated during an active conversation handled by the AI.
- **Return on Investment (ROI) Pitch**: Show the boutique owner that for a $49/month SaaS spend, Closely AI closed or recovered thousands in retail sales.
