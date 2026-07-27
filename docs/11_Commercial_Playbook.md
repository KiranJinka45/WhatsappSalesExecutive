# Closely AI - Commercial Playbook

*Status: **EVOLVING** (Refined based on sales acquisition cycles and pilot commercial outcomes).*
*Version: **v1.0.0-draft***

---

## 1. Ideal Customer Profile (ICP)

Our target customers are small-to-medium business (SMB) fashion and clothing boutique retailers who meet the following characteristics:
* **Product Catalog**: Digital catalog available (CSV, Shopify export, or WooCommerce integration) with structured fields (SKU, name, price, size, stock, category).
* **Conversation Volume**: Handles 50–500 inbound WhatsApp customer chats per day.
* **Current Operations**: Employs 1–3 human agents handling catalog queries, sizing requests, and shipping follow-ups manually.
* **Infrastructure**: Already uses WhatsApp Business App or a basic shared inbox, but experiences bottleneck delays.

---

## 2. Design Partner Selection Criteria

For our pilot waves, we select partners based on engagement readiness:
* **High Responsiveness**: Willing to dedicate a store manager to monitor the dashboard and act on the Approval Queue daily.
* **Low Risk Profile**: Fixed-pricing models (does not negotiate custom prices on a per-chat basis) and a straightforward, clearly documented refund/return policy.
* **Feedback Loop**: Commits to a weekly 30-minute qualitative feedback call.
* **Access**: Can provision full administrative access to their Meta Developer account and catalog source data within 24 hours.

---

## 3. Pilot Agreement Checklist

Before deploying Closely AI to live production traffic, the commercial lead must verify:
* [ ] Signed pilot Terms of Service (ToS) detailing data privacy, safe-harbor AI disclaimers, and liability bounds.
* [ ] Multi-tenant isolation verification sign-off from engineering.
* [ ] Dedicated human backup agent identified and trained on the dashboard override console.
* [ ] Catalog schema validation successfully passed (0 errors in parsing sizes/prices).
* [ ] Meta Business Manager permissions granted.

---

## 4. Success Metrics for a Paying Customer

A pilot partner is considered ready to transition to a standard subscription plan if:
* **PCAR Baseline**: Policy-Compliant Autonomous Resolution (PCAR) rate is stable and measured.
* **Time Saved**: Human staff spending < 1 hour/day on messaging tasks.
* **Conversion Lift**: Measured increase in conversation-to-order funnel throughput vs previous manual baselines.
* **Merchant Satisfaction**: Weekly CSAT feedback score of ≥ 4.5/5.

---

## 5. Pricing Philosophy

We align our monetization model directly with the merchant value generated:
* **Base Platform Fee**: Monthly subscription covering tenant database hosting, dashboards, and system maintenance.
* **Success Volume Fee**: Tiered pricing based on successfully resolved autonomous conversations (PCAR-completed interactions) or direct transaction revenue events, ensuring Closely AI is a profit center rather than a cost center.

---

## 6. Onboarding Checklist

Completed within 15 minutes without engineering manual intervention:
1. [ ] **Account Registration**: Merchant signs up and creates Organization ID.
2. [ ] **Catalog Ingestion**: Upload catalog file (CSV/Shopify) and verify formatting parses correctly.
3. [ ] **Policy Mapping**: Configure business policies (shipping fees, exchange rules, discount limit thresholds).
4. [ ] **Channel Integration**: Link WhatsApp number using the embedded Meta signup flow.
5. [ ] **Sandbox Run**: Execute 5 test conversations inside the local emulator to verify bot grounding and Approval Queue alerts.
6. [ ] **Go Live**: Activate autonomous routing.

---

## 7. Offboarding Checklist

To be completed within 24 hours of contract termination:
1. [ ] **Deactivate Webhooks**: Unregister WhatsApp webhook endpoints from the Meta App.
2. [ ] **Tenant Purge**: Archive and soft-delete customer conversation tables matching Organization ID.
3. [ ] **Catalog Deletion**: Physically delete product embeddings and image caches from pgvector store.
4. [ ] **Revoke Credentials**: Revoke developer/dashboard API access tokens and close tenant account.

---

## 8. Renewal Criteria

Evaluate renewal options at the end of the pilot cycle based on:
* Conversion telemetry showing positive ROI.
* Merchant dashboard login metrics showing daily utilization of the approval queue.
* Under-control override rates, proving the bot has adapted to their store personality.
