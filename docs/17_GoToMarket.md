# Closely AI - Go-To-Market & Onboarding Strategy

This specification details the business onboarding process, self-serve client configurations, and strategies to scale customer acquisition for the Closely AI SaaS platform.

---

## 1. Brand Onboarding Lifecycle
To onboard a new retail apparel boutique to Closely AI, the customer success team or self-serve portal follows a 5-step checklist:

```
[ 1. Org Setup ] ──→ [ 2. Rules Setup ] ──→ [ 3. Catalog Sync ]
                                                   │
[ 5. Go Live ] ←── [ 4. Webhook Handshake ] ◄──────┘
```

### Onboarding Steps
1. **Organization Registration**: Create account, assign administrator, and configure brand metadata (Brand Name, WhatsApp display number, Logo).
2. **Policy Configuration**: Input policies (Shipping rates, returns/exchanges, store opening hours, COD availability) via the dashboard text editor.
3. **Catalog Synchronization**: Upload the initial CSV product file. Correct any errors surfaced by the validation pipeline.
4. **WhatsApp BSP Linkage**: Input Meta Cloud API keys and trigger the webhook validation handshake (`GET /api/webhooks/whatsapp`) to link the brand's WhatsApp number.
5. **Testing Sandbox Mode**: Execute 5 test conversations using sandbox numbers to verify vector indexing and grounding accuracy.

---

## 2. Self-Serve Dashboard Requirements
The client dashboard is the hub where retail brands manage their store operations. It features:

- **Catalog Management Portal**: A drag-and-drop CSV uploader displaying error logs and validation progress.
- **Console for Human Takeover**: A unified inbox showing active customer conversations, highlighting those marked `human_takeover` with sound alerts.
- **Analytics Dashboard**: Visual representations of conversion funnels, revenue influenced, and top objections.
- **System Settings Configuration**: Simple switches to enable/disable Cash on Delivery (COD), change shipping thresholds, and set promotional discount codes.

---

## 3. Go-To-Market & Growth Channels
To scale sales for Closely AI:

- **Shopify App Store Listing**: Build a Shopify integration that syncs Shopify catalogs directly to the Closely AI PostgreSQL database, bypassing CSV uploads.
- **Direct Outreach to Instagram D2C Brands**: Target mid-sized fashion labels that handle high volumes of customer inquiries via Instagram DMs and WhatsApp.
- **Free Sandbox Tier**: Offer boutique owners a free trial containing up to 100 conversations to demonstrate conversion-to-sale performance.
