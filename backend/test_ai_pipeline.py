import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from app.database import SessionLocal, tenant_var
from app import models, ai_service

db = SessionLocal()
org = db.query(models.Organization).filter(models.Organization.id == '76043d11-b671-420b-b1cc-3991c5547bbc').first()
tenant_var.set(org.id)

print(f"=== Testing AI Sales Brain for: {org.name} ({org.whatsapp_number}) ===")

test_queries = [
    "Hi, do you have any pure silk sarees in pink under 3000?",
    "What is your return and delivery policy?",
    "Pattu sarees designs chupinchandi budget 2500 lopala"
]

for query in test_queries:
    print(f"\n💬 Customer: '{query}'")
    
    # 1. Intent Classification
    intent = ai_service.classify_intent(query)
    print(f"🎯 Intent: {intent}")
    
    # 2. Entity Extraction
    entities = ai_service.extract_entities(query, [])
    print(f"🔍 Extracted: {entities}")
    
    # 3. Search Products
    matches = db.query(models.Product).filter(
        models.Product.organization_id == org.id,
        models.Product.stock_count > 0
    )
    if entities.get("color"):
        matches = matches.filter(models.Product.color.ilike(f"%{entities['color']}%"))
    if entities.get("fabric"):
        matches = matches.filter(models.Product.fabric.ilike(f"%{entities['fabric']}%"))
    if entities.get("budget_max"):
        matches = matches.filter(models.Product.price <= entities['budget_max'])
    
    matched_prods = matches.limit(3).all()
    catalog_ctx = [{
        "sku": p.sku,
        "name": p.name,
        "price": float(p.price),
        "color": p.color,
        "fabric": p.fabric,
        "stock_count": p.stock_count
    } for p in matched_prods]
    print(f"📦 Retrieved {len(catalog_ctx)} products from catalog:")
    for p in catalog_ctx:
        print(f"   - {p['name']} | ₹{p['price']} | {p['color']} {p['fabric']}")

    # 4. Generate Grounded Reply
    reply = ai_service.generate_reply(
        customer_msg=query,
        history=[],
        catalog_context=catalog_ctx,
        policies_context=org.policies,
        brand_name=org.name
    )
    print(f"🤖 AI Response:\n{reply}\n")

db.close()
