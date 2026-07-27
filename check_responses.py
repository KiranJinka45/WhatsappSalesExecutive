import sys
import os

os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5434/closely_db"
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.app.database import SessionLocal
from backend.app.models import Conversation, Message

db = SessionLocal()
convs = db.query(Conversation).filter(
    Conversation.customer_phone.in_(['+918880000001', '+918880000002', '+918880000003', '+918880000004', '+918880000005'])
).all()

for c in convs:
    print(f"\n--- Conversation: {c.customer_name} ({c.customer_phone}) - Status: {c.status} ---")
    msgs = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.created_at.asc()).all()
    for m in msgs:
        print(f"  [{m.sender.upper()}]: {m.content}")

db.close()
