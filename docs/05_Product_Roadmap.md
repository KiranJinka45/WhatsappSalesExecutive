# Closely AI - Product Roadmap

*Status: **EVOLVING** (Updated iteratively based on customer feedback and validated learning).*
*Version: **v1.0.0-draft***

---

## Product Maturity Gates

We do not transition stages based on timeline optimism. Progression requires concrete evidence:

```
Prototype ──> Internal Demo ──> Offline Validation ──> Design Partner Pilot ──> Pilot Success ──> General Availability
```

* **Prototype**: Initial local build and functional feasibility tests.
* **Internal Demo**: Dogfooding by internal product and engineering teams.
* **Offline Validation**: Validated against goldens, regression test suites, and compliance checks.
* **Design Partner Pilot**: Limited live deployments with highly active design partner merchants.
* **Pilot Success**: Meets phase-specific targets (onboarding speed, latency, safety metrics) over 30 days.
* **General Availability**: Scaled distribution with fully automated self-serve workflows.

---

## Assumptions Register

These core hypotheses must be explicitly validated during our upcoming pilots:

| Hypothesis / Assumption | Current Validation Status | Method of Verification |
|---|---|---|
| Boutique merchants prefer WhatsApp as their primary sales channel. | **Pending Pilot** | Active engagement tracking vs Web/Instagram requests. |
| AI catalog recommendations directly improve conversion rate. | **Pending Pilot** | A/B testing recommendation clicks vs general inquiries. |
| Merchants will review and action their approval queue promptly. | **Pending Pilot** | Measure average response time in the approval dashboard. |
| RAG grounding quality is sufficient to prevent production hallucinations. | **Pending Pilot** | Automated audit logs scanning for factual inconsistencies. |
| Recommendation ranking aligns with merchant stylistic preferences. | **Pending Pilot** | Rate of manual merchant overrides during styling calls. |

---

## Evidence-Driven Roadmap Justification

*Rule*: Every significant roadmap item should cite its evidence source. To prevent speculative feature creep, every proposed roadmap item must be justified by active production evidence or direct customer requests:

| Proposed Feature / Change | Primary Evidence Source | Priority | Status / Action |
|---|---|---|---|
| **Better discount workflow** | Merchant requested it 12 times during interview loops. | **High** | Queued for active sprint |
| **Inventory reservation** | Pilot onboarding interviews showed clear demand. | **High** | Queued for active sprint |
| **Instagram integration** | No active pilot merchant has requested this yet. | **Low** | Backlog |
| **Voice support** | No quantitative or qualitative evidence of merchant need. | **Deferred** | Parking Lot |

---

## Customer Success Roadmap

### Phase 1 (0–30 Days) — Foundation & Core Loop
* **Focus**: Merchant onboarding, basic CSV catalog parser, WhatsApp inbound loop.
* **Scope**: Product discovery, shipping info, FAQs, and human takeover workflow.
* **Exit Gate**: Verified offline testing and emulation complete.

### Release v1.1.0 — First Production Evidence (Current Sprint Focus)
* **Goal**: Establish concrete validation from real user interactions over implementing features.

#### Success Criteria for v1.1.0
To exit this era, we must achieve these exact operational milestones:
* [ ] **First Merchant Onboarded**: A partner store is live in production without developer intervention.
* [ ] **First WhatsApp Conversation**: Real user engages with the number.
* [ ] **First AI Recommendation Accepted**: Customer clicks or acts on a suggested SKU.
* [ ] **First Approval Queue Event**: Out-of-policy text is successfully intercepted.
* [ ] **First Merchant Override**: Merchant edits or rejects an AI queue suggestion.
* [ ] **First Influenced Sale**: A purchase is completed following AI catalog help.
* [ ] **First Weekly Production Report**: Consolidated metrics sent to stakeholders.
* [ ] **First Production Postmortem**: Documented using our standard template (if any incident occurs).
* [ ] **PCAR Baseline**: Measure and establish our initial safe autonomy rate.

### Phase 3 (3–12 Months) — Platform Expansion
* **Focus**: Instagram and Facebook Messenger integration, Web widget, voice support, self-serve billing.

### Phase 4 (Year 2+) — Commerce Verticals
* **Focus**: Replicating the core workforce platform to Beauty, Cosmetics, and Electronics.

---

## Expansion Rules

We protect our focus. A new industry vertical is considered only after:
* Fashion retail achieves product-market fit (PMF).
* At least 50 active paying merchants are secured.
* Repeatable, zero-touch merchant onboarding is verified.
* Stable unit economics are achieved (API/model costs vs subscription).
* Customer support playbooks are documented.
* Core platform layers remain unchanged between tenants.
