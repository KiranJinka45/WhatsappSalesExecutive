# Closely AI - System Architecture Design

## 1. Modular AI Pipeline Deconstruction
To ensure reliability, ease of debugging, and predictability in production, Closely AI splits the generic "AI Service" into a modular pipeline of 11 distinct components:

```
[ Incoming WhatsApp Webhook ]
            ↓
    [ 1. Intent Engine ] ────→ [ 2. Entity Extractor ]
            ↓                           ↓
    [ 3. Catalog Retriever ] ←── [ 4. Knowledge Retriever ]
            ↓                           ↓
    [ 5. Recommendation Engine ] ←── [ 6. Policy Validator ]
            ↓
    [ 7. Grounding Checker ] ──→ [ 8. Response Planner ]
            ↓                           ↓
    [ 9. Response Generator ] ──→ [ 10. Safety Validator ]
            ↓
    [ 11. WhatsApp Sender ]
```

---

## 2. Component Reference

### 1. Intent Engine
- **Responsibility**: Analyzes user message content + chat context and assigns it one of the core retail intents (e.g., `product_discovery`, `logistics`, `checkout_intent`, `human_negotiation`).
- **Tech Choice**: LLM classification (Gemini 2.5 Flash) with JSON Schema output constraint.

### 2. Entity Extractor
- **Responsibility**: Extracts key structured variables from user text such as budget limits, sizes, colors, fabric choices, and quantities.
- **Tech Choice**: LLM Structured Outputs (JSON) using Pydantic schemas.

### 3. Catalog Retriever
- **Responsibility**: Runs hybrid query using semantic embedding (pgvector) and structured filters (SQL WHERE clauses for size/price/color) to fetch the top 3-5 matching products.
- **Tech Choice**: pgvector Cosine Distance + SQLAlchemy queries.

### 4. Knowledge Retriever
- **Responsibility**: Fetches relevant snippets of policies (shipping rates, returns, exchanges, store location).
- **Tech Choice**: Key-value metadata retrieval from the Organization settings.

### 5. Recommendation Engine
- **Responsibility**: Evaluates the retrieved catalog items, customer styling/sizing profiles, and cross-references styling logic to select recommendations.
- **Tech Choice**: Python rule engine + prompt context builder.

### 6. Policy Validator
- **Responsibility**: Checks if there are missing attributes in recommendations (e.g. price, stock count, fabric) and overrides the path if a brand boundary is breached.
- **Tech Choice**: Deterministic Python validation functions.

### 7. Grounding Checker
- **Responsibility**: Ensures facts (size availability, price, color) are strictly derived from the retrieved documents.
- **Tech Choice**: Post-retrieval validation checker.

### 8. Response Planner
- **Responsibility**: Decides the goal of the response based on the current sales funnel stage (e.g. if the customer viewed a product, prompt for size to transition to "Qualified").
- **Tech Choice**: State-machine logic + state prompt injection.

### 9. Response Generator
- **Responsibility**: Generates the natural language reply using the plan, verified details, and brand persona.
- **Tech Choice**: Gemini 2.5 Flash.

### 10. Safety Validator
- **Responsibility**: Scans output text for formatting issues, missing placeholders, and toxic/unprofessional language.
- **Tech Choice**: Regex + lightweight evaluation classifier.

### 11. WhatsApp Sender
- **Responsibility**: Translates generated text into WhatsApp Cloud API JSON payloads (text, template messages, or multi-product listings) and queues them for transmission.
- **Tech Choice**: Async HTTP client (httpx) with retry queue.

---

## 3. High-Level Tech Stack
- **API Gateway & Core Framework**: FastAPI (Python 3.11+)
- **Database**: PostgreSQL with `pgvector` extension
- **Caching & State Stores**: Redis (Conversation session limits, Rate limiting)
- **Message Broker & Delivery Queue**: Celery (Background message processing, retries)
- **AI Models**: Gemini 2.5 Flash (`gemini-2.5-flash`), `text-embedding-004`
- **Containerization**: Docker & Docker Compose
