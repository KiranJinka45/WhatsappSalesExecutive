import os
import csv
import uuid
import time
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables (e.g. GEMINI_API_KEY)
load_dotenv()

# We use google.genai as per your backend ai_service implementation
from google import genai
from google.genai import types

# Configure your public URL base here.
PUBLIC_URL_BASE = "https://hz3mhb-ip-103-214-63-41.tunnelmole.net"

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Error: GEMINI_API_KEY not found in .env file.")
        exit(1)
    return genai.Client(api_key=api_key)

def analyze_saree_image(client, image_path: str, fabric_type: str, max_retries=3):
    """Uses Gemini Vision API to analyze the saree and generate description & color with automatic retries."""
    
    prompt = f"""
    You are an expert Indian ethnic wear fashion consultant for Pushpalatha Silks.
    I am providing an image of a {fabric_type} saree.
    
    Please return a response strictly in this exact format:
    COLOR: [Primary and Secondary Colors, e.g., Mustard Yellow & Green]
    DESCRIPTION: [1 to 2 sentence beautiful sales description highlighting the border, work, and fabric feel.]
    """
    
    for attempt in range(max_retries):
        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
                
            part = types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg")
            
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[part, prompt]
            )
            
            text = response.text.strip()
            
            color = "Multicolor"
            description = f"Beautiful {fabric_type} saree."
            
            # Parse the AI output
            for line in text.split('\n'):
                line = line.strip()
                if line.startswith("COLOR:"):
                    color = line.replace("COLOR:", "").strip()
                elif line.startswith("DESCRIPTION:"):
                    description = line.replace("DESCRIPTION:", "").strip()
                    
            return color, description
            
        except Exception as e:
            print(f"  [!] Attempt {attempt + 1} failed to analyze {os.path.basename(image_path)}: {e}")
            if attempt < max_retries - 1:
                wait_time = (attempt + 1) * 10
                print(f"  Waiting {wait_time}s before retrying...")
                time.sleep(wait_time)
            else:
                return "Unknown", f"Beautiful {fabric_type} saree."

def generate_inventory():
    print("Starting Saree Inventory Generation...")
    client = get_gemini_client()
    
    # Paths
    base_dir = Path(__file__).parent
    uploads_dir = base_dir / "static" / "uploads" / "sarees"
    output_csv = base_dir.parent / "AI_Sales_Employee_Sarees_Inventory.csv"
    
    if not uploads_dir.exists():
        print(f"Directory {uploads_dir} does not exist. Run the folder creation script first.")
        return

    # Prepare CSV Header
    headers = [
        "sku", "name", "price", "color", "category", "gender", 
        "fabric", "description", "stock_count", "sizes", "image_urls", "video_urls"
    ]
    
    processed_urls = set()
    if output_csv.exists():
        try:
            with open(output_csv, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("image_urls"):
                        processed_urls.add(row["image_urls"])
            print(f"Loaded {len(processed_urls)} already processed products. Resuming...")
        except Exception as e:
            print(f"Could not read existing CSV for resume: {e}. Starting fresh.")
            
    # Iterate through all subfolders (which act as Fabric types)
    for fabric_dir in uploads_dir.iterdir():
        if not fabric_dir.is_dir():
            continue
            
        fabric_type = fabric_dir.name
        print(f"\nProcessing Fabric: {fabric_type}...")
        
        # Iterate through images in the folder
        for img_file in fabric_dir.iterdir():
            if img_file.suffix.lower() not in ['.jpg', '.jpeg', '.png', '.webp']:
                continue
                
            from urllib.parse import quote
            safe_fabric = quote(fabric_type)
            safe_filename = quote(img_file.name)
            public_url = f"{PUBLIC_URL_BASE}/static/uploads/sarees/{safe_fabric}/{safe_filename}"
            
            if public_url in processed_urls:
                print(f"  Skipping {img_file.name} (already processed).")
                continue
                
            print(f"  Analyzing {img_file.name}...")
            
            # Generate Metadata
            sku = f"SKU-{fabric_type[:4].upper().replace(' ', '')}-{str(uuid.uuid4())[:6].upper()}"
            name = f"Premium {fabric_type} Saree - {img_file.stem.replace('_', ' ').title()}"
            
            # Use Gemini to extract color and description
            color, description = analyze_saree_image(client, str(img_file), fabric_type)
            
            row = {
                "sku": sku,
                "name": name,
                "price": "4500.0",  # Default price
                "color": color,
                "category": "Sarees",
                "gender": "Female",
                "fabric": fabric_type,
                "description": description,
                "stock_count": "10",
                "sizes": "Free Size",
                "image_urls": public_url,
                "video_urls": ""
            }
            
            # Append directly to CSV
            file_exists = output_csv.exists()
            mode = "a" if file_exists else "w"
            with open(output_csv, mode, newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                if not file_exists:
                    writer.writeheader()
                writer.writerow(row)
                
            # Sleep briefly to avoid hitting Gemini API rate limits on free tier
            time.sleep(4.5)
            
    print("Done! Inventory CSV generated/updated successfully.")

if __name__ == "__main__":
    generate_inventory()
