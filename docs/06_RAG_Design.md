# Closely AI - Retrieval-Augmented Generation (RAG) Design

This document details the hybrid search strategy, policy grounding, and context window pruning rules that drive the Closely AI product retrieval pipeline.

---

## 1. Catalog Hybrid Search Architecture
To prevent the LLM from making irrelevant recommendations or displaying options unavailable in the customer's size, the retrieval layer combines **vector semantic search** with **strict SQL filters**:

```
[ Natural Language Query: "Green linen shirt under 2000 in XL" ]
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
    [ Vector Search ]        [ Entity Parsing ]
 (text-embedding-004)        (Color=green, Fabric=linen, 
             │                MaxPrice=2000, Size=XL)
             │                       │
             └───────────┬───────────┘
                         ▼
        [ Hybrid SQL Query Planner ]
      - Apply metadata constraints (WHERE clauses)
      - Rank results by pgvector cosine similarity
                         ▼
        [ Filtered Catalog Context List ]
```

### PostgreSQL Execution Plan
```sql
SELECT id, sku, name, price, color, fabric, sizes, stock_count, image_urls
FROM products
WHERE organization_id = :org_id
  AND stock_count > 0                    -- Filter out of stock items
  AND price <= :max_price                -- Price ceiling
  AND :size = ANY(sizes)                 -- Strict size match
ORDER BY embedding <=> :query_embedding  -- Cosine distance similarity
LIMIT 5;
```

---

## 2. Policy Grounding & Knowledge Integration
Policies are not stored as massive, unindexed PDF text blocks. Instead, they are organized as structured JSON keys in the `Organization` table:

```json
{
  "shipping": {
    "standard_rate": 100,
    "free_shipping_threshold": 3000,
    "delivery_timeline_days": "3-5 business days"
  },
  "returns": {
    "policy_window_days": 7,
    "conditions": "Tags must be intact, unwashed apparel, return shipping self-serve",
    "refund_method": "Store credit only"
  },
  "cod": {
    "available": true,
    "additional_cod_charge": 50
  }
}
```

### Context Selection Logic
1. If the `Intent Engine` classifies the query as `logistics`, the system fetches the *full* policy block and injects it into the generator prompt.
2. If the intent is `product_discovery`, only the standard shipping rates are injected as brief prompt footers to avoid using too many tokens.

---

## 3. Context Pruning & Re-ranking Rules
To optimize prompt efficiency and stay within latency targets, the pipeline applies strict context pruning:

* **Stock Threshold Pruning**: Drop any product where `stock_count` is 0 from recommendation context, unless the user explicitly asked: *"Is SKU-123 back in stock yet?"*
* **Diversity Re-ranking**: If the top 3 vector matches are identical styles in different colors, the retriever selects the top match, and then grabs the next most relevant *distinct* SKU styles to show diversity.
* **Context Budgeting**: Cap catalog prompt token counts at 1,500 tokens. This leaves room for the last 10 messages of conversation history in the Gemini 2.5 context window.
