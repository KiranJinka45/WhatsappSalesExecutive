import sys
import os
import uuid

os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5434/closely_db"
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from backend.app.database import SessionLocal
from backend.app.models import Product, Organization

db = SessionLocal()
kavitha = db.query(Organization).filter(Organization.name == "Kavitha's Ethnic Couture").first()
siddi = db.query(Organization).filter(Organization.name == "Sri Siddi Vinayaka Silk Sarees").first()

if kavitha and siddi:
    products = db.query(Product).filter(Product.organization_id == kavitha.id).all()
    copied = 0
    for p in products:
        exists = db.query(Product).filter(Product.organization_id == siddi.id, Product.sku == p.sku).first()
        if not exists:
            new_p = Product(
                id=uuid.uuid4(),
                organization_id=siddi.id,
                sku=p.sku,
                name=p.name,
                gender=p.gender,
                price=p.price,
                color=p.color,
                fabric=p.fabric,
                description=p.description,
                sizes=p.sizes,
                stock_count=p.stock_count,
                image_urls=p.image_urls,
                video_urls=p.video_urls,
                embedding=p.embedding
            )
            db.add(new_p)
            copied += 1
    db.commit()
    print(f"Copied {copied} products successfully!")
else:
    print("Failed to find organizations.")
db.close()
