# Closely AI - Production Release Checklist

This checklist defines standard deployment steps, live sanity checks, and change freeze protocols before launching a release tag to production.

---

## 1. Pre-Deployment Checks
- [ ] **Tests Green**: Ensure all CI unit, integration, and grounding tests are passing.
- [ ] **Secrets Loaded**: Verify production database strings and Gemini API keys are configured inside the cloud vault.
- [ ] **Database Backup**: Trigger manual backup of production DB before running upgrades.
- [ ] **Vector Extension**: Confirm PostgreSQL instance is initialized with `CREATE EXTENSION IF NOT EXISTS vector;`.

---

## 2. Deployment Procedures
- [ ] **Run Migrations**: Run the Alembic database migrations pipeline:
  ```bash
  alembic upgrade head
  ```
- [ ] **Deploy Containers**: Deploy new `web`, `worker`, and `frontend` Docker images.
- [ ] **Cache Flush**: Run Redis command to flush transient vector embedding keys:
  ```redis
  redis-cli FLUSHDB
  ```

---

## 3. Post-Deployment Verification (Smoke Tests)
- [ ] **Health Endpoint Check**: Verify `GET /` returns `{"status": "healthy", "version": "2.0"}`.
- [ ] **Inbound Sandbox Test**: Message the live sandbox number *"Hello"* and verify AI greeting and conversation state transitions to `GREETING`.
- [ ] **Dashboard Link Check**: Log in to dashboard and verify the active conversation feed connects via WebSockets.
- [ ] **Logs Sanity**: Monitor structured logs for database connection pool exhaust warnings or Gemini API timeout errors.

---

## 4. Change Control & Specification Freeze Protocol
Once this deployment is marked complete, the document package is officially frozen (Version 1.0).

> [!IMPORTANT]
> **Change Freeze Rules**: No modifications to the frozen documents (PRD, Architecture, DB design, API, Acceptance Criteria) are permitted without a formal Change Request process:
> 1. Submit a Change Request document proposing features/changes.
> 2. Create or update an Architecture Decision Record (ADR) detailing rationale.
> 3. Update the matching code and documentation simultaneously in a single pull request.
