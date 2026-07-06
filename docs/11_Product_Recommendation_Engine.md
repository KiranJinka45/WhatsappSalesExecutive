# Closely AI - Product Recommendation Engine

This specification defines the logic rules, style coordinating parameters, and size verification workflows used by the recommendation engine.

---

## 1. Size Verification Workflow
A primary cause of cart abandonment and returns in e-commerce is sizing mismatches. The recommendation engine applies a strict filter before any product is surfaced to the customer:

```
[ Catalog Retrieval Matches ]
             │
     (Extract User Size)
    - Query database memory
    - Default to user size input (e.g., "M")
             │
      (Filter Check)
      - Is UserSize in product.sizes?
      - Is product.stock_count > 0?
             ├─► YES: Retain in recommendation list
             └─► NO: Drop from recommendations list
```

---

## 2. Apparel Styling & Coordinating Rules
To elevate the product beyond simple keyword search, the engine integrates styling heuristics that mimic a human boutique assistant:

### Color Coordinating Engine
- **Neutral + Vibrant**: Pair neutral colored bottoms (Beige, Off-White, Black) with vibrant tops (Crimson, Mustard, Emerald).
- **Monochromatic Pairings**: If user searches for a styling set, recommend secondary colors within the same tone profile.

### Fabric Harmonization
- **Cotton + Cotton**: Do not pair premium silk Kurtis with casual linen pants. Match fabric weights and wash cares.
- **Dry-clean vs Machine-wash**: Ensure recommended matching sets have identical cleaning guidelines to prevent customer care issues.

---

## 3. Visual Similarity Search (Moat Integration)
To implement a robust competitive moat, Closely AI integrates visual search capabilities. If a customer uploads an image (e.g. *"Do you have something like this dress?"*):

```
[ Customer sends image via WhatsApp Webhook ]
                      │
            (Download media URL)
                      │
        (Gemini Multimodal Embedding API)
      - Generate 768-dim image embedding
                      │
           (Vector Similarity Query)
    - Search products.image_embeddings table
                      │
         (Top 3 Visual Matches Returned)
```

### Visual Search Schema Hook
To support visual search, the `products` table contains a separate visual vector column:
```sql
ALTER TABLE products ADD COLUMN image_embedding VECTOR(768);
CREATE INDEX idx_products_image_embedding ON products USING hnsw (image_embedding vector_cosine_ops);
```
- **Embedding Model**: Gemini 2.5 Flash multimodal vision or Google multimodal embedding model.
