# Closely AI - Operations Runbook & Escalation Protocols

This runbook defines system operations, human takeover rules, fallback procedures during outages, and logging structures.

---

## 1. Human Takeover & Escalation Lifecycle

```
[ Conversation status: ai_active ]
                 │
      (Intent / Policy Check)
      - User asks to speak with owner
      - Price or stock validation mismatch
      - User requests discount
                 │
                 ▼
  [ Update status: human_takeover ]
                 │
   ┌─────────────┴─────────────┐
   ▼                           ▼
[ Dashboard Notification ]  [ Stop AI Pipeline ]
- WebSockets notification    - Skip reply generation
- Alert UI displays chat     - Silently log messages
                               - Await agent reply
```

### Dashboard Release / Hand-back
Once the human agent completes the sale or resolves the issue, they click **"Resume AI Sales Mode"** on the dashboard.
- **Action**: REST API triggers `POST /api/conversations/{id}/resolve` (updates status to `ai_active`, resets funnel state to `RECOMMENDATION` or `CHECKOUT`, and resumes automated flow).

---

## 2. System Fallback Procedures

### API Outage Fallbacks (Gemini Offline)
- **Problem**: Gemini API times out or fails (HTTP 500/503/429).
- **Behavior**: The AI generation step fails. The system catches the exception and executes the following fallback actions:
  1. Append system message to history: *"I'm having trouble retrieving details right now. Let me connect you with one of our store managers."*
  2. Call the WhatsApp API to dispatch this fallback text.
  3. Force transition the conversation status to `human_takeover`.
  4. Trigger a Slack / Dashboard notification: `[OUTAGE ALERT] Gemini API invocation failed. Handoff triggered.`

### Webhook Delivery Failure Recovery
- **Problem**: Meta Cloud API fails to deliver incoming messages due to API Gateway congestion.
- **Behavior**: Meta retries webhook delivery. The system uses a deduplication filter in Redis (`webhook:dedup:<message_id>`) with a 5-minute TTL to ensure we do not process or reply to the same message multiple times.

---

## 3. Monitoring & Alerting Schema
- **Metrics Dashboard**: Track API performance using Prometheus and Grafana.
- **Crucial Metrics**:
  - `llm_generation_latency_seconds`: Target `< 1.2s` average.
  - `human_takeover_ratio`: Target `< 15%` of total daily conversations.
  - `api_calls_count`: Partitioned by tenant organization.
- **Error Tracking**: Log all LLM prompt errors with transaction IDs using structured logging (`structlog`).
