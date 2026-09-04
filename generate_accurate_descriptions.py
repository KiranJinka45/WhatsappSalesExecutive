import os
import csv
import json
import colorsys
from pathlib import Path
from urllib.parse import unquote
from PIL import Image
from sqlalchemy import create_engine, text

BASE_DIR = Path(__file__).parent
SAREES_DIR = BASE_DIR / "backend" / "static" / "uploads" / "sarees"
CSV_FILE = BASE_DIR / "Closely_Boutique_Sarees_Catalog_Supabase.csv"
CACHE_FILE = BASE_DIR / "image_analysis_cache.json"

cache = {}
if CACHE_FILE.exists():
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}

def classify_color(h, s, v):
    if v < 0.18:
        return "Midnight Black"
    if s < 0.14:
        if v > 0.82: return "Cream / Off-White"
        elif v > 0.52: return "Silver Grey"
        else: return "Steel / Slate Grey"
    
    if s < 0.28 and v > 0.70:
        if 20 <= h < 50: return "Pastel Peach"
        if 50 <= h < 90: return "Pale Buttercup Yellow"
        if 90 <= h < 160: return "Mint Sage Green"
        if 160 <= h < 220: return "Sky Blue"
        if 220 <= h < 320: return "Lavender Lilac"
        return "Blush Rose Pink"

    if h < 15 or h >= 345:
        if v < 0.48 or (s > 0.70 and v < 0.55): return "Deep Crimson Maroon"
        return "Ruby Red"
    elif 15 <= h < 45:
        if s > 0.55 and v > 0.60: return "Tangerine Orange"
        if v < 0.45: return "Rust Copper"
        return "Coral Peach"
    elif 45 <= h < 70:
        if s > 0.45 and v > 0.65: return "Mustard Golden Yellow"
        if v < 0.50: return "Antique Bronze Gold"
        return "Haldi Yellow"
    elif 70 <= h < 160:
        if 70 <= h < 95: return "Olive Chartreuse Green"
        if v < 0.42: return "Deep Bottle Green"
        return "Emerald Forest Green"
    elif 160 <= h < 205:
        return "Teal Peacock Green"
    elif 205 <= h < 255:
        if v < 0.42: return "Midnight Navy Blue"
        return "Royal Peacock Blue"
    elif 255 <= h < 300:
        if v < 0.45: return "Deep Royal Purple"
        return "Violet Amethyst"
    elif 300 <= h < 345:
        if v < 0.45: return "Plum Wine"
        return "Rani Pink / Magenta"
    return "Multicolor & Gold"

def analyze_saree_image(img_path, category, fabric):
    img = Image.open(img_path).convert("RGB")
    w, h = img.size

    body_crop = img.crop((int(w * 0.25), int(h * 0.22), int(w * 0.75), int(h * 0.58))).resize((100, 100))
    border_crop = img.crop((int(w * 0.20), int(h * 0.68), int(w * 0.80), int(h * 0.92))).resize((100, 100))

    def get_dominant(crop):
        pixels = list(crop.getdata())
        valid = []
        zari_count = 0
        for r, g, b in pixels:
            h_val, s_val, v_val = colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)
            if (35 <= h_val * 360 <= 55) and s_val > 0.40 and v_val > 0.55:
                zari_count += 1
            if not (v_val > 0.88 and s_val < 0.10) and v_val > 0.12:
                valid.append((h_val * 360, s_val, v_val))
        
        if not valid:
            return "Rich Silk", False
        
        valid.sort(key=lambda x: x[1] * x[2], reverse=True)
        top = valid[len(valid) // 3]
        has_zari = (zari_count / len(pixels)) > 0.08
        return classify_color(top[0], top[1], top[2]), has_zari

    body_color, has_body_zari = get_dominant(body_crop)
    border_color, has_border_zari = get_dominant(border_crop)

    if body_color == border_color:
        full_color = f"{body_color} with Gold Zari"
    else:
        full_color = f"{body_color} & {border_color} with Gold Zari"

    fab_clean = fabric.replace("_", " ").title()
    cat_clean = category.replace("_", " ").title()

    description = (
        f"Exquisite handloom {fab_clean} saree showcased in a captivating {body_color} body "
        f"adorned with delicate woven motifs. Styled with a contrasting {border_color} border and opulent "
        f"zari jacquard detailing, this masterpiece is ideal for weddings, temple rituals, and grand festive occasions."
    )

    return full_color, description

def main():
    with open(CSV_FILE, "r", encoding="utf-8") as f:
        reader = list(csv.DictReader(f))
        fieldnames = list(reader[0].keys())

    updated = 0
    for idx, row in enumerate(reader, 1):
        sku = row["sku"]
        category = row["category"]
        fabric = row["fabric"]
        img_url = row["image_urls"].split(",")[0].strip()
        
        parts = img_url.split("/catelog-images/")
        rel_path = unquote(parts[1]) if len(parts) > 1 else None

        if rel_path and rel_path in cache and cache[rel_path].get("color"):
            color = cache[rel_path]["color"]
            desc = cache[rel_path]["description"]
            print(f"[{idx}/{len(reader)}] ({sku}) [Gemini Cached] -> {color}")
        elif rel_path:
            local_img = SAREES_DIR / rel_path
            if local_img.exists():
                color, desc = analyze_saree_image(local_img, category, fabric)
                print(f"[{idx}/{len(reader)}] ({sku}) [Vision Analyzed] -> {color}")
            else:
                color = row["color"]
                desc = row["description"]
        else:
            color = row["color"]
            desc = row["description"]

        row["color"] = color
        row["description"] = desc
        updated += 1

    with open(CSV_FILE, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(reader)
    print(f"\n[+] Successfully updated {CSV_FILE.name} with {updated} accurate product descriptions & colors!")

    try:
        engine = create_engine("postgresql://postgres:postgres@127.0.0.1:5434/closely_db")
        with engine.connect() as conn:
            db_up = 0
            for row in reader:
                res = conn.execute(
                    text("UPDATE products SET color = :color, description = :desc WHERE sku = :sku"),
                    {"color": row["color"], "desc": row["description"], "sku": row["sku"]}
                )
                db_up += res.rowcount
            conn.commit()
            print(f"[+] Updated {db_up} records in local PostgreSQL database (closely_db)!")
    except Exception as e:
        print(f"[-] Database notice: {e}")

if __name__ == "__main__":
    main()
