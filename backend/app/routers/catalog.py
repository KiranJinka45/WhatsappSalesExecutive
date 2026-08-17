import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from ..database import get_db, SessionLocal
from .. import models, schemas, security, catalog_service

logger = logging.getLogger(__name__)
from ..catalog_service import generate_product_embedding_task

router = APIRouter(prefix="/api/catalog", tags=["catalog"], responses={401: {"description": "Unauthorized"}, 400: {"description": "Bad Request"}})

@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_catalog(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    mode: str = Query("atomic", description="Import mode: 'atomic' or 'partial'"),
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Upload CSV or Excel file."
        )
    try:
        contents = await file.read()
        result = catalog_service.parse_and_sync_catalog(
            db, str(org.id), contents, file.filename, background_tasks, mode=mode
        )
        return result
    except ValueError as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(ve)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )

import uuid
import os
from fastapi import Request

@router.post("/upload-image", status_code=status.HTTP_201_CREATED)
async def upload_catalog_image(
    request: Request,
    file: UploadFile = File(...),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (JPEG, PNG, WebP, etc.)."
        )
    
    ext = os.path.splitext(file.filename)[1] or ".jpg"
    unique_filename = f"{org.id}_{uuid.uuid4().hex[:10]}{ext}"
    upload_dir = "static/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, unique_filename)
    
    contents = await file.read()
    with open(file_path, "wb") as f:
        f.write(contents)
    
    base_url = str(request.base_url).rstrip("/")
    if "onrender.com" in base_url and base_url.startswith("http://"):
        base_url = base_url.replace("http://", "https://")
    
    image_url = f"{base_url}/static/uploads/{unique_filename}"
    return {"url": image_url, "filename": unique_filename}

from sqlalchemy import or_

@router.get("/products", response_model=List[schemas.ProductOut])
def get_products(
    q: Optional[str] = Query(None, description="Semantic search query"),
    category_id: Optional[str] = Query(None),
    gender: Optional[str] = Query(None),
    min_price: Optional[Decimal] = Query(None),
    max_price: Optional[Decimal] = Query(None),
    color: Optional[str] = Query(None),
    fabric: Optional[str] = Query(None),
    in_stock: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    extracted_entities = {}
    if q and q.strip():
        try:
            from ..ai.entity_extractor import extract_entities
            extracted_entities = extract_entities(q)
        except Exception as err:
            logger.warning(f"Entity extraction failed for query '{q}': {err}")

    # Merge extracted entities if explicit parameters were not supplied
    if min_price is None and extracted_entities.get("budget_min") is not None:
        try:
            min_price = Decimal(str(extracted_entities["budget_min"]))
        except Exception:
            pass
    if max_price is None and extracted_entities.get("budget_max") is not None:
        try:
            max_price = Decimal(str(extracted_entities["budget_max"]))
        except Exception:
            pass
    if color is None and extracted_entities.get("color"):
        color = str(extracted_entities["color"])
    if fabric is None and extracted_entities.get("fabric"):
        fabric = str(extracted_entities["fabric"])
    if gender is None and extracted_entities.get("gender"):
        gender = str(extracted_entities["gender"])

    query = db.query(models.Product)

    # 1. Apply all structured filters first
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    elif extracted_entities.get("product_type"):
        cat_name = str(extracted_entities["product_type"])
        query = query.join(models.Category, isouter=True).filter(
            or_(models.Category.name.ilike(f"%{cat_name}%"), models.Product.name.ilike(f"%{cat_name}%"))
        )

    if gender:
        query = query.filter(or_(models.Product.gender.ilike(f"%{gender}%"), models.Product.gender.is_(None)))
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)
    if color:
        query = query.filter(models.Product.color.ilike(f"%{color}%"))
    if fabric:
        query = query.filter(models.Product.fabric.ilike(f"%{fabric}%"))
    if in_stock is True:
        query = query.filter(models.Product.stock_count > 0)
    elif in_stock is False:
        query = query.filter(models.Product.stock_count == 0)

    # 2. Search execution: If structured entities were extracted, return entity-filtered results deterministically
    has_structured_filters = bool(
        category_id or gender or min_price is not None or max_price is not None or color or fabric or extracted_entities.get("product_type")
    )

    if has_structured_filters:
        entity_results = query.order_by(models.Product.created_at.desc()).offset(offset).limit(limit).all()
        if entity_results:
            return entity_results

    # 3. Fallback text or vector similarity search if query provided and no structured results found
    if q and q.strip():
        search_str = q.strip()
        pattern = f"%{search_str}%"

        # Check for direct text matches across fields
        text_match_query = query.filter(
            or_(
                models.Product.sku.ilike(pattern),
                models.Product.name.ilike(pattern),
                models.Product.color.ilike(pattern),
                models.Product.fabric.ilike(pattern),
                models.Product.description.ilike(pattern)
            )
        )
        text_results = text_match_query.offset(offset).limit(limit).all()
        if text_results:
            return text_results

        # Fallback to vector semantic search
        try:
            from ..ai_service import get_embedding
            query_embedding = get_embedding(search_str)
            if query_embedding and any(v != 0 for v in query_embedding):
                query = query.filter(models.Product.embedding_status == "completed").order_by(
                    models.Product.embedding.cosine_distance(query_embedding)
                )
            else:
                query = query.order_by(models.Product.created_at.desc())
        except Exception as err:
            logger.warning(f"Vector search failed: {err}")
            query = query.order_by(models.Product.created_at.desc())
    else:
        query = query.order_by(models.Product.created_at.desc())

    return query.offset(offset).limit(limit).all()

@router.post("/products", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: schemas.ProductCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    # Check duplicate SKU
    existing = db.query(models.Product).filter(
        models.Product.organization_id == org.id,
        models.Product.sku == product_in.sku
    ).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Product SKU {product_in.sku} already exists."
        )

    # Category resolver
    cat_id = None
    if product_in.category_name:
        category = db.query(models.Category).filter(
            models.Category.organization_id == org.id,
            models.Category.name.ilike(product_in.category_name)
        ).first()
        if not category:
            category = models.Category(organization_id=org.id, name=product_in.category_name)
            db.add(category)
            db.commit()
            db.refresh(category)
        cat_id = category.id

    new_prod = models.Product(
        organization_id=org.id,
        category_id=cat_id,
        sku=product_in.sku,
        name=product_in.name,
        gender=product_in.gender,
        price=product_in.price,
        color=product_in.color,
        fabric=product_in.fabric,
        description=product_in.description,
        sizes=product_in.sizes,
        stock_count=product_in.stock_count,
        image_urls=product_in.image_urls,
        video_urls=product_in.video_urls,
        embedding_status="pending"
    )
    db.add(new_prod)
    db.commit()
    db.refresh(new_prod)

    # Schedule the embedding generation asynchronously
    background_tasks.add_task(generate_product_embedding_task, SessionLocal, str(new_prod.id))
    return new_prod

@router.put("/products/{id}", response_model=schemas.ProductOut, responses={404: {"description": "Product not found"}})
def update_product(
    id: str,
    product_in: schemas.ProductUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    product = db.query(models.Product).filter(
        models.Product.organization_id == org.id,
        models.Product.id == id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    update_data = product_in.model_dump(exclude_unset=True)

    # Handle Category Update
    if "category_name" in update_data:
        category_name = update_data.pop("category_name")
        if category_name:
            category = db.query(models.Category).filter(
                models.Category.organization_id == org.id,
                models.Category.name.ilike(category_name)
            ).first()
            if not category:
                category = models.Category(organization_id=org.id, name=category_name)
                db.add(category)
                db.commit()
                db.refresh(category)
            product.category_id = category.id
        else:
            product.category_id = None

    # Apply updates
    for field, value in update_data.items():
        setattr(product, field, value)

    # Mark status as pending for recalculation
    product.embedding_status = "pending"
    db.commit()
    db.refresh(product)

    # Schedule the embedding generation asynchronously
    background_tasks.add_task(generate_product_embedding_task, SessionLocal, str(product.id))
    return product

@router.delete("/products/{id}", status_code=status.HTTP_204_NO_CONTENT, responses={404: {"description": "Product not found"}})
def delete_product(
    id: str,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    product = db.query(models.Product).filter(
        models.Product.organization_id == org.id,
        models.Product.id == id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    db.delete(product)
    db.commit()
    return None

@router.get("/public/products", responses={404: {"description": "Store not found"}})
def get_public_products(
    tenant_slug: str = Query(..., description="Slugified name of the store"),
    category: Optional[str] = Query(None),
    min_price: Optional[Decimal] = Query(None),
    max_price: Optional[Decimal] = Query(None),
    db: Session = Depends(get_db)
):
    import re
    # 1. Resolve organization by slug
    def get_slug(name: str) -> str:
        return re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')

    orgs = db.query(models.Organization).all()
    target_org = None
    for o in orgs:
        if get_slug(o.name) == tenant_slug:
            target_org = o
            break
            
    if not target_org:
        # Fallback to direct name prefix matching
        for o in orgs:
            if tenant_slug.replace('-', ' ') in o.name.lower():
                target_org = o
                break

    if not target_org:
        raise HTTPException(status_code=404, detail="Store not found")

    # 2. Query products scoped by target organization and active status
    query = db.query(models.Product).filter(
        models.Product.organization_id == target_org.id,
        models.Product.stock_count > 0
    )

    # 3. Apply category filter (fuzzy text match category name, fabric, or product name)
    if category and category.strip():
        cat_pat = f"%{category.strip()}%"
        # We can join with categories or just check product attributes
        query = query.filter(
            or_(
                models.Product.name.ilike(cat_pat),
                models.Product.fabric.ilike(cat_pat),
                models.Product.color.ilike(cat_pat)
            )
        )

    # 4. Apply price range limits
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)

    # 5. Order by price ascending
    products = query.order_by(models.Product.price.asc()).limit(50).all()

    # 6. Format response structure
    res_list = []
    for p in products:
        res_list.append({
            "id": str(p.id),
            "name": p.name,
            "price": float(p.price),
            "image_url": p.image_urls[0] if p.image_urls and len(p.image_urls) > 0 else "https://via.placeholder.com/300"
        })
    return res_list
