import requests
import random
import time
from concurrent.futures import ThreadPoolExecutor

url = "http://localhost:8000/api/webhooks/whatsapp"
brand_phone = "9493348129"

customers = [
    {"name": "Anita", "phone": "+919876543210"},
    {"name": "Rahul", "phone": "+919876543211"},
    {"name": "Priya", "phone": "+919876543212"},
    {"name": "Suresh", "phone": "+919876543213"},
    {"name": "Deepa", "phone": "+919876543214"}
]

queries = [
    "Do you have red kanjeevaram sarees?",
    "What is the price of the green silk saree?",
    "Do you offer cash on delivery?",
    "Show me your latest arrivals",
    "I want to return my last order, it has a defect.",
    "Can you show me some party wear sarees under 10000?",
    "Are you open today?",
    "I would like to speak to a human agent please.",
    "Do you ship internationally to USA?",
    "I need a blue saree for a wedding tomorrow, do you have express delivery?",
    "Do you have anything in banarasi?",
    "What is your return policy?"
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
    print("Starting simulated customer traffic...")
    with ThreadPoolExecutor(max_workers=5) as executor:
        for _ in range(25):
            customer = random.choice(customers)
            message = random.choice(queries)
            executor.submit(send_message, customer, message)
            time.sleep(random.uniform(0.5, 1.5))
    print("Finished sending simulated traffic.")

if __name__ == "__main__":
    run_simulation()
