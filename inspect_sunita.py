import sys
import os

os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5434/closely_db"
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.app.database import SessionLocal
from backend.app.models import Conversation, Message

db = SessionLocal()
convs = db.query(Conversation).filter(
    Conversation.customer_phone == '+917770000003'
).all()

for c in convs:
    print(f"\n--- Conversation ID: {c.id} - Org: {c.organization_id} - Status: {c.status} ---")
    msgs = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.created_at.asc()).all()
    for m in msgs:
        print(f"  [{m.sender.upper()}] (ID: {m.id}, Created: {m.created_at}): {m.content}")

db.close()
