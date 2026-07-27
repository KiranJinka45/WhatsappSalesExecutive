# Closely AI - Production & Pilot Evidence

This directory stores operational validation datasets, performance metrics, and compliance audit logs. To maintain scientific rigour and prevent documentation entropy, all pilot trials are structured as follows:

```
evidence/
    pilots/
        pilot-001/                  # Unique ID for each pilot brand/boutique
            conversations/          # Anonymized conversation logs
            approval_events/        # Queue audit logs (approved/edited/rejected counts)
            merchant_feedback/      # Qualitative feedback and surveys
            incidents/              # Logs of postmortems or server failures
            metrics/                # Measured PCAR, turnaround times, and latency
            weekly_reports/         # Weekly progress logs for stakeholders
```

---

## Directory Guidelines

### 1. `conversations/`
* Stores JSON blocks of chat traces.
* **Governance Rule**: All customer names, phone numbers, and addresses must be completely scrubbed (PII stripped) prior to checking datasets into the repository.
* Each trace must contain the environmental metadata (Model version, prompt version, policy version) for full reproducibility.

### 2. `approval_events/`
* Logs the rate of manual overrides and approval queue metrics.
* Used directly to calculate the **Merchant Override Rate** and audit safety trigger accuracy.

### 3. `incidents/`
* Local markdown files detailing incident postmortems using the [Incident Postmortem Template](file:///c:/whatsapp_AI%20Sales%20Employee/docs/incident-postmortem-template.md).

### 4. `metrics/`
* Telemetry datasets calculating **Policy-Compliant Autonomous Resolution (PCAR)**, p95 latency, and CSAT scores over the pilot lifetime.
