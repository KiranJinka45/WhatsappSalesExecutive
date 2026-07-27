# Closely AI - Observability, Logging & Monitoring

This document details the structured logging standard, Prometheus metric endpoints, distributed OpenTelemetry trace configuration, and operational alerts.

---

## 1. Structured Logging Standard

To ensure all logs are queryable and traceable across distributed services, the FastAPI backend enforces a canonical JSON log and event standard. Every transaction and background job must log context containing these keys:

### Logging Event Schema
```json
{
  "timestamp": "2026-07-07T10:12:45.123Z",
  "request_id": "req-9e390c5d-2831-4c12-9c1c",
  "trace_id": "trace-5e6a7b2c9d8e4f1a",
  "conversation_id": "conv-8b2c4d6e-8e39-4c12-9c1c",
  "merchant_id": "org-8e390c5d-2831-4c12-9c1c-c76b91176b9f",
  "customer_id_hashed": "hash-919876543210-sha256",
  "model_version": "gemini-2.5-flash",
  "prompt_version": "v1.4-sales-grounding",
  "latency_ms": 842,
  "outcome": "recommendation_sent",
  "error_code": null,
  "level": "info",
  "message": "AI reply successfully generated and validated for conversation"
}
```

### Log Schema Dictionary
* `timestamp` (String/UTC): ISO 8601 formatted date and time with millisecond precision.
* `request_id` (String): Unique transaction tracking ID generated at the API controller boundary.
* `trace_id` (String): OpenTelemetry distributed tracing ID to correlate API calls with background Celery/database spans.
* `conversation_id` (String/UUID): The active customer conversation database ID.
* `merchant_id` (String/UUID): The organization tenant database ID.
* `customer_id_hashed` (String): Cryptographically hashed phone number of the customer (SHA-256) to comply with privacy minimization.
* `model_version` (String): Exact version tag of the LLM generator (e.g. `gemini-2.5-flash`).
* `prompt_version` (String): Version code of the active system prompt template loaded from database memory.
* `latency_ms` (Integer): Total millisecond execution time of the request or task.
* `outcome` (String): Standardized execution output tag (e.g. `recommendation_sent`, `takeover_triggered`, `payment_linked`, `safety_blocked`).
* `error_code` (String/Null): Standardized system error identifier if the run failed (e.g. `GEMINI_TIMEOUT`, `DB_POOL_EXHAUSTED`, `SIGNATURE_MISMATCH`).

---

## 2. Core Prometheus Metrics

The backend exposes a `/metrics` route scraped by Prometheus to collect operational counters:

* `inbound_webhooks_total`: Counter tracking total WhatsApp incoming webhooks.
* `llm_latency_seconds_histogram`: Histogram measuring Gemini response latencies.
* `conversion_stage_reached_total`: Counter tracking customer conversion actions (e.g. `stage=CART_INTENT`).
* `takeover_escalations_total`: Counter tracking manual takeover trigger loops.

---

## 3. Distributed Tracing (OpenTelemetry)

To debug latency spikes, OpenTelemetry is injected into the middleware layer to trace webhook requests through the engine:

```
[ Inbound HTTP Webhook ]  (Trace ID: 5e6a7b...)
        │
        ├──► [ Intent Classifier Task ]  (Span ID: i1, Duration: 350ms)
        │
        ├──► [ Vector DB Query ]         (Span ID: q2, Duration: 80ms)
        │
        └──► [ Gemini Response Call ]    (Span ID: g3, Duration: 750ms)
```

---

## 4. Alerting Threshold Rules

Automated alerts dispatch notifications to Slack or PagerDuty on these threshold violations:

1. **System Outage Alert**: Trigger immediately if Webhook endpoint returns HTTP 500 errors on `> 5%` of calls in any 5-minute window.
2. **LLM Latency Spike**: Trigger warning if average p95 response generation latency exceeds `3.0 seconds` over 10 consecutive calls.
3. **Queue Backlog Warning**: Alert if Celery task queue size exceeds `100` pending outbound WhatsApp messages.
