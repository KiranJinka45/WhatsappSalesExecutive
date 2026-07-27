import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import sys

sys.path.append(r"c:\whatsapp_AI Sales Employee\backend")

load_dotenv(r"c:\whatsapp_AI Sales Employee\backend\.env")

# Fallback to local DB if no remote one
DB_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/closely_db")
print(f"Connecting to: {DB_URL}")

engine = create_engine(DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

from app import models

# Get the last AI message that failed
failed_msg = db.query(models.Message).filter(models.Message.status == 'failed').order_by(models.Message.created_at.desc()).first()

if failed_msg:
    with open("error_log_output.txt", "w", encoding="utf-8") as f:
        f.write(f"FAILED MSG ID: {failed_msg.id}\n")
        f.write(f"CONTENT: {failed_msg.content}\n")
        f.write(f"ERROR: {failed_msg.error_message}\n")
    print("Wrote error to error_log_output.txt")
else:
    print("No failed messages found.")
