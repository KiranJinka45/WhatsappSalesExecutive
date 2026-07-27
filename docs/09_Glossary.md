# Closely AI - Strategic Glossary

*Status: **EVOLVING** (Updated as new technical components or operational metrics are established).*

---

## Glossary of Terms

### PCAR (Policy-Compliant Autonomous Resolution Rate)
The percentage of customer conversations that were completed autonomously while remaining within configured merchant policies and without requiring human intervention.

### False Escalation Rate
The percentage of approval requests that the merchant immediately approves without modification. Used to tune the Decision Engine; a high false escalation rate indicates the bot is unnecessarily escalating tasks it could have handled autonomously (resulting in merchant fatigue).

### E0 to E6 Evidence
A standardized classification of evidence quality from E0 (theoretical design) to E6 (long-term operational proof). Helps prevent overstating software readiness.

### L0 to L4 Autonomy
A 5-level system classification defining permissions for AI acts:
* **L0**: Read-only analytics tracking.
* **L1**: Draft suggestions for reviews.
* **L2**: Fully automated replies (FAQs, product search).
* **L3**: Risky workflows requiring merchant approval.
* **L4**: Direct merchant actions only (refunds, edits).

### Deterministic Decision Engine
A set of rule-based logical gates executing immediately before generative model outputs to ensure strict adherence to store pricing, inventory count, and shipping constraints.

### Human Handoff / Handoff Queue
The mechanism by which conversations are transferred to the merchant dashboard queue, pausing the autonomous responder when a user message exceeds policy boundaries or requests direct operator support.

### Safe Autonomy
The state where AI acts strictly within policies configured by the merchant. Handing off out-of-policy requests to a human is considered a safe and successful outcome, not an AI failure.
