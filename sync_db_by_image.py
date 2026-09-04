import csv
from sqlalchemy import create_engine, text

CSV_FILE = "Closely_Boutique_Sarees_Catalog_Supabase.csv"

with open(CSV_FILE, "r", encoding="utf-8") as f:
    csv_rows = list(csv.DictReader(f))

file_map = {}
for r in csv_rows:
    img_url = r["image_urls"].split(",")[0].strip()
    filename = img_url.split("/")[-1]
    file_map[filename] = (r["color"], r["description"])

engine = create_engine("postgresql://postgres:postgres@127.0.0.1:5434/closely_db")
updated_count = 0
with engine.connect() as conn:
    db_prods = conn.execute(text("SELECT id, image_urls FROM products")).fetchall()
    for pid, urls in db_prods:
        if not urls:
            continue
        first_url = urls[0] if isinstance(urls, list) else str(urls).split(",")[0]
        fname = first_url.split("/")[-1].strip("\"' ")
        if fname in file_map:
            color, desc = file_map[fname]
            conn.execute(
                text("UPDATE products SET color = :color, description = :desc WHERE id = :id"),
                {"color": color, "desc": desc, "id": pid}
            )
            updated_count += 1
    conn.commit()

print(f"Successfully updated {updated_count} products in local DB by image filename match!")
