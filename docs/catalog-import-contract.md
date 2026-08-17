# Closely AI - Catalog Import Contract & Schema Specification

---

## 1. Required Fields & Schema Validation Rules

Every CSV or Google Sheet inventory import must conform to the following schema contract:

| Field Name | Type | Required | Validation Rules | Description |
|---|---|---|---|---|
| `sku` | String | **Yes** | Unique per tenant, 3–50 chars, alphanumeric | Stock Keeping Unit identifier |
| `name` | String | **Yes** | 2–150 chars | Product title (e.g. *Kanchipuram Silk Saree*) |
| `price` | Float | **Yes** | Positive float > 0.00 | Item retail price (INR) |
| `stock_count` | Integer | **Yes** | Non-negative integer ≥ 0 | Current available stock quantity |
| `category` | String | **Yes** | Standard apparel type (*Saree, Kurti, Lehenga, Blouse, Suit*) | Category classification |
| `size` | String | Optional | Standard sizes (*S, M, L, XL, XXL, Free Size*) | Available size options |
| `color` | String | Optional | Color name (e.g. *Maroon, Red, Gold, Teal*) | Dominant color |
| `fabric` | String | Optional | Fabric material (*Silk, Cotton, Georgette, Linen*) | Material type |
| `image_url` | String | Optional | Valid HTTP/HTTPS image URL | Direct product photo link |

---

## 2. Ingestion Error Handling & Summary Report Format

When a CSV catalog is uploaded, the parser returns a structured validation payload:

```json
{
  "total_rows_parsed": 120,
  "successful_imports": 115,
  "failed_rows_count": 5,
  "errors": [
    {
      "row_number": 14,
      "sku": "SKU-994",
      "field": "price",
      "error": "Price must be a positive number greater than 0. Received: -50.00"
    },
    {
      "row_number": 42,
      "sku": "",
      "field": "sku",
      "error": "Required field 'sku' is missing or empty"
    }
  ]
}
```

### Ingestion Safety Rules
1. **Atomic Import Option**: If invalid rows exist, the merchant can choose to proceed with importing valid rows while downloading an Error Report CSV, or abort the import.
2. **Deterministic Overwrite**: Re-uploading an existing SKU updates its price, stock, color, size, and fabric details deterministically without creating duplicate records.
