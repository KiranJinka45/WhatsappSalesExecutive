# Closely AI - Catalog Standards & Validation Pipeline

To ensure the AI recommendation engine operates with high-quality product listings, Closely AI enforces a strict validation pipeline for catalog CSV/Excel uploads. 

---

## 1. Catalog File Specifications

### Required CSV Columns & Formats
- `sku` (String): Unique identifier. No spaces.
- `name` (String): Public-facing title of the product.
- `price` (Decimal/Numeric): Positive number, no currency symbols.
- `color` (String): Primary color of the garment.
- `category` (String): Product classification.
- `fabric` (String): Fabric composition (e.g. "Pure Linen", "Cotton Blend").
- `sizes` (String): Comma-separated list (e.g., "S,M,L,XL").
- `stock_count` (Integer): Non-negative stock count.
- `image_urls` (String): Comma-separated list of fully qualified HTTP/HTTPS URLs.

---

## 2. Validation Pipeline Schema
When a catalog file is uploaded, the system parses it and passes each row through the validation filter before writing to the database:

```
[ Uploaded CSV File ]
         │
  (Header Check) ───[Missing Required Headers?]──► [ REJECT FILE ]
         │
    (Row Loop)
         │
   (Validations)
   - Price Missing/Non-numeric?
   - Duplicate SKU?
   - Empty Category/Fabric?
   - Missing Stock Count?
   - Invalid Image URLs?
         │
         ├───[Errors Found?]──► Collect Row Errors
         │
  (Final Check)
         ├───[Any Errors Collected?]──► [ REJECT UPLOAD ] & Return Errors JSON
         └───[Zero Errors?]──────────► [ COMMIT TO DB ] & Generate Embeddings
```

---

## 3. Strict Reject Criteria

| Violation Type | Reason for Rejection | Pipeline Behavior |
| :--- | :--- | :--- |
| **Missing SKU** | Product identifier is absent. | Reject Row |
| **Duplicate SKU** | SKU already exists in this file or organization. | Reject Row (or full file if duplicate is within the upload) |
| **Missing/Zero Price** | Price is empty, non-numeric, or `<= 0.00`. | Reject Row |
| **Empty Category** | Category field is blank. | Reject Row |
| **Empty Fabric** | Fabric field is blank (vital for clothing RAG queries). | Reject Row |
| **Missing Stock** | Stock is empty or `< 0`. | Reject Row |
| **Bad Image URL** | URL does not begin with `http://` or `https://`. | Reject Row |

### Example Error Validation JSON Response
```json
{
  "status": "failed",
  "total_rows_evaluated": 150,
  "errors_count": 3,
  "errors": [
    { "row": 14, "sku": "SKU-404", "field": "price", "message": "Price is empty or invalid" },
    { "row": 32, "sku": "SKU-999", "field": "fabric", "message": "Fabric material type is required" },
    { "row": 105, "sku": "SKU-123", "field": "image_urls", "message": "URL 'invalid-url' is not a valid HTTP/HTTPS format" }
  ]
}
```
If *any* row fails, the database transaction is rolled back, protecting the catalog integrity.
