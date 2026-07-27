import sys
import json
import hmac
import hashlib
import time
import httpx
import os
from typing import Dict, Any

# Adjust paths to import backend configuration
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.app.config import settings

def compute_signature(payload: bytes, secret: str) -> str:
    """
    Computes X-Hub-Signature-256 signature for the given payload.
    """
    computed = hmac.new(
        secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return f"sha256={computed}"

def build_meta_webhook(phone: str, text: str, name: str = "Test Customer") -> Dict[str, Any]:
    """
    Wraps text message in standard Meta Cloud API webhook JSON wrapper.
    """
    timestamp = str(int(time.time()))
    return {
        "object": "whatsapp_business_account",
        "entry": [{
            "changes": [{
                "field": "messages",
                "value": {
                    "contacts": [{
                        "wa_id": phone,
                        "profile": {
                            "name": name
                        }
                    }],
                    "messages": [{
                        "id": f"wamid.mockreplay_{phone}_{timestamp}",
                        "from": phone,
                        "timestamp": timestamp,
                        "type": "text",
                        "text": {
                            "body": text
                        }
                    }],
                    "metadata": {
                        "display_phone_number": "15550000000",
                        "phone_number_id": "mock_phone_id"
                    }
                }
            }]
        }]
    }

def send_webhook(payload: dict, secret: Optional[str] = None, target_url: str = "http://localhost:8000/api/webhooks/whatsapp"):
    payload_bytes = json.dumps(payload).encode('utf-8')
    headers = {"Content-Type": "application/json"}
    
    if secret:
        sig = compute_signature(payload_bytes, secret)
        headers["X-Hub-Signature-256"] = sig
        print(f"Calculated signature: {sig}")

    print(f"Sending webhook to {target_url}...")
    try:
        response = httpx.post(target_url, content=payload_bytes, headers=headers, timeout=5.0)
        print(f"Response Status: {response.status_code}")
        print(f"Response Content: {response.text}\n")
        return response
    except Exception as e:
        print(f"Failed to connect to backend: {e}\n")
        return None

def main():
    if len(sys.argv) < 2:
        print("Usage: python replay.py <file_path.json> [customer_phone_number]")
        sys.exit(1)

    file_path = sys.argv[1]
    phone_number = sys.argv[2] if len(sys.argv) > 2 else "919876543210"
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        sys.exit(1)

    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    secret = settings.WHATSAPP_APP_SECRET
    if not secret:
        print("Settings WHATSAPP_APP_SECRET is not configured. Webhook signature check will be skipped by the backend if it is also null there.")

    # 1. Check if the payload is a raw webhook dict
    if isinstance(data, dict) and "object" in data:
        print(f"Replaying raw webhook payload from {file_path}")
        send_webhook(data, secret)
    # 2. Check if the payload is a list of historic messages
    elif isinstance(data, list):
        print(f"Replaying conversation sequence ({len(data)} items) from {file_path}")
        for turn in data:
            if turn.get("sender") == "customer":
                text = turn.get("content")
                print(f"Replaying Customer Message: '{text}'")
                payload = build_meta_webhook(phone_number, text)
                send_webhook(payload, secret)
                # Wait 2.0s to allow async pipeline processing and print sequencing
                time.sleep(2.0)
    else:
        print("Unsupported JSON format. Provide a raw Meta Cloud API webhook object or a list of conversation logs.")
        sys.exit(1)

if __name__ == "__main__":
    main()
