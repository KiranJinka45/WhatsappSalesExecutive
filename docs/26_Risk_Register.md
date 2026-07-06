# Closely AI - Risk Register

This document tracks engineering, AI operational, and external integration risks, mapping out proactive mitigation strategies.

---

## Risk Register Matrix

| Risk ID & Description | Probability | Impact | Mitigation Strategy | Owner |
| :--- | :--- | :--- | :--- | :--- |
| **RSK-01: Meta Cloud API Modifications**<br>Meta changes payload structures or pricing models. | Medium | High | Implement a **BSP Adapter Layer** in the backend. Raw webhook payloads translate to internal events immediately, isolating upstream API changes. | Dev Lead |
| **RSK-02: Gemini API Outage / Throttle**<br>API calls time out or fail, blocking replies. | Medium | High | Define **Outage Fallback Handlers**. If Gemini fails, immediately send a preset customer support template and trigger a human takeover status. | AI Lead |
| **RSK-03: Invalid Catalog Uploads**<br>Merchants upload empty prices or duplicate SKUs. | High | Medium | Implement the **Strict CSV Schema Validation Pipeline** (reverting transactions on any failure row). | Backend Dev |
| **RSK-04: AI Response Hallucination**<br>AI invents products, sizes, or pricing. | Medium | Critical | - Enforce strict zero-temperature parameters.<br>- Apply post-retrieval **Grounding Checkers** comparing outputs against retrieved DB arrays. | AI Lead |
| **RSK-05: Multi-Tenant Data Leak**<br>SQL code missing filter, leaking catalog across brands. | Low | Critical | - Enable SQLAlchemy custom tenant-filtered base queries.<br>- Write automated integration tests asserting cross-tenant query failure. | Security Lead |
| **RSK-06: Webhook Spamming (DoS)**<br>High volume incoming webhook hits inflating LLM bill. | Medium | High | Implement **Redis Webhook Gateway Rate Limiting** per phone number/IP, returning HTTP 429 before invoking NLU engines. | Infra Lead |
