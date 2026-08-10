import os
import csv
import uuid
import sys

from app.database import SessionLocal
from app.models import Product, Organization, Category

def import_csv():
    db = SessionLocal()
    org_name = "Sri Siddi Vinayaka"
    org = db.query(Organization).filter(Organization.name == org_name).first()
    
    if not org:
        print(f"Error: Organization '{org_name}' not found.")
        return

    # Delete all existing products for this org to clear the Unsplash placeholders
    deleted_count = db.query(Product).filter(Product.organization_id == org.id).delete()
    print(f"Deleted {deleted_count} old placeholder products.")
    db.commit()

    csv_path = "/app/AI_Sales_Employee_Sarees_Inventory.csv"
    if not os.path.exists(csv_path):
        # Fallback to parent dir if mounted differently
        csv_path = "../AI_Sales_Employee_Sarees_Inventory.csv"
        
    imported = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            cat_name = row['category']
            cat = db.query(Category).filter(Category.organization_id == org.id, Category.name == cat_name).first()
            if not cat:
                cat = Category(organization_id=org.id, name=cat_name)
                db.add(cat)
                db.commit()
                db.refresh(cat)
            
            p = Product(
                id=uuid.uuid4(),
                organization_id=org.id,
                category_id=cat.id,
                sku=row['sku'],
                name=row['name'],
                price=float(row['price']) if row['price'] else 0.0,
                color=row['color'],
                fabric=row['fabric'],
                description=row['description'],
                stock_count=int(row['stock_count']) if row['stock_count'] else 0,
                sizes=row['sizes'],
                image_urls=[row['image_urls']],
                embedding_status='pending'
            )
            db.add(p)
            imported += 1
            
    db.commit()
    print(f"Successfully imported {imported} new products into the database!")

if __name__ == "__main__":
    import_csv()
