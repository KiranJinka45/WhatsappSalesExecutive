# Closely AI - Git Workflow Specification

This specification details standard commit naming conventions, pre-commit pipelines, and pull request procedures.

---

## 1. Conventional Commits Standard
All commit messages must adhere to the Conventional Commits format to facilitate changelog generation and automated release tracking:

```
<type>(<scope>): <short description>
```

### Type Mapping
- `feat`: A new feature introduction (e.g. `feat(auth): implement JWT registration`).
- `fix`: A bug fix (e.g. `fix(catalog): resolve duplicate SKU constraint error`).
- `docs`: Documentation updates only (e.g. `docs(specs): freeze MVP readiness docs`).
- `refactor`: Code restructuring without functional modifications.
- `test`: Adding or correcting tests.

### Format Guidelines
- **Subject Length**: Under 72 characters.
- **Tense**: Present imperative (e.g., "add filter", not "added filter").

---

## 2. Pre-Commit Hooks
Pre-commit hooks are configured using `.pre-commit-config.yaml` to block invalid commits locally:

```
[ Git Commit Triggered ]
           │
     (Ruff Check) ───[Style errors?]───► [ BLOCK COMMIT ]
           │
     (Black Check) ──[Format errors?]──► [ BLOCK COMMIT ]
           │
   (Pytest Run MVP) ─[Tests failed?]───► [ BLOCK COMMIT ]
           │
   [ Commit Approved ]
```

---

## 3. Pull Request (PR) Requirements
Before merging code into the main branch, a PR must be created. The PR template requires:

- **Summary of Changes**: 1-2 sentence technical overview.
- **Verification Logs**: Console output or test run logs proving the changes work.
- **DoD Compliance**: Checklist confirming tests are present, linting passed, and database migrations are generated.
- **Review Gate**: Must receive at least one positive code review approval.
