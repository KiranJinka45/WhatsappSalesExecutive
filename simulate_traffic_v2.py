import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor

url = "http://localhost:8000/api/webhooks/whatsapp"
brand_phone = "9493348129"

# Fresh customer set to avoid existing conversations locked in human_takeover status
customers = [
    {"name": "Meera", "phone": "+918880000001"},
    {"name": "Rohan", "phone": "+918880000002"},
    {"name": "Ananya", "phone": "+918880000003"},
    {"name": "Vikram", "phone": "+918880000004"},
    {"name": "Kavya", "phone": "+918880000005"}
]

# Specifically include queries that will match policies and products
queries = [
    "Do you have red silk sarees?",
    "What is the price of the green silk saree?",
    "Do you offer cash on delivery?",
    "Show me your latest arrivals",
    "Can you show me some party wear sarees under 10000?",
    "Are you open today?",
    "Do you ship internationally?",
    "What is your return policy?",
    "Do you have anything in banarasi?",
    "I need a blue silk saree, show me options"
]

def send_message(customer, message):
    payload = {
        "customer_phone": customer["phone"],
        "message": message,
        "customer_name": customer["name"],
        "brand_phone": brand_phone
    }
    try:
        response = requests.post(url, json=payload, headers={'Content-Type': 'application/json'})
        print(f"Sent message from {customer['name']}: {response.status_code}")
    except Exception as e:
        print(f"Failed to send from {customer['name']}: {e}")

def run_simulation():
    print("Starting simulated customer traffic v2...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in range(15):
            customer = random.choice(customers)
            message = random.choice(queries)
            executor.submit(send_message, customer, message)
            time.sleep(random.uniform(0.5, 1.5))
    print("Finished sending simulated traffic v2.")

if __name__ == "__main__":
    run_simulation()
