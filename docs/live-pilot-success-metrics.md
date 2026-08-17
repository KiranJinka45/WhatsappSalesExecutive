# Live Pilot Success Metrics & Telemetry Specification

**Date:** 2026-08-16  
**Document Version:** 1.1  
**Target Environment:** First 14 Days of Live Boutique Pilot

---

## 1. Zero-Tolerance Safety Thresholds (Pass/Fail)

| Telemetry Metric | Target Threshold | Monitoring Mechanism | Alert SLA |
|---|---|---|---|
| **Outbound Messages Without Approval** | **0** | DB Trigger & Audit Log Check | Instant PagerAlert |
| **Duplicate Outbound Messages** | **0** | Outbox Idempotency Key Constraint | Instant PagerAlert |
| **Incorrect Price / Stock Promises** | **0** | Tenant-Scoped Catalog Grounding Engine Audit | Instant PagerAlert |
| **Cross-Tenant Access Incidents** | **0** | RLS Violation & Audit Log Check | Instant PagerAlert |
| **Kill-Switch Execution Failures** | **0** | Dispatch Transaction Interception | Instant PagerAlert |
| **Automatic Retries on Unknown Timeout** | **0** | Outbox Worker Retry Block Check | Instant PagerAlert |

---

## 2. Programmatic Telemetry Requirements Per Live Send

For every live outbound message, the system programmatically calculates and logs:
- `approved_text_character_count` (`len(message_text)`)
- `approved_text_utf8_byte_count` (`len(message_text.encode("utf-8"))`)
- `content_sha256` (`hashlib.sha256(message_text.encode("utf-8")).hexdigest()`)
- `message_version`
- `outbox_id`
- `provider_message_id_hash`
- `audit_event_ids`
