# Closely AI - Coding Standards

This document establishes style guidelines, syntax requirements, and quality expectations across backend and frontend development.

---

## 1. Backend Standards (Python 3.11+)

### Style & Linting
- **Formatter**: Ruff and Black.
- **Rules**: Strict conformance with PEP 8.
- **Type Hinting**: Required on all function signatures, including arguments and return values.
  ```python
  def calculate_lead_score(interest: int, sentiment: float) -> float:
      return round((interest * 0.6) + (sentiment * 0.4), 2)
  ```

### API Serialization & Validation
- **Pydantic**: All request bodies and response items must map to explicit Pydantic schemas (inheriting from `pydantic.BaseModel`).
- **Input Validation**: Never trust client inputs. Utilize Pydantic field validators to parse prices, SKUs, and telephone numbers.

### Error Handling & Logging
- **Bare Excepts**: Forbidden. Explicitly catch anticipated exceptions (e.g. `sqlalchemy.exc.IntegrityError`, `google.genai.errors.APIError`).
- **Structured Logging**: Use `structlog` or standard logging with JSON formatting to output key-value context (e.g., `logger.error("Database query failed", org_id=org_id, error=str(e))`).

---

## 2. Frontend Standards (React + JavaScript)

### Formatting & Syntax
- **Linter**: Oxlint / ESLint.
- **Setup**: React 18+ functional components with hooks.
- **Prop Validation**: Enforce typing checks or JSDoc headers for component variables.

### State & Performance Management
- **State Scope**: Keep state as local as possible. Do not lift state globally unless multiple views (e.g., Catalog and Dashboard) require synchronized values.
- **Vite Build**: Zero compilation warnings allowed in production builds.
- **CSS Styling**: Maintain vanilla CSS layouts or HSL variable utility classes in `index.css`. Ad-hoc tailwind utility overrides are prohibited.
