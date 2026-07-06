# Closely AI - Deployment & Infrastructure Design

This document details the production containerization layout, scaling strategy, Alembic migrations configuration, and Redis caching topology.

---

## 1. Production Topology
The Closely AI backend runs as a containerized microservice group managed via Docker Compose or Kubernetes:

```
                  [ HTTPS Webhook Requests ]
                              │
                     [ Nginx Reverse Proxy ]
                              │
                 [ FastAPI App (Uvicorn / Gunicorn) ]
                              │
            ┌─────────────────┼─────────────────┐
            ▼                 ▼                 ▼
     [ PostgreSQL ]        [ Redis ]    [ Celery Worker ]
      (pgvector)        (Cache & Sessions) (Outbound Queue)
```

---

## 2. Docker Compose Configuration
The default `docker-compose.yml` configures the primary services:

- **web**: FastAPI backend app.
- **db**: PostgreSQL database enabled with pgvector.
- **redis**: Caching backend and message broker for Celery.
- **worker**: Background task engine processing API calls to WhatsApp and Gemini.

---

## 3. Database Migration Pipeline
To update the database schema without destroying customer records:

1. **Alembic integration**: Initialize Alembic in the backend repository root.
2. **Migration command**:
   ```bash
   alembic revision --autogenerate -m "Add lead scoring and customer memory tables"
   alembic upgrade head
   ```
3. **CI/CD Hook**: Add `alembic upgrade head` to the Docker container startup lifecycle script before spawning the Uvicorn web service.

---

## 4. Redis Caching Topology

### Vector Search Cache
- **Concept**: If two users query the catalog with identical strings (e.g. *"Red silk saree"*), we cache the resulting vector embedding list for 1 hour to skip the Gemini embedding generation API latency.
- **Cache Key format**: `embedding:query:<sha256_hash_of_query_text>`

### Chat Session & Funnel State Caching
- **Concept**: Conversation state context maps are mirrored in Redis to avoid querying PostgreSQL multiple times per webhook payload.
- **TTL**: 24 hours.
- **Cache Key format**: `session:org:<org_id>:phone:<phone>`

---

## 5. Environment Secrets Checklist
A checklist of variables required in the production `.env` file:
- `DATABASE_URL`: Connection string with `postgresql+psycopg2://`
- `REDIS_URL`: Redis URI
- `GEMINI_API_KEY`: API key for model executions
- `WHATSAPP_VERIFY_TOKEN`: Webhook handshake string
- `WHATSAPP_API_TOKEN`: Meta Cloud API System Token
- `WEBHOOK_APP_SECRET`: Meta App secret used for signature verification
- `JWT_SECRET`: For dashboard authorization
