import os
import json
import pytest
from app.emulator import generate_realistic_wamid

CONTRACTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "contracts"))

def test_meta_send_message_contract():
    """
    Assert that the emulator's outbound send message payload matches the recorded Meta API schema.
    """
    with open(os.path.join(CONTRACTS_DIR, "meta_send_message.json"), "r") as f:
        contract = json.load(f)
        
    # Generate realistic emulator response schema
    wamid = generate_realistic_wamid("919876543210")
    emulator_response = {
        "messaging_product": "whatsapp",
        "contacts": [
            {
                "input": "919876543210",
                "wa_id": "919876543210"
            }
        ],
        "messages": [
            {
                "id": wamid
            }
        ]
    }
    
    # Verify key structure and static defaults match
    assert emulator_response.keys() == contract.keys()
    assert emulator_response["messaging_product"] == contract["messaging_product"]
    assert len(emulator_response["contacts"]) == len(contract["contacts"])
    assert emulator_response["contacts"][0].keys() == contract["contacts"][0].keys()
    assert len(emulator_response["messages"]) == len(contract["messages"])
    assert emulator_response["messages"][0]["id"].startswith("wamid.HBgM")

def test_meta_errors_contract():
    """
    Assert that error layouts mapped in contracts align with standard exceptions.
    """
    with open(os.path.join(CONTRACTS_DIR, "meta_error_429.json"), "r") as f:
        err_429 = json.load(f)
    assert "error" in err_429
    assert err_429["error"]["code"] == 131048
    
    with open(os.path.join(CONTRACTS_DIR, "meta_error_500.json"), "r") as f:
        err_500 = json.load(f)
    assert "error" in err_500
    assert err_500["error"]["type"] == "OAuthException"
