# Milestone 4 – Migration & RLS Verification Report

**Date:** 2026-08-15  
**Status:** Verified for Controlled Sandbox Pilot  

---

## 1. Migration Chain Architecture

The Alembic migration chain has been structured to allow bootstrapping from an empty PostgreSQL database:

```text
<base> → a0000000001 (Baseline schema: organizations, users, categories, products, conversations, messages, memories, orders, order_items, recommendation_feedback, approval_requests, approval_audit_logs)
       → b2fbe48c9249 (Notification table + Decision Engine schemas)
       → f6fce6b78e4f (Write RLS policies) [branchpoint]
            → bcf53b84a362 (Image embedding)
                 → c3a4b1d2e5f6 (Product SKU unique constraint)
            → e7f8a9b0c1d2 (Outbound messages table + Outbox RLS)
       → d4d1f5b38d89 (Merge branching heads)
       → a2f4c9b0e8d1 (Hardened Audit Log Immutability & RLS) ← HEAD
```

---

## 2. Migration Bootstrap Verification

- **Command Run:** `alembic upgrade head`
- **Target DB:** Clean/Empty PostgreSQL instance
- **Result:** Successfully applied all migrations from base to `a2f4c9b0e8d1`. All foreign key constraints, pgvector extensions, indexes, and initial tables created without errors.

---

## 3. Row-Level Security (RLS) Policy Verification

### Policy Strategy: Fail-Closed
- **Predicate:** `organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid`
- **Fallback Behavior:** When `app.current_tenant` is unset or empty string, `nullif` evaluates to `NULL`. Since `organization_id = NULL` evaluates to `UNKNOWN` (false), all tenant rows are hidden (0 rows returned) rather than exposing records.

### Verified Tenant-Scoped Tables (Canonical PostgreSQL Query Result)

All 14 tables in the schema are tenant-scoped, with RLS enabled and RLS forced. Privileges are granted to `closely_app` depending on target operational or audit immutability needs:

| Table Name | RLS Enabled | FORCE RLS | Policies | Privileges (`closely_app`) |
|---|---|---|---|---|
| `approval_audit_logs` | `True` | `True` | `approval_audit_logs_tenant_select_policy`, `approval_audit_logs_tenant_insert_policy` | `SELECT, INSERT` *(strictly append-only, UPDATE/DELETE denied)* |
| `approval_requests` | `True` | `True` | `approval_requests_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `categories` | `True` | `True` | `categories_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `conversations` | `True` | `True` | `conversations_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `customer_memories` | `True` | `True` | `customer_memories_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `messages` | `True` | `True` | `messages_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `notifications` | `True` | `True` | `notifications_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `order_items` | `True` | `True` | `order_items_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `orders` | `True` | `True` | `orders_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `organizations` | `True` | `True` | `organizations_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `outbound_messages` | `True` | `True` | `outbound_messages_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `products` | `True` | `True` | `products_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `recommendation_feedback` | `True` | `True` | `recommendation_feedback_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |
| `users` | `True` | `True` | `users_tenant_{select,insert,update,delete,policy}` | `SELECT, INSERT, UPDATE, DELETE` |

---

## 4. Database Role & Security Configuration

- **Application Role:** `closely_app` (Non-superuser, least-privilege table grants).
- **RLS Bypass:** Disabled. The application role cannot bypass RLS.
- **Tenant Context Setting:** Transaction-scoped `SET LOCAL app.current_tenant = :tenant_id` executed upon DB session acquisition for authenticated tenant requests.
