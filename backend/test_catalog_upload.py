import asyncio
import os
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app import models
from app.catalog_service import parse_and_sync_catalog
from fastapi import BackgroundTasks

models.Base.metadata.create_all(bind=engine)

def test_upload():
    db = SessionLocal()
    org = db.query(models.Organization).first()
    if not org:
        org = models.Organization(name="Test Org")
        db.add(org)
        db.commit()
        db.refresh(org)

    csv_data = b"sku,name,price,color,category,fabric,stock_count\nS1,Test1,100,Red,Cat1,Cotton,10"
    
    bg_tasks = BackgroundTasks()
    try:
        res = parse_and_sync_catalog(db, str(org.id), csv_data, "test.csv", bg_tasks)
        print("Success:", res)
    except Exception as e:
        print("Error:", e)
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    test_upload()
