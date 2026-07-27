import requests
import json
import time

BASE_URL = "http://localhost:8000/api"

# We need an org and a token, but the webhook doesn't need a token, it uses the verification token
WEBHOOK_URL = f"http://localhost:8000/api/webhooks/whatsapp"

def test_approval_flow():
    print("Testing Decision Engine Approval Flow...")
    
    # 1. Send a simulated webhook message that triggers the bulk order policy
    payload = {
        "customer_phone": "+919900005557",
        "customer_name": "Test Bulk Buyer",
        "message": "Hello, I would like to order 100 items of this product.",
        "brand_phone": "+15551234567"
    }
    
    print("Sending webhook message...")
    res = requests.post(WEBHOOK_URL, json=payload)
    if res.status_code != 200:
        print(f"Webhook failed: {res.text}")
        return
        
    data = res.json()
    print("Webhook response:", data)
    
    if data.get("status") == "WAITING_FOR_OWNER":
        print("SUCCESS: Message routed to waiting for owner!")
    else:
        print("ERROR: Message did not trigger approval.")
        
if __name__ == "__main__":
    test_approval_flow()
