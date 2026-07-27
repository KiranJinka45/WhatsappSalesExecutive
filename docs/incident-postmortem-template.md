# Operational Postmortem: [Incident ID / Short Title]

## Metadata

| Property | Value / Detail |
|---|---|
| **Incident ID** | INC-YYYY-MM-DD-XX |
| **Owner** | [Name / Lead Engineer] |
| **Status** | [Draft / Under Review / Completed] |
| **Customer Impact** | [Total customers affected, messaging failures, duration of impact] |
| **Merchant Impact** | [Number of boutiques affected, financial risk, dashboard outage duration] |

---

## Executive Summary

Provide a 2-3 sentence overview of what went wrong, why it happened, what the customer/merchant experienced, and how it was fixed.

---

## Timeline (All times in UTC)

* **HH:MM** - Root cause change deployed / Event triggered.
* **HH:MM** - Incident starts (first customer failure, latency spike, etc.).
* **HH:MM** - Detection (alert triggers, or manual report received).
* **HH:MM** - Response team assembled.
* **HH:MM** - Root cause identified.
* **HH:MM** - Mitigation deployed / Rollback initiated.
* **HH:MM** - Verification checks green; incident resolved.

---

## Detection

* How was the incident first detected? (e.g. automated alert, merchant email, customer complaint).
* Did existing monitoring fire? If not, what dashboard/alert gap existed?

---

## Root Cause Analysis (RCA)

Provide a detailed explanation of the technical failure mode. Utilize the **5 Whys** method to trace the issue to its root.

### The 5 Whys
1. **Why** did the system fail? (e.g. The database query timed out).
2. **Why** did it timeout? (e.g. It was scanning a table without an index).
3. **Why** was there no index? (e.g. The migration failed to run in the staging env).
4. **Why** did the migration fail to run? (e.g. CI did not block on missing migration verification).
5. **Why** did CI not block? (e.g. The check was disabled in staging config).

---

## Contributing Factors

List any environmental, structural, or code-related circumstances that contributed to the severity, duration, or scope of the incident.

* e.g., Missing fallback path to human operators.
* e.g., Meta API rate limits blocked our normal notification channels.

---

## Corrective Actions (Fixing the Incident)

What actions were taken immediately to resolve the customer/merchant impact?

* e.g., Rolled back commit `abc1234`.
* e.g., Scaled Redis read replicas.

---

## Preventive Actions (Preventing Reoccurrence)

What long-term changes are required to ensure this specific incident class cannot happen again? Map these directly to **Evidence Levels (E1-E3)**:

| Action Item | Owner | Target Date | Verification Method (CI/Code) |
|---|---|---|---|
| Add CI migration validation check | [Name] | YYYY-MM-DD | E1 unit test checks for pending migrations |
| Build index on target organization table | [Name] | YYYY-MM-DD | E2 integration test executes hybrid queries |

---

## Evidence

Attach links to logs, trace telemetry, screenshots of metrics dashboards, or customer chat records showing the incident timeline and verification tests.
