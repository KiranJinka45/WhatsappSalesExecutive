# Closely AI - Database Schema Design

## 1. Unified Entity Relationship Diagram (ERD)
The schema is optimized for multi-tenancy, vector searching (pgvector), customer profiling, sales attribution, and real-time conversation state tracking.

```
[ organizations ] 
   │
   ├── [ users ]
   ├── [ categories ]
   ├── [ products ] (pgvector)
   ├── [ customer_memory ]
   ├── [ catalog_validation_reports ]
   └── [ conversations ]
          │
          ├── [ messages ]
          └── [ orders ]
```

---

## 2. PostgreSQL Schema Specifications

### `organizations`
Stores tenant business information, shipping parameters, and policies.
```sql
CREATE TABLE organizations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    logo_url TEXT,
    address TEXT,
    whatsapp_number VARCHAR(20) UNIQUE,
    policies JSONB DEFAULT '{}'::jsonb, -- shipping, returns, exchange, FAQ
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### `products`
Stores clothing inventory with size arrays, multi-image lists, and text embeddings.
```sql
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    category_id UUID REFERENCES categories(id) ON DELETE SET NULL,
    sku VARCHAR(100) NOT NULL,
    name VARCHAR(255) NOT NULL,
    gender VARCHAR(50), -- 'Men', 'Women', 'Unisex'
    price NUMERIC(10, 2) NOT NULL,
    color VARCHAR(100) NOT NULL,
    fabric VARCHAR(255),
    description TEXT,
    sizes VARCHAR(50)[] DEFAULT ARRAY[]::VARCHAR[], -- ['XS', 'S', 'M', 'L']
    stock_count INTEGER DEFAULT 0,
    image_urls TEXT[] DEFAULT ARRAY[]::TEXT[],
    video_urls TEXT[] DEFAULT ARRAY[]::TEXT[],
    embedding VECTOR(768), -- pgvector storage for Gemini text-embedding-004
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(organization_id, sku)
);
CREATE INDEX idx_products_embedding ON products USING hnsw (embedding vector_cosine_ops);
```

### `conversations`
Tracks the conversation state machine and AI sales qualification metrics.
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_phone VARCHAR(20) NOT NULL,
    customer_name VARCHAR(255),
    status VARCHAR(50) DEFAULT 'ai_active', -- 'ai_active', 'human_takeover', 'resolved'
    assigned_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    
    -- Sales Funnel & Lead Scoring Data
    sales_funnel_stage VARCHAR(50) DEFAULT 'VISITOR', -- 'VISITOR', 'INTERESTED', 'QUALIFIED', 'PRODUCT_VIEWED', 'CART_INTENT', 'ORDER_CREATED', 'PAID', 'DELIVERED', 'REPEAT'
    purchase_probability NUMERIC(3, 2) DEFAULT 0.00, -- 0.00 to 1.00
    interest_score INTEGER DEFAULT 0, -- 0 to 100
    budget_score INTEGER DEFAULT 0,
    urgency_level VARCHAR(20) DEFAULT 'LOW', -- 'LOW', 'MEDIUM', 'HIGH'
    sentiment_score NUMERIC(3, 2) DEFAULT 0.00, -- -1.00 to 1.00
    
    current_state VARCHAR(100) DEFAULT 'GREETING', -- Conversational State Machine
    summary TEXT, -- Session memory rollup
    metadata JSONB DEFAULT '{}'::jsonb, -- dynamic attributes (sizing, items discussed)
    
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_conv_org_phone ON conversations(organization_id, customer_phone);
```

### `customer_memory`
Long-term preference profile used for personalizing recommendations.
```sql
CREATE TABLE customer_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    customer_phone VARCHAR(20) NOT NULL,
    sizing_profile JSONB DEFAULT '{}'::jsonb, -- e.g., {"top": "M", "bottom": 32}
    fabric_preferences VARCHAR(100)[] DEFAULT ARRAY[]::VARCHAR[],
    favorite_colors VARCHAR(100)[] DEFAULT ARRAY[]::VARCHAR[],
    purchase_history JSONB DEFAULT '[]'::jsonb,
    lifetime_value NUMERIC(12, 2) DEFAULT 0.00,
    last_interaction TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(organization_id, customer_phone)
);
```

### `orders`
Attributes sales directly to AI interaction context.
```sql
CREATE TABLE orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    customer_phone VARCHAR(20) NOT NULL,
    items JSONB NOT NULL, -- [{"sku": "SKU-1", "qty": 1, "price": 999.00, "size": "M"}]
    total_amount NUMERIC(10, 2) NOT NULL,
    payment_status VARCHAR(50) DEFAULT 'PENDING', -- 'PENDING', 'PAID', 'REFUNDED'
    payment_link TEXT,
    delivery_status VARCHAR(50) DEFAULT 'UNFULFILLED', -- 'UNFULFILLED', 'SHIPPED', 'DELIVERED'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

### `catalog_validation_reports`
Holds file compliance histories for CSV uploads.
```sql
CREATE TABLE catalog_validation_reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL, -- 'PASSED', 'FAILED'
    errors JSONB DEFAULT '[]'::jsonb, -- list of row-level errors
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```
