# Closely AI - Observability & Monitoring

This document details structured logging configurations, Prometheus metric endpoints, trace tracking setups, and alert thresholds.

---

## 1. Structured Logging Format
To facilitate log aggregation (using systems like Datadog, Grafana Loki, or AWS CloudWatch), the FastAPI backend uses structured JSON logging via the Python `structlog` package:

```json
{
  "timestamp": "2026-07-05T08:54:59Z",
  "level": "info",
  "event": "conversation_state_transition",
  "org_id": "8e390c5d-2831-4c12-9c1c-c76b91176b9f",
  "customer_phone": "919876543210",
  "previous_state": "GREETING",
  "new_state": "NEED_DISCOVERY",
  "intent": "product_discovery"
}
```

---

## 2. Core Prometheus Metrics
The backend exposes a `/metrics` route scraped by Prometheus to collect operational counters:

- `inbound_webhooks_total`: Counter tracking total WhatsApp incoming webhooks.
- `llm_latency_seconds_histogram`: Histogram measuring Gemini response latencies.
- `conversion_stage_reached_total`: Counter tracking customer conversion actions (e.g. `stage=CART_INTENT`).
- `takeover_escalations_total`: Counter tracking manual takeover trigger loops.

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
