# ADR 0005: Multi-Tenant Logical Partitioning

## Context
Closely AI must support thousands of merchants. Tenant data (catalog, client chats, configuration) must be kept strictly isolated to maintain security and satisfy compliance rules.

## Decision
Implement a multi-tenant model using **Logical Partitioning** via an `organization_id` column on all tenant-specific tables.
* A single shared database cluster serves all tenants.
* Custom database filters (via SQLAlchemy base queries) are implemented to automatically append `WHERE organization_id = tenant_id` to all queries, preventing cross-tenant leakage.

## Alternatives Considered
* **Database-per-tenant**: Rejected due to high infrastructure cost and slow connection pooling at scale.
* **Schema-per-tenant**: Rejected due to migration overhead when running updates.

## Consequences
* Fast onboarding and cost-effective scaling.
* Developers must remain highly disciplined (CI checks verify RLS or column filters are correctly applied).

## Status
Accepted
