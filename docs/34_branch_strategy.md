# Closely AI - Branching Strategy

This document establishes trunk-based branching rules to keep development cycles rapid, clean, and stable for our startup environment.

---

## 1. Branch Hierarchy

```
        ┌─── feature/jwt-auth ───┐
        │                        ▼
[ main ] ─────────────────────────► [ Tag: v1.0.0 (Prod Release) ]
        ▲                        ▲
        └─── feature/csv-parser ─┘
```

- **`main`**: The stable core. All code here must be deployable. Direct commits to `main` are strictly blocked.
- **Short-Lived Feature Branches (`feature/*` or `bugfix/*`)**:
  - Forked off: `main`.
  - Naming: `feature/short-description` (e.g., `feature/catalog-upload`) or `bugfix/issue-description` (e.g., `bugfix/tenant-leak-remediation`).
  - Lifespan: Target `< 3 days` to prevent major code divergence.

---

## 2. Integration & Merge Rules
1. **Pull Request Validation**: Feature branches can only merge back to `main` via an approved Pull Request.
2. **Rebase vs. Merge**: Developers should rebase their feature branch onto `main` locally before submitting a PR to maintain a linear history:
   ```bash
   git checkout feature/catalog-upload
   git pull origin main --rebase
   ```
3. **Clean Up**: Branches must be deleted automatically on GitHub and locally once merged to keep the repository history clean.

---

## 3. Hotfix Escalation Protocol
If a critical defect is identified in production (e.g., webhook handshake failure):
1. Fork `hotfix/description` directly from the active tag on `main`.
2. Apply the fix and verify against integration test suites locally.
3. Submit a PR directly to `main` with the title prefix `[HOTFIX-URGENT]`.
4. Deploy, tag the new release (e.g., `v1.0.1`), and merge changes back down.
