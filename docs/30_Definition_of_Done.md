# Closely AI - Definition of Done (DoD)

This document establishes the quality checklist that every feature branch must pass before it is approved for merging into the production branch.

---

## The Definition of Done Checklist

### 1. Code Quality & Formatting
- [ ] Code follows PEP8 guidelines (linted using ruff/black).
- [ ] No hardcoded passwords, credentials, or API keys (loaded exclusively via `.env`).
- [ ] Core database updates are encapsulated in an Alembic migration script.

### 2. Testing Coverage
- [ ] Unit tests written for all new service functions (pytest coverage `> 80%`).
- [ ] Integration tests written for all new API router endpoints.
- [ ] Webhook parsers tested with simulated Meta/Twilio payloads.

### 3. AI Pipeline Validation
- [ ] Prompts and system instructions verified against regression datasets.
- [ ] Grounding checks run; zero hallucination metrics confirmed.
- [ ] API latency remains within the SLA target (p95 `< 2.0s`).

### 4. Merchant Dashboard (Frontend)
- [ ] Frontend code compiles successfully via Vite without warnings.
- [ ] Oxlint rules run with zero syntax or style errors.
- [ ] Responsive design verified (tested on both desktop and mobile viewports).

### 5. Security & Isolation
- [ ] Tenant access controls are verified (queries automatically apply `organization_id` limits).
- [ ] Input parameter validation is enforced (Pydantic models reject bad payloads).
- [ ] Webhook signature verification is active for incoming gateways.

### 6. Documentation & Metrics
- [ ] API endpoints are documented in Swagger (FastAPI routers include descriptive docstrings).
- [ ] Logging metrics are implemented (`structlog` statements cover error transitions).
- [ ] The `walkthrough.md` is updated with verification logs.
