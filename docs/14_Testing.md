# Closely AI - Testing & AI Evaluation Framework

This document defines the testing protocols, unit test scopes, and evaluation framework for conversational accuracy and RAG precision.

---

## 1. Conversational AI Evaluation Metrics
Unlike standard code, LLM outputs must be evaluated continuously for grounding, hallucination, and sales conversion rates:

| Metric | Target SLA | Evaluation Method |
| :--- | :--- | :--- |
| **Grounding Score** | `> 98%` | LLM-as-a-Judge compares final output facts against catalog retrieve context list. |
| **Hallucination Rate** | `< 1%` | Scan output for prices/fabrics/colors not present in catalog dataset. |
| **Intent Precision** | `> 95%` | Evaluate classifier against a static validation dataset of 500 test messages. |
| **Retrieval Recall** | `> 90%` | Measure if appropriate product categories/colors are found by pgvector search. |
| **Escalation Accuracy** | `100%` | Verify that all negotiations or policy mismatches correctly trigger takeover status. |
| **Token Cost / Msg** | `< $0.005` | Monitor token usage headers to control operating margins. |
| **Latency SLA** | `< 2.0s (p95)` | Monitor processing time from webhook arrival to WhatsApp outbound queue. |

---

## 2. LLM Validation & Test Suite
To automate LLM evaluations, Closely AI uses a validation script that runs periodically on staging:

```
                  [ Staging CI/CD Pipeline ]
                             │
            (Load Bootstrap Test Conversations)
               - 100 mock customer queries
               - Pre-defined ground truth outputs
                             │
                (Execute AI Pipeline Run)
                             │
            (Evaluate Grounding & Hallucinations)
         - Run LLM judge to verify facts match DB
                             │
        ┌────────────────────┴────────────────────┐
        ▼                                         ▼
  [ Pass: Build OK ]                     [ Fail: Alert Team ]
 (Grounding >= 98%)                       (Grounding < 98%)
```

---

## 3. Traditional Code Testing

### Unit Test Suites
- **Catalog Sync Validation**: Test CSV parsing with:
  - Missing headers.
  - Duplicate SKUs.
  - Invalid image/video URLs.
  - Price formatting errors.
- **State Machine Transitions**: Mock database saves and asserts that sending a message changes the conversation state (e.g. from `GREETING` to `NEED_DISCOVERY`).

### Integration Test Suites
- **Webhook Endpoint**: Mock incoming HTTP calls in Twilio and Meta styles and verify database message entries.
- **Payment Lifecycle Webhook**: Mock a payment capture from Stripe/Razorpay and verify that the conversation stage shifts to `PAID` and order status changes.
