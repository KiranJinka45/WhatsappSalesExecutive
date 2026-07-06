# Closely AI - Codebase Repository Structure

This document details the modular directory structure of both backend and frontend components, enforcing boundaries and file placement.

---

## Codebase Directory Map

```
/whatsapp_AI Sales Employee/
├── docker-compose.yml
├── .env.example
├── docs/                      # 40 Certified Specs & Design Artifacts
│   ├── 01_PRD.md
│   └── ...
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini            # DB migration config
│   ├── alembic/               # Migration scripts
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py            # API Gateway initialization
│   │   ├── config.py          # Env loading & settings
│   │   ├── database.py        # SQLAlchemy setups
│   │   ├── models.py          # SQLAlchemy PostgreSQL models
│   │   ├── schemas.py         # Pydantic serialization models
│   │   ├── security.py        # Webhook verification & JWT auth
│   │   ├── catalog_service.py # CSV parser & validation pipeline
│   │   ├── routers/           # FastAPI Controller layer
│   │   │   ├── auth.py
│   │   │   ├── brand.py
│   │   │   ├── catalog.py
│   │   │   ├── conversations.py
│   │   │   └── webhooks.py
│   │   └── services/          # Core Business Services (Single engine)
│   │       ├── __init__.py
│   │       ├── conversation_engine.py  # Consolidated AI modules
│   │       ├── whatsapp_client.py     # Meta Cloud API client wrapper
│   │       └── payment_client.py      # Razorpay/Stripe wrapper
│   └── tests/                 # Core test directories
│       ├── conftest.py
│       ├── test_auth.py
│       ├── test_catalog.py
│       ├── test_conversations.py
│       └── test_webhooks.py
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── index.html
    ├── src/
    │   ├── main.jsx
    │   ├── App.jsx
    │   ├── components/        # Reusable dashboard UI blocks
    │   ├── services/          # API fetch wrapper calls
    │   └── views/             # Major dashboard views
    │       ├── Dashboard.jsx
    │       ├── Catalog.jsx
    │       └── LiveChat.jsx
```
---

## Directory Placement Guidelines
1. **No Modular Duplication**: All AI helper engines must reside inside `/backend/app/services/conversation_engine.py` as separate internal modules/functions (rather than independent services) to prevent premature microservice fragmentation.
2. **Migration Scripts**: All schema updates must be written inside `/backend/alembic/versions/` and generated via the CLI.
3. **Frontend Assets**: Raw templates and stylesheets must reside inside `/frontend/src/` to benefit from Vite's compilation tree.
