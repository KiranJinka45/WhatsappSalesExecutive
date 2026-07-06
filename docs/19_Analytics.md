# Closely AI - Business Analytics & Conversion Metrics

This specification details the SQL aggregation queries, dashboard charts, and metrics definitions that run the analytics dashboard.

---

## 1. Analytics Dashboard Metrics Definition

- **Revenue Influenced**: Total sales revenue processed from transactions that occurred inside an active conversation session.
- **AI-Closed Orders**: Orders successfully paid where the conversation state stayed `ai_active` without shifting to `human_takeover`.
- **Cart Abandonment Rate**: The count of conversations that reached `CART_INTENT` or `ORDER_CREATED` stages but did not result in a `PAID` transaction within 24 hours.
- **Recovery Rate**: The percentage of abandoned carts successfully converted to `PAID` after the scheduler dispatched a recovery message.
- **Top Objections**: Classification of takeovers based on the trigger intent (e.g., pricing complaints, shipping delivery limits, sizing fears).

---

## 2. Business SQL Analytics Aggregations

### Revenue Influenced & Sales Attribution
```sql
SELECT 
    o.name AS organization_name,
    COUNT(ord.id) AS total_orders,
    SUM(ord.total_amount) AS revenue_influenced,
    COUNT(CASE WHEN conv.status = 'ai_active' THEN 1 END) AS ai_closed_orders,
    COUNT(CASE WHEN conv.status = 'human_takeover' THEN 1 END) AS human_assisted_orders
FROM orders ord
JOIN conversations conv ON ord.conversation_id = conv.id
JOIN organizations o ON ord.organization_id = o.id
WHERE ord.payment_status = 'PAID'
  AND ord.created_at >= NOW() - INTERVAL '30 days'
GROUP BY o.name;
```

### Cart Abandonment & Recovery Tracking
```sql
SELECT 
    o.name AS organization_name,
    COUNT(CASE WHEN conv.sales_funnel_stage = 'CART_INTENT' AND ord.payment_status = 'PENDING' THEN 1 END) AS abandoned_carts,
    COUNT(CASE WHEN conv.sales_funnel_stage = 'PAID' AND conv.metadata->>'recovered' = 'true' THEN 1 END) AS recovered_carts
FROM conversations conv
LEFT JOIN orders ord ON ord.conversation_id = conv.id
JOIN organizations o ON conv.organization_id = o.id
GROUP BY o.name;
```

### Popular Catalog Attribute Inquiries
```sql
SELECT 
    p.category_id,
    p.color,
    COUNT(*) as search_frequency
FROM products p
WHERE p.stock_count > 0
GROUP BY p.category_id, p.color
ORDER BY search_frequency DESC
LIMIT 10;
```

---

## 3. Dashboard Chart Requirements
The client dashboard UI contains four core charts:
1. **Sales Funnel Graph**: Interactive bar chart displaying progression rates: `Visitor` -> `Interested` -> `Qualified` -> `Product Viewed` -> `Cart Intent` -> `Paid`.
2. **Revenue Attribution Line Chart**: Compares cumulative revenue from AI-Closed vs. Human-Assisted orders over time.
3. **Objection Categories Pie Chart**: Categorizes human takeover trigger causes (e.g., Sizing = 40%, Price negotiation = 35%, Delivery check = 25%).
4. **Product Conversion Leaderboard**: Lists top converting product SKUs.
