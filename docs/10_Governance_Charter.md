# Closely AI - Documentation Governance Charter

*Status: **FROZEN** (Meta-rules governing all documentation changes).*
*Version: **v1.0.0***

> **Governance v1.0.0 is frozen. Changes to frozen documents require either production evidence or an explicit strategic decision. Documentation should not expand in anticipation of hypothetical future requirements.**

---

## Documentation Meta-Rules

Documentation is treated as an operational asset. To prevent strategic and technical documentation drift, updates must follow these strict criteria:

### 1. Frozen Governance Documents (Class A)
* **Documents**: `00_Mission_Vision_Strategy.md` (Vision & Mission), `01_Product_Principles.md`, `02_AI_Constitution.md`, `03_Architecture_Principles.md`, `04_Engineering_Guardrails.md`, `10_Governance_Charter.md`, `12_Pilot_Readiness_Checklist.md`.
* **Modification Rules**:
  * Cannot be updated based on hypothetical improvements or general ideas.
  * Changes require either:
    1. **Production evidence**: Verifiable telemetry, postmortem logs, or system constraint evidence showing a flaw.
    2. **Executive strategy decision**: A formal company-wide pivot approved by executive stakeholders.

### 2. Evolving Strategy & Execution Documents (Class B)
* **Documents**: `05_Product_Roadmap.md`, `06_AI_Quality_Framework.md`, `07_Evidence_Maturity_Model.md`, `08_Operational_Governance.md`, `09_Glossary.md`.
* **Modification Rules**:
  * Changes are driven by pilot outcomes, customer feedback metrics, and operational performance telemetry.
  * Can be edited during sprint reviews or retrospective cycles based on real-world verification.

### 3. Deletion Bias
* **Rule**: Bias toward deleting rather than adding. To maintain system clarity and keep operations lightweight, teams must actively:
  * Remove unused policies.
  * Remove unused prompts.
  * Remove unused feature flags.
  * Remove unused metrics.
  * Remove unused documentation.
  * Remove abandoned roadmap items.

No document should be updated merely because a "better idea" exists.

---

## Semantic Versioning for Governance

We apply semantic versioning (`vMajor.Minor.Patch`) to all Class A frozen documentation:
* **Major Version (`v1.0.0` to `v2.0.0`)**: Large strategic pivots, restructuring of the business model, or complete architectural shifts.
* **Minor Version (`v1.0.0` to `v1.1.0`)**: Refinements to principles, added categories in lists, or addition of governance parameters.
* **Patch Version (`v1.0.0` to `v1.0.1`)**: Text formatting, clarifications, correcting typos, and fixing hyperlinks.

---

## Annual Review Cadence

To ensure documents stay relevant without causing churn, the following audit schedule is enforced:

| Document | Review Frequency | Primary Driver |
|---|---|---|
| **Mission & Vision** | Annual | Strategic Alignment |
| **Product Principles** | Annual | Product Market Fit |
| **AI Constitution** | Annual | Regulatory Changes or Safety Standards |
| **Architecture Principles**| Semiannual | Production Evidence & Core Telemetry |
| **Engineering Guardrails**| Quarterly | CI/CD Metrics, Codebase Complexity |
| **Product Roadmap** | Monthly | Sprint Validation, Customer feedback |
| **AI Quality Framework** | Monthly | LLM evaluation benchmarks, CSAT sweeps |
| **Evidence Maturity Model**| Quarterly | Test harness changes, tooling improvements |
| **Operational Governance**| Quarterly | Team scale, process improvements |
| **Glossary** | As needed | Codebase changes |

---

## Connecting Governance to CI

Our documentation guidelines are programmatically validated where possible inside our CI pipeline:
1. **ADR Validation**: Any ADR referenced in code comments (e.g. `// ADR-0004`) must map to a valid markdown file in `docs/adr/`.
2. **API Verification**: Architectural modifications affecting request/response formats must match the corresponding OpenAPI specifications before merge.
3. **Telemetry & Dictionary Compliance**: Telemetry changes must be synced with the metrics dictionary, failing builds if new metrics lack documentation.
4. **Approval Workflow Compliance**: Merges adding custom decision flows must provide offline emulator tests demonstrating the L3/L4 escalation paths.

---

## Primary Milestone: v1.1.0 — First Production Evidence

All technical and strategic sprint work aligns toward this single execution target:

### Exit Criteria:
* **Meta Cloud API Integration**: Real WhatsApp messages routed successfully in production env.
* **First Boutique Onboarded**: Active partner using Closely AI without engineering intervention.
* **First Production Conversations**: Real customer-bot chats completed.
* **PCAR Baseline**: Policy-Compliant Autonomous Resolution (PCAR) rate measured from live production logs.
* **Approval Queue Exercised**: Merchant active in approving/editing/rejecting escalated messages.
* **False Escalation Baseline**: First baseline established for automated vs manual triggers.
* **Incident Logged**: First production incident (if any) resolved and documented via standard postmortem templates.
* **Weekly Report**: Weekly operational evidence review completed.
* **Valuation Checked**: At least one pilot partner confirms the product saves measurable time or improves sales.

---

## Weekly Executive Review

Every Friday (or after each pilot cycle), the team produces a one-page summary focused purely on evidence:

```
Weekly Executive Review

Merchant Count: [X active]
Conversation Volume: [Total messages received / processed]
PCAR: [Safe autonomous resolution rate %]
Merchant Overrides: [Total overrides count & % of queued messages]
False Escalations: [Total false escalations count & % of queued messages]
Approval Turnaround: [Median queue delay in minutes]
CSAT: [Average customer satisfaction / 5]
Conversion: [Funnel percentage / sales generated value]
Revenue: [MRR / influenced transaction value]
Incidents: [P0/P1 logs and resolution status]

Top 5 Merchant Requests:
1. ...

Engineering Actions:
1. ...

Roadmap Decisions:
1. ...
```

---

## Three Reviews After Every Pilot

Every pilot cycle must conclude with three distinct evaluations to inform the next iteration:

### 1. Technical Review
* **Key Questions**: What failed? What was slow? What generated incidents? Which rules fired most?

### 2. Merchant Review
* **Key Questions**: What saved the most time? What frustrated them? Which approvals felt unnecessary? Which approvals were missing?

### 3. Business Review
* **Key Questions**: Did conversations increase? Did conversions increase? Did workload decrease? Would they pay? Would they recommend it?

---

## What NOT to Measure

To prevent metrics bloat, we explicitly ignore the following indicators as measures of customer value:
* Lines of code (LoC)
* Number of custom prompts written
* Number of underlying LLM models in use
* Number of individual agent configurations
* Total documentation files created
* Test execution count (once baseline platform stability is verified)

---

## Technical Directive

> **Governance v1.0.0 is frozen. Architectural changes now require production evidence or an approved strategic decision. The team's primary objective is to acquire production evidence through design-partner pilots, measure business outcomes, and allow empirical results—not assumptions—to drive the roadmap.**
