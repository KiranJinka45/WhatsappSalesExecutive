import csv
import io
import re
import logging
from sqlalchemy.orm import Session
from decimal import Decimal
from fastapi import BackgroundTasks
from . import models
from .database import SessionLocal, tenant_var

logger = logging.getLogger(__name__)

def generate_product_embedding_task(db_session_factory, product_id: str):
    """
    Background task to generate product vector embedding asynchronously.
    Updates embedding_status to 'completed' or 'failed'.
    """
    db = db_session_factory()
    token = tenant_var.set(None)  # Bypass tenant filtering to query globally by ID
    try:
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if not product:
            return
            
        product.embedding_status = "processing"
        db.commit()
        
        cat_name = product.category.name if product.category else "Uncategorized"
        embed_text = f"Product: {product.name}. Category: {cat_name}. Gender: {product.gender or 'Unisex'}. Price: INR {product.price}. Color: {product.color}. Fabric: {product.fabric or ''}. Description: {product.description or ''}."
        
        from .ai_service import get_embedding
        embedding = get_embedding(embed_text)
        
        # Verify embedding is valid
        if embedding and any(v != 0.0 for v in embedding):
            product.embedding = embedding
            product.embedding_status = "completed"
        else:
            product.embedding_status = "failed"
            
        db.commit()
    except Exception as e:
        logger.error(f"Failed async embedding for product {product_id}: {e}")
        try:
            product = db.query(models.Product).filter(models.Product.id == product_id).first()
            if product:
                product.embedding_status = "failed"
                db.commit()
        except Exception as e:
            logger.warning("Error resetting database session during catalog import: %s", str(e))
    finally:
        db.close()
        tenant_var.reset(token)

def parse_and_sync_catalog(
    db: Session, 
    org_id: str, 
    file_content: bytes, 
    filename: str,
    background_tasks: BackgroundTasks
) -> dict:
    """
    Parses a CSV file with robust validation, uploads products,
    and schedules vector embedding updates asynchronously.
    Rejects the entire file if any validation errors are found.
    """
    # 1. Validate File Size (Max 5MB)
    if len(file_content) > 5 * 1024 * 1024:
        raise ValueError("File size exceeds the maximum limit of 5MB.")

    if not filename.endswith(".csv"):
        raise ValueError("Only CSV format is supported.")

    # 2. Validate Character Encoding
    try:
        csv_data = file_content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            csv_data = file_content.decode('latin-1')
        except Exception as e:
            raise ValueError(f"Failed to decode file. Unsupported character encoding: {e}")

    # Read first line to get headers
    lines = io.StringIO(csv_data)
    first_line_reader = csv.reader(lines)
    try:
        header = next(first_line_reader)
    except StopIteration:
        raise ValueError("Empty CSV file uploaded.")

    # Normalize headers
    normalized_header = []
    for col in header:
        col_clean = col.strip().lower()
        if col_clean in ['stock count', 'stock_count']:
            normalized_header.append('stock_count')
        elif col_clean in ['image urls', 'image_urls']:
            normalized_header.append('image_urls')
        elif col_clean in ['video urls', 'video_urls']:
            normalized_header.append('video_urls')
        else:
            normalized_header.append(col_clean)

    required_cols = ['sku', 'name', 'price', 'color', 'category', 'fabric', 'stock_count']
    missing_cols = [col for col in required_cols if col not in normalized_header]
    if missing_cols:
        raise ValueError(f"Missing required columns in CSV: {', '.join(missing_cols)}")

    # Setup reader starting from line 2
    lines.seek(0)
    next(lines)
    reader = csv.DictReader(lines, fieldnames=normalized_header)

    errors = []
    rows_to_process = []
    seen_skus = set()
    seen_names = set()

    url_regex = re.compile(
        r'^(?:http|ftp)s?://' # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|' # domain...
        r'localhost|' # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})' # ...or ip
        r'(?::\d+)?' # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)

    for idx, row in enumerate(reader, start=2):
        if not row or all(not val.strip() for val in row.values() if val):
            continue
            
        sku = (row.get('sku') or '').strip()
        name = (row.get('name') or '').strip()
        price_val = (row.get('price') or '').strip()
        color = (row.get('color') or '').strip()
        category_name = (row.get('category') or '').strip()
        fabric = (row.get('fabric') or '').strip()
        stock_val = (row.get('stock_count') or '').strip()

        row_errors = []

        # SKU validation
        if not sku:
            row_errors.append("SKU is empty")
        elif sku in seen_skus:
            row_errors.append(f"Duplicate SKU '{sku}' found in CSV")
        else:
            seen_skus.add(sku)

        # Name validation
        if not name:
            row_errors.append("Name is empty")
        elif name.lower() in seen_names:
            # We allow it, but record a warning/log or enforce uniqueness if requested
            pass
        else:
            seen_names.add(name.lower())

        # Color validation
        if not color:
            row_errors.append("Color is empty")

        # Category validation
        if not category_name:
            row_errors.append("Category is empty")
        elif len(category_name) < 2 or len(category_name) > 50:
            row_errors.append(f"Category name '{category_name}' must be between 2 and 50 characters")

        # Fabric validation
        if not fabric:
            row_errors.append("Fabric is empty")

        # Price validation
        if not price_val:
            row_errors.append("Price is empty")
        else:
            # Handle currency symbols if present (e.g. ₹, $, INR)
            clean_price = re.sub(r'[^\d.-]', '', price_val)
            try:
                price = Decimal(clean_price)
                if price < 0:
                    row_errors.append("Price cannot be negative")
            except Exception:
                row_errors.append(f"Invalid price format '{price_val}'")

        # Stock validation
        if not stock_val:
            row_errors.append("Stock count is empty")
        else:
            try:
                stock_count = int(stock_val)
                if stock_count < 0:
                    row_errors.append("Stock count cannot be negative")
            except Exception:
                row_errors.append(f"Invalid stock count value '{stock_val}'")

        # Sizes validation
        sizes_val = (row.get('sizes') or '').strip()
        sizes = [s.strip() for s in sizes_val.split(',') if s.strip()]
        
        # Image URLs validation
        image_val = (row.get('image_urls') or '').strip()
        image_urls = [url.strip() for url in image_val.split(',') if url.strip()]
        for url in image_urls:
            if not url_regex.match(url):
                row_errors.append(f"Invalid image URL format: '{url}'")

        # Video URLs validation
        video_val = (row.get('video_urls') or '').strip()
        video_urls = [url.strip() for url in video_val.split(',') if url.strip()]
        for url in video_urls:
            if not url_regex.match(url):
                row_errors.append(f"Invalid video URL format: '{url}'")

        if row_errors:
            errors.append(f"Row {idx}: {', '.join(row_errors)}")
        else:
            row_data = {
                'sku': sku,
                'name': name,
                'price': Decimal(clean_price),
                'color': color,
                'category_name': category_name,
                'gender': (row.get('gender') or 'Unisex').strip(),
                'fabric': fabric,
                'description': (row.get('description') or '').strip(),
                'stock_count': int(stock_val),
                'sizes': sizes,
                'image_urls': image_urls,
                'video_urls': video_urls,
            }
            rows_to_process.append(row_data)

    if errors:
        error_msg = "; ".join(errors[:20])
        if len(errors) > 20:
            error_msg += f" ... and {len(errors) - 20} more errors."
        raise ValueError(f"Catalog validation failed: {error_msg}")

    products_created = 0
    products_updated = 0

    for r in rows_to_process:
        # Create/Find category
        category = db.query(models.Category).filter(
            models.Category.organization_id == org_id,
            models.Category.name.ilike(r['category_name'])
        ).first()

        if not category:
            category = models.Category(organization_id=org_id, name=r['category_name'])
            db.add(category)
            db.commit()
            db.refresh(category)

        # Search existing product
        product = db.query(models.Product).filter(
            models.Product.organization_id == org_id,
            models.Product.sku == r['sku']
        ).first()

        if product:
            product.category_id = category.id
            product.name = r['name']
            product.gender = r['gender']
            product.price = r['price']
            product.color = r['color']
            product.fabric = r['fabric']
            product.description = r['description']
            product.sizes = r['sizes']
            product.stock_count = r['stock_count']
            product.image_urls = r['image_urls']
            product.video_urls = r['video_urls']
            # Re-trigger embedding generation asynchronously
            product.embedding_status = "pending"
            products_updated += 1
        else:
            product = models.Product(
                organization_id=org_id,
                category_id=category.id,
                sku=r['sku'],
                name=r['name'],
                gender=r['gender'],
                price=r['price'],
                color=r['color'],
                fabric=r['fabric'],
                description=r['description'],
                sizes=r['sizes'],
                stock_count=r['stock_count'],
                image_urls=r['image_urls'],
                video_urls=r['video_urls'],
                embedding_status="pending"
            )
            db.add(product)
            products_created += 1

        db.commit()
        db.refresh(product)
        # Schedule the vector embedding generator task
        background_tasks.add_task(generate_product_embedding_task, SessionLocal, str(product.id))

    return {
        "status": "success",
        "created": products_created,
        "updated": products_updated
    }
