# Closely AI - CI/CD Pipelines

This document details the automated integration and deployment workflows configured for GitHub Actions or similar runners.

---

## 1. Continuous Integration (CI) Workflow
The CI pipeline executes on every Pull Request (PR) targeted at the `main` branch to guarantee compile safety and test compliance.

```
[ Developer Opens PR ]
          │
  ┌───────┴───────┐
  ▼               ▼
[ Lint Checks ] [ Build Verifications ]
- Ruff (Python) - Docker builds
- Oxlint (JS)   - Vite frontend build
  │               │
  └───────┬───────┘
          ▼
   [ Pytest Runs ]
- Execute unit tests
- Execute integration tests
- Calculate coverage (>80%)
          │
    [ PR Approved ]
```

---

## 2. Continuous Deployment (CD) Workflow
The CD pipeline executes automatically upon a merge to `main` (Staging deploy) or when a release tag is pushed (Production deploy).

### Phase A: Staging Deployment (Auto-run on merge to `main`)
1. **Build Container Images**: Compile Docker images for `web`, `worker`, and `frontend`.
2. **Push to Container Registry**: Push tagged images to private registry (e.g., AWS ECR or Docker Hub) using commit SHA.
3. **Database Migration Upgrade**: Run `alembic upgrade head` in the staging container.
4. **Deploy Containers**: Deploy new images to the staging server.

### Phase B: Production Deployment (Run on Tag Push e.g., `v*`)
1. **Promote Staging Images**: Re-tag stable staging images as `latest` and target release tag.
2. **Database Migration Upgrade**: Run production migrations.
3. **Rolling Deploy**: Perform rolling deployment on the production cluster to ensure zero downtime during webhook operations.
4. **Flush Cache**: Clear specific Redis vector search keys to force fresh cache generation.
