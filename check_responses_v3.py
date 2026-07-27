import sys
import os

# Set stdout to UTF-8 to handle emojis in Windows console
sys.stdout.reconfigure(encoding='utf-8')

os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@127.0.0.1:5434/closely_db"
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from backend.app.database import SessionLocal
from backend.app.models import Conversation, Message

db = SessionLocal()
convs = db.query(Conversation).filter(
    Conversation.customer_phone.in_(['+917770000001', '+917770000002', '+917770000003', '+917770000004', '+917770000005'])
).all()

for c in convs:
    print(f"\n--- Conversation: {c.customer_name} ({c.customer_phone}) - Status: {c.status} ---")
    msgs = db.query(Message).filter(Message.conversation_id == c.id).order_by(Message.created_at.asc()).all()
    for m in msgs:
        print(f"  [{m.sender.upper()}]: {m.content}")

db.close()
