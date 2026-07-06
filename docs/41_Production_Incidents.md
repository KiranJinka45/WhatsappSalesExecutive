# Closely AI - Production Incident Reports

## Sprint 1 Production Bug #001

### Root Cause
A ContextVar leakage occurred in our multi-tenancy logical partitioning layer (`tenant_var` context variable). Because HTTP request threads/coroutines propagate ContextVars, when a request handler modified the tenant ID via `tenant_var.set(user.organization_id)` and completed, the context was not reset. When subsequent requests ran on the same execution path, they inherited the dirty ContextVar state.

### Impact
* **Cross-request tenant contamination**: Tenant A's session could query or modify Tenant B's data under concurrent traffic.
* **Severity**: High (Critical Security Vulnerability).

### Resolution
* Refactored the core authorization middleware and database wrappers to set context variables with a token handle, and reset it inside a strict `try/finally` block.
* Example fix:
  ```python
  token = tenant_var.set(org_id)
  try:
      # Request execution
  finally:
      tenant_var.reset(token)
  ```

### Regression Test
* Added `tests/test_tenant_isolation.py` which mocks two concurrent user sessions (`Tenant A` and `Tenant B`) executing CRUD operations, asserting that Tenant A receives HTTP 404/403 or empty listings when trying to read, modify, or delete Tenant B's entities.
