import sys
import os
import json
from uuid import uuid4
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.database import SessionLocal, Base, engine
from backend.app.models import Organization, Conversation, Message
from backend.app.catalog_service import parse_and_sync_catalog
from backend.app.routers.webhooks import process_message_async

def setup_db():
    Base.metadata.create_all(bind=engine)

def run_simulation():
    setup_db()
    db = SessionLocal()
    
    merchants = [
        {"id": "merchant_01", "name": "Ethnic Boutique", "phone": "+919876543210", "csv": "pilot/merchant_01/catalog.csv", "dir": "pilot/merchant_01"},
        {"id": "merchant_02", "name": "Modern Streetwear", "phone": "+919876543211", "csv": "pilot/merchant_02/catalog.csv", "dir": "pilot/merchant_02"},
        {"id": "merchant_03", "name": "Formal Menswear", "phone": "+919876543212", "csv": "pilot/merchant_03/catalog.csv", "dir": "pilot/merchant_03"}
    ]
    
    # 1. Register and Ingest
    for m in merchants:
        print(f"--- Simulating {m['name']} ---")
        
        # Create Org
        org = db.query(Organization).filter(Organization.whatsapp_number == m["phone"]).first()
        if not org:
            org = Organization(name=m["name"], whatsapp_number=m["phone"])
            db.add(org)
            db.commit()
            db.refresh(org)
            
        # Upload Catalog
        try:
            with open(m["csv"], "rb") as f:
                content = f.read()
            report = parse_and_sync_catalog(content, org.id, db)
            print(f"Catalog upload for {m['name']}: {report.valid_count} valid, {report.invalid_count} invalid.")
        except Exception as e:
            print(f"Failed to upload catalog: {e}")
            
        m["org_id"] = str(org.id)

    # 2. Simulate Customer Journeys
    customer_phone = "+918888888888"
    customer_queries = [
        "Hi, do you have any blue items?",
        "What is the price of the first one?",
        "Do you have anything under 2000?",
        "I want to order it."
    ]
    
    for m in merchants:
        print(f"\nSimulating conversation for {m['name']}...")
        
        # Create a conversation
        db.organization_id = m["org_id"]
        conv = Conversation(
            organization_id=m["org_id"],
            customer_phone=customer_phone,
            customer_name="Kiran",
            status="ai_active"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)
        
        conv_log = []
        
        for q in customer_queries:
            # Add Customer Message
            cust_msg = Message(
                conversation_id=conv.id,
                sender="customer",
                message_type="text",
                content=q
            )
            db.add(cust_msg)
            db.commit()
            
            conv_log.append({"sender": "customer", "message": q})
            
            # Trigger AI processing synchronously for simulation
            print(f"Customer: {q}")
            process_message_async(m["org_id"], str(conv.id), q)
            
            # Fetch AI reply
            ai_msg = db.query(Message).filter(
                Message.conversation_id == conv.id,
                Message.sender == "ai"
            ).order_by(Message.created_at.desc()).first()
            
            if ai_msg:
                print(f"AI: {ai_msg.content}")
                conv_log.append({"sender": "ai", "message": ai_msg.content})
                
        # Write to conversation_001.json
        with open(f"{m['dir']}/conversation_001.json", "w") as f:
            json.dump(conv_log, f, indent=2)
            
    db.close()
    print("\nSimulation complete! Check the pilot/ directory for output JSON files.")

if __name__ == "__main__":
    run_simulation()
