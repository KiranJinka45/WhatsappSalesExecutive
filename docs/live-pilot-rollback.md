# Live Pilot Rollback & Emergency Containment Guide

**Date:** 2026-08-16  
**Document Version:** 1.1  
**Target Environment:** Limited Live Boutique Pilot

---

## 1. Kill Switch Lifecycle & Immediate Containment

### Preflight & Live Lifecycle
- **Preflight State:** Tenant kill switch is **ON**. Every outbound send attempt is strictly blocked.
- **Activation:** Owner manually switches tenant kill switch **OFF** immediately before first live approved send.
- **Emergency Activation (Rollback):** If an anomaly, provider loop, catalog error, or security alert occurs:
  1. **Activate Kill Switch:** Toggle `emergency_kill_switch` to `true` in Merchant Dashboard or via API:
     ```bash
     curl -X PUT "https://app.closelyai.com/api/brand/profile" \
          -H "Authorization: Bearer <OWNER_JWT>" \
          -H "Content-Type: application/json" \
          -d '{"policies": {"emergency_kill_switch": true}}'
     ```
  2. **Effect:** Immediately halts all outbound dispatches at the transaction entry layer.

### Step 2: Transition All Active Conversations to `HUMAN_TAKEOVER`
```sql
UPDATE conversations
SET status = 'HUMAN_TAKEOVER',
    escalation_reason = 'EMERGENCY_PILOT_PAUSE'
WHERE organization_id = :pilot_org_id
  AND status = 'AI_ACTIVE';
```

---

## 2. Security Migration Forward-Only Policy

- Migration `a2f4c9b0e8d1` is strictly **forward-only**. Running `alembic downgrade` raises a `RuntimeError`.
- If database rollback is needed, restore from pre-migration WAL database snapshot.

---

## 3. Post-Rollback Protocol

1. Export `approval_audit_logs` for incident analysis.
2. Confirm zero unapproved messages were dispatched.
3. Conduct Root Cause Analysis (RCA) before resuming operations.
