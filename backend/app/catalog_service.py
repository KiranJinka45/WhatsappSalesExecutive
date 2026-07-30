import csv
import io
import re
import logging
from sqlalchemy.orm import Session
from decimal import Decimal
from fastapi import BackgroundTasks
from pydantic import BaseModel, Field, field_validator, ValidationError
from typing import List, Optional
from . import models
from .database import SessionLocal, tenant_var

logger = logging.getLogger(__name__)

class CatalogRow(BaseModel):
    sku: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    price: Decimal = Field(..., ge=0)
    color: str = Field(..., min_length=1)
    category_name: str = Field(..., min_length=2, max_length=50)
    gender: str = Field(default="Unisex")
    fabric: str = Field(..., min_length=1)
    description: str = Field(default="")
    stock_count: int = Field(..., ge=0)
    sizes: List[str] = Field(default_factory=list)
    image_urls: List[str] = Field(default_factory=list)
    video_urls: List[str] = Field(default_factory=list)

    @field_validator("image_urls", "video_urls", mode="before")
    def split_urls(cls, v):
        if isinstance(v, str):
            return [url.strip() for url in v.split(",") if url.strip()]
        return v

    @field_validator("sizes", mode="before")
    def split_sizes(cls, v):
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

def generate_product_embedding_task(db_session_factory, product_id: str):
    """
    Background task to generate product vector embedding and image embedding asynchronously.
    """
    db = db_session_factory()
    token = tenant_var.set(None)  # Bypass tenant filtering to query globally by ID
    try:
        product = db.query(models.Product).filter(models.Product.id == product_id).first()
        if not product:
            return
            
        # 1. Text embedding generation
        product.embedding_status = "processing"
        db.commit()
        
        cat_name = product.category.name if product.category else "Uncategorized"
        embed_text = f"Product: {product.name}. Category: {cat_name}. Gender: {product.gender or 'Unisex'}. Price: INR {product.price}. Color: {product.color}. Fabric: {product.fabric or ''}. Description: {product.description or ''}."
        
        from .ai_service import get_embedding
        embedding = get_embedding(embed_text)
        
        if embedding and any(v != 0.0 for v in embedding):
            product.embedding = embedding
            product.embedding_status = "completed"
        else:
            product.embedding_status = "failed"
        db.commit()
        
        # 2. Image embedding generation (multimodal embedding)
        if product.image_urls and len(product.image_urls) > 0:
            product.image_embedding_status = "processing"
            db.commit()
            
            first_img_url = product.image_urls[0]
            # Simple placeholder bypass
            if "via.placeholder.com" in first_img_url or "placehold.co" in first_img_url:
                product.image_embedding_status = "failed"
                db.commit()
            else:
                try:
                    import httpx
                    logger.info(f"Downloading catalog image for embedding: {first_img_url}")
                    img_resp = httpx.get(first_img_url, timeout=20.0)
                    if img_resp.status_code == 200:
                        img_bytes = img_resp.content
                        from .ai_service import get_image_embedding
                        img_emb = get_image_embedding(img_bytes)
                        if img_emb and any(v != 0.0 for v in img_emb):
                            product.image_embedding = img_emb
                            product.image_embedding_status = "completed"
                            logger.info(f"Image embedding succeeded for product ID: {product_id}")
                        else:
                            product.image_embedding_status = "failed"
                            logger.error(f"Image embedding generated zero/empty vector for product ID: {product_id}")
                    else:
                        product.image_embedding_status = "failed"
                        logger.error(f"Failed to download catalog image for product ID: {product_id}. Status: {img_resp.status_code}")
                except Exception as img_err:
                    product.image_embedding_status = "failed"
                    logger.error(f"Image embedding failed for product {product_id}: {img_err}", exc_info=True)
                db.commit()
        else:
            product.image_embedding_status = "none"
            db.commit()
            
    except Exception as e:
        logger.error(f"Failed async embedding for product {product_id}: {e}")
        try:
            product = db.query(models.Product).filter(models.Product.id == product_id).first()
            if product:
                product.embedding_status = "failed"
                product.image_embedding_status = "failed"
                db.commit()
        except Exception as db_err:
            logger.warning("Error resetting database session during catalog import: %s", str(db_err))
    finally:
        db.close()
        tenant_var.reset(token)

def backfill_missing_image_embeddings(db_session_factory):
    """
    Scans the database for catalog products with images that are missing image embeddings,
    and runs the embedding generator task for them in a background thread.
    """
    db = db_session_factory()
    token = tenant_var.set(None)
    try:
        # Find products that have image_urls but image_embedding is NULL or image_embedding_status is pending/failed
        from sqlalchemy import and_, or_
        pending_products = db.query(models.Product).filter(
            models.Product.image_urls != None,
            models.Product.image_embedding_status.in_(["pending", "failed"])
        ).all()
        
        if pending_products:
            logger.info(f"Backfill: Found {len(pending_products)} products with pending image embeddings. Scheduling tasks...")
            import threading
            for prod in pending_products:
                # Run embedding task in a background daemon thread
                t = threading.Thread(
                    target=generate_product_embedding_task,
                    args=(db_session_factory, str(prod.id)),
                    daemon=True
                )
                t.start()
    except Exception as e:
        logger.error(f"Error during image embedding backfill scan: {e}")
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

    # Normalize line endings to standard Unix newline '\n' (handles \r\n and Classic Mac \r)
    csv_data = csv_data.replace('\r\n', '\n').replace('\r', '\n')

    # Read first line to get headers
    lines = io.StringIO(csv_data)
    first_line_reader = csv.reader(lines)
    try:
        header = next(first_line_reader)
    except StopIteration:
        raise ValueError("Empty CSV file uploaded.")

    # Normalize headers dynamically to handle common CSV column aliases
    normalized_header = []
    for col in header:
        col_clean = col.strip().lower()
        if col_clean in ['stock count', 'stock_count', 'stock', 'qty', 'quantity', 'inventory']:
            normalized_header.append('stock_count')
        elif col_clean in ['price (inr)', 'price(inr)', 'price_inr', 'price', 'mrp', 'amount', 'cost']:
            normalized_header.append('price')
        elif col_clean in ['category_name', 'category name', 'category']:
            normalized_header.append('category')
        elif col_clean in ['image urls', 'image_urls', 'images', 'image_url']:
            normalized_header.append('image_urls')
        elif col_clean in ['video urls', 'video_urls', 'videos', 'video_url']:
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

    for idx, row in enumerate(reader, start=2):
        if not row or all(not val.strip() for val in row.values() if val):
            continue
            
        # Pre-process some fields before Pydantic validation
        raw_price = (row.get('price') or '').strip()
        clean_price = re.sub(r'[^\d.-]', '', raw_price) if raw_price else ''
        
        row_dict = {
            'sku': (row.get('sku') or '').strip(),
            'name': (row.get('name') or '').strip(),
            'price': clean_price or None,
            'color': (row.get('color') or '').strip(),
            'category_name': (row.get('category') or '').strip(),
            'gender': (row.get('gender') or 'Unisex').strip(),
            'fabric': (row.get('fabric') or '').strip(),
            'description': (row.get('description') or '').strip(),
            'stock_count': (row.get('stock_count') or '').strip() or None,
            'sizes': (row.get('sizes') or '').strip(),
            'image_urls': (row.get('image_urls') or '').strip(),
            'video_urls': (row.get('video_urls') or '').strip(),
        }

        try:
            valid_row = CatalogRow(**row_dict)
            if valid_row.sku in seen_skus:
                errors.append(f"Row {idx}: Duplicate SKU '{valid_row.sku}' found in CSV")
            else:
                seen_skus.add(valid_row.sku)
                rows_to_process.append((idx, valid_row))
        except ValidationError as e:
            # Format Pydantic errors nicely
            err_msgs = []
            for err in e.errors():
                loc = ".".join([str(l) for l in err["loc"]])
                err_msgs.append(f"{loc}: {err['msg']}")
            errors.append(f"Row {idx}: {'; '.join(err_msgs)}")

    if errors:
        # Check if there is a negative price error to customize message
        price_errs = [e for e in errors if "price" in e.lower() and ("greater than or equal to 0" in e.lower() or "less than" in e.lower() or "negative" in e.lower())]
        if price_errs:
            raise ValueError("Price cannot be negative")
        raise ValueError(f"Validation failed: {'; '.join(errors)}")

    products_created = 0
    products_updated = 0

    for row_idx, valid_row in rows_to_process:
        # Create/Find category
        category = db.query(models.Category).filter(
            models.Category.organization_id == org_id,
            models.Category.name.ilike(valid_row.category_name)
        ).first()

        if not category:
            category = models.Category(organization_id=org_id, name=valid_row.category_name)
            db.add(category)
            db.commit()
            db.refresh(category)

        # Search existing product
        product = db.query(models.Product).filter(
            models.Product.organization_id == org_id,
            models.Product.sku == valid_row.sku
        ).first()

        if product:
            product.category_id = category.id
            product.name = valid_row.name
            product.gender = valid_row.gender
            product.price = valid_row.price
            product.color = valid_row.color
            product.fabric = valid_row.fabric
            product.description = valid_row.description
            product.sizes = valid_row.sizes
            product.stock_count = valid_row.stock_count
            product.image_urls = valid_row.image_urls
            product.video_urls = valid_row.video_urls
            # Re-trigger embedding generation asynchronously
            product.embedding_status = "pending"
            products_updated += 1
        else:
            product = models.Product(
                organization_id=org_id,
                category_id=category.id,
                sku=valid_row.sku,
                name=valid_row.name,
                gender=valid_row.gender,
                price=valid_row.price,
                color=valid_row.color,
                fabric=valid_row.fabric,
                description=valid_row.description,
                sizes=valid_row.sizes,
                stock_count=valid_row.stock_count,
                image_urls=valid_row.image_urls,
                video_urls=valid_row.video_urls,
                embedding_status="pending"
            )
            db.add(product)
            products_created += 1

        db.commit()
        db.refresh(product)
        # Schedule the vector embedding generator task
        background_tasks.add_task(generate_product_embedding_task, SessionLocal, str(product.id))

    status_msg = "success" if not errors else "partial_success"
    if not rows_to_process and errors:
        status_msg = "failed"
        
    return {
        "status": status_msg,
        "created": products_created,
        "updated": products_updated,
        "invalid_rows": len(errors),
        "errors": errors
    }
