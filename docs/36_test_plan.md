# Closely AI - Test Execution Plan

This document maps out testing strategies, E2E test runs, and localized testing commands.

---

## 1. Test Levels & Coverage Targets

### Unit Testing (Coverage Target: > 80%)
- **Scope**: Catalog parsers, validation schemas, lead score helper math, security encryption functions.
- **Mocking**: External APIs (Gemini, Meta Cloud API) are fully mocked using `pytest-mock` to avoid network dependency.

### Integration Testing (Coverage Target: > 75%)
- **Scope**: FastAPI endpoint routing, database model insertions, webhook endpoint routing, and state machine updates.
- **Setup**: Run tests against a local test PostgreSQL instance (with `pgvector` enabled) and a test Redis cache inside a separate Docker network.

---

## 2. End-to-End (E2E) Flow Mocking
To test the complete conversational purchase journey without calling Meta, developers run simulated transaction tests:

```
[ Mock Customer Webhook POST ]
              │
      (Ingest Message)
              │
    (Verify conversation stage = 'CART_INTENT')
              │
   (Mock payment.captured Webhook)
              │
   (Assert order status = 'PAID')
              │
 (Assert Conversation status = 'ai_active')
```

---

## 3. Testing Commands Cheat Sheet

### Backend Tests (Pytest)
```bash
# Run the entire test suite with coverage report
docker-compose exec web pytest --cov=app tests/

# Run only catalog validation service tests
docker-compose exec web pytest tests/test_catalog.py -v
```

### AI Evaluation Suite
Runs grounding checks on a synthetic test conversation file:
```bash
# Execute evaluation script on staging context
python -m tests.evaluate_llm_grounding --dataset=tests/fixtures/eval_conversations.json
```
This script returns precision/recall metrics. A grounding score `< 98%` will fail the pipeline.
