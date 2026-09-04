import os
import csv
import json
import time
from pathlib import Path
from urllib.parse import unquote
from dotenv import load_dotenv

backend_dir = Path(__file__).parent / "backend"
load_dotenv(backend_dir / ".env")

from google import genai
from google.genai import types
from sqlalchemy import create_engine, text

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("Error: GEMINI_API_KEY not found in backend/.env")
    exit(1)

client = genai.Client(api_key=API_KEY)
CACHE_FILE = Path(__file__).parent / "image_analysis_cache.json"
CSV_FILE = Path(__file__).parent / "Closely_Boutique_Sarees_Catalog_Supabase.csv"

def load_cache():
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache):
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)

def analyze_image(image_path: str, category: str, fabric: str, max_retries=5):
    prompt = f"""You are an expert Indian silk saree catalog merchandiser.
I am providing an image of a {category} / {fabric} saree.

Analyze this saree image in detail.
Return strictly in this format:
COLOR: [Accurate primary & border/accent colors, e.g. Bottle Green & Ruby Red with Gold Zari]
DESCRIPTION: [A rich, elegant 2-sentence description detailing the exact body color, weave motifs, border design, pallu, and best occasions.]"""

    with open(image_path, "rb") as f:
        img_bytes = f.read()

    part = types.Part.from_bytes(data=img_bytes, mime_type="image/jpeg")

    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-3.6-flash",
                contents=[part, prompt]
            )
            text_out = response.text.strip()
            
            color = ""
            description = ""
            for line in text_out.split("\n"):
                line = line.strip()
                if line.upper().startswith("COLOR:"):
                    color = line[6:].strip().strip("[]*#")
                elif line.upper().startswith("DESCRIPTION:"):
                    description = line[12:].strip().strip("[]*#")
            
            if color and description:
                return color, description
            else:
                return "Multicolor & Gold", text_out
        except Exception as e:
            err_str = str(e)
            print(f"    [!] Error on {os.path.basename(image_path)} (attempt {attempt+1}/{max_retries}): {err_str[:120]}")
            if "RESOURCE_EXHAUSTED" in err_str or "429" in err_str:
                wait_sec = 8 + (attempt * 4)
                print(f"    Rate limit hit, pausing {wait_sec}s...")
                time.sleep(wait_sec)
            else:
                time.sleep(3)
    return None, None

def sync_csv_and_db(cache):
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)

    updated_count = 0
    for row in rows:
        img_url = row["image_urls"].split(",")[0].strip()
        parts = img_url.split("/catelog-images/")
        rel_path = unquote(parts[1]) if len(parts) > 1 else row["sku"]
        if rel_path in cache:
            row["color"] = cache[rel_path]["color"]
            row["description"] = cache[rel_path]["description"]
            updated_count += 1

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    try:
        db_url = "postgresql://postgres:postgres@127.0.0.1:5434/closely_db"
        engine = create_engine(db_url)
        with engine.connect() as conn:
            for row in rows:
                conn.execute(
                    text("UPDATE products SET color = :color, description = :desc WHERE sku = :sku"),
                    {"color": row["color"], "desc": row["description"], "sku": row["sku"]}
                )
            conn.commit()
    except Exception:
        pass

    return updated_count

def main():
    sarees_dir = backend_dir / "static" / "uploads" / "sarees"
    cache = load_cache()
    print(f"Loaded {len(cache)} cached image analyses.")

    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))

    total = len(reader)
    for idx, row in enumerate(reader, 1):
        sku = row["sku"]
        category = row["category"]
        fabric = row["fabric"]
        img_url = row["image_urls"].split(",")[0].strip()
        parts = img_url.split("/catelog-images/")
        if len(parts) > 1:
            rel_path = unquote(parts[1])
            local_img_path = sarees_dir / rel_path
        else:
            rel_path = sku
            local_img_path = None

        if rel_path in cache:
            print(f"[{idx}/{total}] {sku} ({rel_path}) -> Cached: {cache[rel_path]['color']}")
            continue

        if not local_img_path or not local_img_path.exists():
            print(f"[{idx}/{total}] {sku} -> Image not found: {local_img_path}")
            continue

        print(f"[{idx}/{total}] Analyzing {sku} ({rel_path})...")
        color, desc = analyze_image(str(local_img_path), category, fabric)
        if color and desc:
            cache[rel_path] = {"color": color, "description": desc}
            save_cache(cache)
            sync_csv_and_db(cache)
            print(f"    -> Color: {color}")
            print(f"    -> Desc: {desc[:90]}...")
        else:
            print(f"    -> Failed to analyze {sku}")

        time.sleep(4.5)

    updated_final = sync_csv_and_db(cache)
    print(f"\n[+] DONE! {updated_final} / {total} products updated with accurate image descriptions & colors.")

if __name__ == "__main__":
    main()
