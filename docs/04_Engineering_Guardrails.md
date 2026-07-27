# Closely AI - Engineering Guardrails

*Status: **FROZEN** (Stable; code merge gates, operational capacity limits, and change controls).*
*Version: **v1.0.0***

---

## Engineering Guardrails

No pull requests or features will be merged into the core branch unless:

✓ **Unit tests pass**: Basic functions have coverage.
✓ **Integration tests pass**: Message pipelines run successfully in CI.
✓ **Backward compatibility**: Database changes and APIs must not break existing live deployments.
✓ **Audit logging**: Changes to user state or billing must trigger structured audit logs.
✓ **Metrics tracking**: Telemetry is added for runtime latency and failure modes.
✓ **Documentation updated**: Strategy, PRDs, and READMEs remain synced with code.
✓ **Isolation preserved**: Explicit RLS or multi-tenant database filtering checks are verified.

---

## Technical Debt Policy

* **Sprint Allocation**: Every sprint allocates **20% of engineering capacity** to stability, refactoring, writing tests, documentation, or infrastructure/operational improvements.
* **Refusal of Work**: Engineers are expected to reject feature requests that skip layer boundaries unless a documented architectural waiver is signed by the lead architect.

---

## Change Budgets (Sprint Constraints)

To prevent operational instability during active merchant pilot waves, the following limits are enforced per sprint:

| Constraint Type | Limit per Sprint | Purpose |
|---|---|---|
| **Maximum Architecture Changes** | **1** | Reduces core code churn and side effects. |
| **Maximum Schema Migrations** | **1** | Minimizes database migration risks and downtime. |
| **Maximum New Infrastructure Components** | **0** | Disallows introduction of new tools (e.g. queue brokers, search engines) during pilots. |
| **Maximum Breaking API Changes** | **0** | Guarantees external messaging endpoints remain backwards-compatible. |

---

## Policy & Environment Versioning

All live conversations must be fully reproducible for operational audits. Every chat message log must store the exact environmental variables active at the moment of response:
1. **Model & Prompt Version**: The specific LLM vendor release and prompt configuration template version.
2. **Decision Engine Code Release**: The code commit hash of the Rule Engine.
3. **Merchant Policy Version**: The configuration state active for that organization (e.g. `Policy v1.0` specifying `discount_limit = 0%`, `bulk_threshold = 10`, and `refund_requires_owner = true`).

---

## Engineering Principles

1. AI handles routine work.
2. Deterministic rules govern business-critical actions.
3. Every AI decision is auditable.
4. Every merchant has isolated data.
5. Every automation has a human override.
6. Architecture grows from customer evidence, not assumptions.

---

## "Evidence Required" Gates

To prevent accidental overstatement and keep engineering honest about feature status, we define readiness by evidence, not optimism:

| Claim | Required Evidence |
|---|---|
| **Feature Complete** | Unit + integration tests pass successfully in CI environment. |
| **Pilot Ready** | Emulator runs green, chaos scenarios handled, deterministic replay validated, operational playbooks documented. |
| **Design Partner Ready** | Successful onboarding flow executed, pilot logs monitored, and system behavior reviewed. |
| **Production Ready** | Live validation telemetry gathered, SLOs (Service Level Objectives) met, and rollback procedures tested. |
| **Enterprise Ready** | Multi-tenant leak validation completed, external security review executed, and backup/DR (Disaster Recovery) verified. |
