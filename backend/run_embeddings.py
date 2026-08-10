import os
import sys

from app.database import SessionLocal
from app.models import Product
from app.catalog_service import generate_product_embedding_task

def run_embeddings():
    db = SessionLocal()
    products = db.query(Product).filter(Product.embedding_status == 'pending').all()
    print(f"Found {len(products)} products needing AI embeddings.")
    
    for p in products:
        print(f"Generating embedding for {p.name}...")
        try:
            generate_product_embedding_task(SessionLocal, str(p.id))
        except Exception as e:
            print(f"Error on {p.name}: {e}")
            
    print("All embeddings generated successfully!")

if __name__ == "__main__":
    run_embeddings()
