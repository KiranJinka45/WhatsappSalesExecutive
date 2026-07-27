# Closely AI - Operations & Pilot Incidents Runbook

This document defines system operations targets, Service Level Indicators (SLIs), incident response playbooks with role ownership, and disaster recovery validation drills.

---

## 1. Service Level Objectives (SLOs) & Service Level Indicators (SLIs)

To ensure launch readiness and define operational boundaries, Closely AI commits to the following operational targets during active pilot and production phases:

| Objective (SLO) | Target | Service Level Indicator (SLI) Formula | Measurement Window |
| :--- | :--- | :--- | :--- |
| **API Availability** | $\ge 99.5\%$ | $\frac{\text{Successful HTTP Requests (2xx/3xx/4xx)}}{\text{Total HTTP Requests}}$ | Rolling 30 Days |
| **p95 Response Latency** | $< 2.0\text{ s}$ | $95^{\text{th}}$ percentile latency of all `/api/` calls | Rolling 24 Hours |
| **Webhook Acknowledgment** | $< 500\text{ ms}$ | $\frac{\text{Webhooks responded to with } 200 \text{ OK in } \le 500\text{ms}}{\text{Total Webhooks Received}}$ | Rolling 24 Hours |
| **Successful Catalog Imports**| $> 99.0\%$ | $\frac{\text{Completed imports without system exception}}{\text{Total catalog uploads initiated}}$ | Rolling 7 Days |
| **Failed Deployments** | $< 5.0\%$ | $\frac{\text{Failed staging/production deployment runs}}{\text{Total deploy pipeline triggers}}$ | Rolling Quarterly |

---

## 2. Disaster Recovery (DR) Targets & Drills

Having backups is not enough; their restoration must be audited regularly. The support team must perform a quarterly dry run to verify the recovery systems against defined business targets:

### Recovery Targets
* **Recovery Point Objective (RPO)**: **15 minutes** (Maximum tolerable data loss. Backups must occur or stream transaction logs to replica storage continuously).
* **Recovery Time Objective (RTO)**: **30 minutes** (Maximum tolerable downtime to restore database, index cache, and backend services).

### Quarterly DR Drill Checklist
1. **Restore Backup**: Spin up an isolated PostgreSQL instance and restore the latest backup dump.
2. **Verify Data Integrity**: Confirm table row counts match expected parameters:
   ```sql
   SELECT count(*) FROM products;
   SELECT count(*) FROM conversations;
   ```
3. **Verify pgvector Embeddings**: Run a similarity cosine query to confirm vector index retrieval operates correctly:
   ```sql
   SELECT id, name FROM products ORDER BY embedding <=> (SELECT embedding FROM products LIMIT 1) LIMIT 5;
   ```
4. **Verify Conversations**: Verify historic dialogue threads read and write successfully.
5. **Verify Orders**: Verify that orders resolve to correct states and payment checkouts can be created.

---

## 3. Playbook for Pilot Incidents & Incident Owners

Every incident class has designated technical owners and target resolution parameters.

| Incident Class | Primary Owner | Secondary Owner | Escalation Path | Target Resolution |
| :--- | :--- | :--- | :--- | :--- |
| **Database Outage** | Database Engineer | Backend Engineer | Founder (after 30 min) | 15 minutes |
| **WhatsApp Gateway** | Integrations Lead | Support Lead | Founder (after 30 min) | 20 minutes |
| **AI Generation Spikes**| AI Pipeline Engineer | Backend Engineer | Founder (after 30 min) | 15 minutes |
| **Payment Gateway** | Backend Engineer | Support Lead | Founder (after 45 min) | 30 minutes |
| **Cache Outages** | DevOps Engineer | Infrastructure Lead | Founder (after 30 min) | 10 minutes |

### Incident A: Customer Cannot Upload CSV Catalog
* **Primary Owner**: Support Lead (Secondary: Backend Engineer)
* **Diagnosis**:
  1. Search Docker logs for `/api/catalog/upload` endpoints and locate transaction HTTP status.
  2. If a `500` status is logged, parse the JSON payload returned. If the detail is `Validation failed` or `Price cannot be negative`, the uploader did its job; the source data is malformed.
* **Known Fixes**:
  - *Line Ending mismatch*: Strip `\r` MacOS carriage returns using utility scripts before re-upload.
  - *Encoding mismatch*: Re-save the file explicitly as UTF-8 in Excel.
* **Escalation**: Connect the merchant to Level-2 engineering support to debug custom formatting.

### Incident B: WhatsApp Webhook / Gateway Failure
* **Primary Owner**: Integrations Lead (Secondary: Support Lead)
* **Diagnosis**:
  1. Inspect the Meta App Dashboard webhook health log.
  2. Verify the FastAPI status in container logs: `docker logs closely_backend`.
  3. Verify webhook response latency is $< 500$ ms.
* **Known Fixes**:
  - *Deduplication Hang*: If Redis is rejecting queries due to duplicate message IDs, clear the message deduplication key (`redis-cli del "webhook:dedup:<msg_id>"`).
  - *Token Expired*: If logs show `401 Unauthorized` responses from the Meta API, retrieve a new permanent Page Access Token from the Meta Developer Console and update `WHATSAPP_ACCESS_TOKEN`.

### Incident C: AI Timeout / Latency Spikes
* **Primary Owner**: AI Pipeline Engineer (Secondary: Backend Engineer)
* **Diagnosis**:
  1. Audit average time of `/ai/client` calls in Grafana metrics.
  2. Check Google GenAI API rate limits.
* **Known Fixes**:
  - *Fallback Handoff*: The system is designed to automatically transfer status to `human_takeover` if Gemini returns a timeout or exception. Confirm that manual agents are notified on-screen.

### Incident D: Payment Generation / Confirmation Failure
* **Primary Owner**: Backend Engineer (Secondary: Support Lead)
* **Diagnosis**:
  1. Verify if the Razorpay/Stripe checkout URL generator endpoint responds.
  2. Check payment webhook payloads matching `POST /api/webhooks/payments`.
* **Known Fixes**:
  - *Manual Confirmation*: If the payment webhook failed to fire but the customer has paid, the dashboard agent can manually select "Mark as Paid" to transition the conversation status and update the order state.

### Incident E: Cache Outages (Redis Outage)
* **Primary Owner**: DevOps Engineer (Secondary: Infrastructure Lead)
* **Diagnosis**: Rate limiter rejects requests; SSE connection streams are disconnected; message queue fails.
* **Known Fixes**:
  - **CAUTION**: Do **NOT** run `redis-cli FLUSHDB` in production, as this deletes active user sessions, queues, and critical state data.
  - *Selective Deletion*: Delete or expire only the specific namespace keys causing issues:
    ```bash
    redis-cli --scan --pattern "webhook:dedup:*" | xargs redis-cli del
    ```
  - *Namespace Invalidation*: Restart the rate limiting service configuration to invalidate expired windows.
  - *Service Restart*: Run `docker-compose restart redis` to restore cache memory safely.
