import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import sys

sys.path.append(r"c:\whatsapp_AI Sales Employee\backend")

load_dotenv(r"c:\whatsapp_AI Sales Employee\backend\.env")

DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/closely_db")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

from app import models

failed_msgs = db.query(models.Message).filter(models.Message.content.like('%System Error%')).order_by(models.Message.created_at.desc()).limit(5).all()

with open("error_log_output3.txt", "w", encoding="utf-8") as f:
    if not failed_msgs:
        f.write("No system error messages found.\n")
    for msg in failed_msgs:
        f.write(f"FAILED MSG ID: {msg.id}\n")
        f.write(f"CONTENT: {msg.content}\n")
        f.write(f"ERROR: {msg.error_message}\n")
        f.write("-" * 50 + "\n")
print("Done")
