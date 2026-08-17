# Closely AI - Shadow Mode Execution Runbook

---

## 1. Overview & Operational Goal

In **Shadow Mode**, Closely AI receives incoming WhatsApp messages, retrieves catalog facts, applies deterministic policy guardrails, and generates draft replies in the background without dispatching any messages to WhatsApp customers.

```
WhatsApp Customer Message ──► Webhook API ──► Redis/Async Queue ──► Shadow Worker
                                                                        │
                                                                        ▼
                                                            Generates Copilot Draft
                                                            Calculates Confidence
                                                            Stores Grounding Evidence
                                                                        │
                                                                        ▼
                                                            [0 Messages Sent to Customer]
                                                            Saved in ApprovalRequest Audit
```

---

## 2. Telemetry & Observation Protocol

During Shadow Mode, the background worker logs structured observation records into `ApprovalRequest` and `Notification` audit entities:

1. **Incoming Intent & Extracted Entities**:
   - `intent`: E.g. `CATALOG_INQUIRY`, `DISCOUNT_REQUEST`, `REFUND_REQUEST`, `COMPLAINT`, `BULK_ORDER`, `TAILORING`.
   - `entities`: E.g. `{"color": "maroon", "budget_max": 10000, "sku": "SKU-SAR-001"}`.
2. **Deterministic SQL Search Result**:
   - `retrieved_skus`: List of matching SKUs.
   - `price_snapshot`: Live price fetched from SQL.
   - `stock_snapshot`: Live stock count fetched from SQL.
3. **Generated Draft & Grounding Validation**:
   - `draft_text`: Proposed response text.
   - `grounding_valid`: True/False (whether draft prices and SKUs match SQL snapshot).
   - `grounding_score`: Decimal between 0.0 and 1.0.
   - `draft_latency`: Time taken from webhook arrival to draft ready.
4. **Accuracy Comparison**:
   - Compares the AI draft against the manual response sent by human store staff.
   - Computes intent accuracy, entity extraction F1, price correctness, and false-escalation rate.

---

## 3. Verified Shadow Mode Scenarios (17 Pipeline Scenarios)

The shadow execution suite in `backend/tests/test_05_shadow_mode.py` covers 17 distinct scenarios:

| # | Scenario | Decision / Escalation | Outbound Sent? |
|---|---|---|---|
| 1 | Fast Webhook Acknowledgment | HTTP 200 returned immediately | No |
| 2 | Duplicate `wamid` Idempotency | Redis deduplication key skips worker | No |
| 3 | Tenant Resolution & Rejection | Invalid brand phone returns 400 error | No |
| 4 | Exact SKU Query | SQL lookup, copilot draft generated | No |
| 5 | Product Filter Query | SQL WHERE filters, draft with catalog matches | No |
| 6 | Out of Stock Query | Stock 0 detected, suggested alternative | No |
| 7 | No Result Catalog Query | Zero matches, polite fallback response | No |
| 8 | Discount Escalation | `DISCOUNT_POLICY` lock -> `WAITING_APPROVAL` | No |
| 9 | Refund Escalation | `REFUND_POLICY` lock -> `WAITING_APPROVAL` | No |
| 10 | Complaint Escalation | `COMPLAINT_ESCALATION` lock -> `WAITING_APPROVAL` | No |
| 11 | Bulk Order (>10 pcs) | `BULK_THRESHOLD` lock -> `WAITING_APPROVAL` | No |
| 12 | Tailoring / Custom Fit | `TAILORING_CUSTOM` lock -> `WAITING_APPROVAL` | No |
| 13 | Low Confidence (< 0.85) | `LOW_CONFIDENCE` lock -> `WAITING_APPROVAL` | No |
| 14 | Prompt Injection Security | Security Event logged -> `WAITING_APPROVAL` | No |
| 15 | Cross-Tenant DB Isolation | `SET LOCAL app.current_tenant` enforced | No |
| 16 | Zero-Outbound Guardrail | `send_whatsapp_message` suppressed in Shadow Mode | No |
| 17 | Network Boundary Guardrail | Zero external HTTP traffic emitted to Meta API | No |

---

## 4. Comprehensive Audit Paths (13 Logging Trajectories)

The audit validation suite in `backend/tests/test_06_shadow_audit_and_security.py` verifies 13 distinct audit trajectories:

1. `test_audit_01_valid_catalog_query`: Standard inquiry with complete SKU snapshots and grounding scores.
2. `test_audit_02_no_matching_product`: Catalog miss logging and polite fallback draft.
3. `test_audit_03_out_of_stock_result`: Out-of-stock event capture and escalation notice.
4. `test_audit_04_low_confidence`: Confidence threshold failure logging with reasoning.
5. `test_audit_05_discount_request`: Discount policy lock event and approval request creation.
6. `test_audit_06_refund_request`: Refund escalation event with customer policy history.
7. `test_audit_07_complaint_escalation`: High-priority escalation notification creation.
8. `test_audit_08_bulk_order`: Quantity threshold violation recording.
9. `test_audit_09_tailoring_request`: Custom work escalation logging.
10. `test_audit_10_prompt_injection`: Security event classification and query isolation.
11. `test_audit_11_duplicate_webhook`: Idempotency bypass audit logging.
12. `test_audit_12_worker_exception`: Worker failure fallback state recording.
13. `test_audit_13_database_retry_fallback`: DB connection retry and graceful transaction recovery.
