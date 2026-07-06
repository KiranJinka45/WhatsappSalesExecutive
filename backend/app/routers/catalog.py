from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional
from decimal import Decimal
from ..database import get_db, SessionLocal
from .. import models, schemas, security, catalog_service
from ..catalog_service import generate_product_embedding_task

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

@router.post("/upload", status_code=status.HTTP_200_OK)
async def upload_catalog(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    if not file.filename.endswith(('.csv', '.xlsx', '.xls')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Upload CSV or Excel file."
        )
    try:
        contents = await file.read()
        result = catalog_service.parse_and_sync_catalog(
            db, str(org.id), contents, file.filename, background_tasks
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

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
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    # Base query filters are handled by SQLAlchemy tenant compiled query hook automatically
    query = db.query(models.Product)

    # If semantic search is requested, query similarity using pgvector
    if q:
        from ..ai_service import get_embedding
        query_embedding = get_embedding(q)
        # We only retrieve products with completed embeddings for similarity orderings
        query = query.filter(models.Product.embedding_status == "completed").order_by(
            models.Product.embedding.cosine_distance(query_embedding)
        )
    else:
        # Default chronological ordering
        query = query.order_by(models.Product.created_at.desc())

    # Apply structured filters
    if category_id:
        query = query.filter(models.Product.category_id == category_id)
    if gender:
        query = query.filter(models.Product.gender.ilike(gender))
    if min_price is not None:
        query = query.filter(models.Product.price >= min_price)
    if max_price is not None:
        query = query.filter(models.Product.price <= max_price)
    if color:
        query = query.filter(models.Product.color.ilike(color))
    if fabric:
        query = query.filter(models.Product.fabric.ilike(fabric))
    if in_stock is True:
        query = query.filter(models.Product.stock_count > 0)
    elif in_stock is False:
        query = query.filter(models.Product.stock_count == 0)

    return query.offset(offset).limit(limit).all()

@router.post("/products", response_model=schemas.ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(
    product_in: schemas.ProductCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    # Check duplicate SKU
    existing = db.query(models.Product).filter(
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

@router.put("/products/{id}", response_model=schemas.ProductOut)
def update_product(
    id: str,
    product_in: schemas.ProductUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    product = db.query(models.Product).filter(
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

@router.delete("/products/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    id: str,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    product = db.query(models.Product).filter(
        models.Product.id == id
    ).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    
    db.delete(product)
    db.commit()
    return None
