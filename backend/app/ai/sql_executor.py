from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import logging
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, text
from .schemas import ProductSearchCriteria, GroundedProductResult
from .. import models
from ..database import tenant_var

logger = logging.getLogger(__name__)


def execute_deterministic_catalog_query(
    db: Session,
    org_id: UUID,
    criteria: Optional[ProductSearchCriteria] = None,
    limit: int = 5
) -> Tuple[List[GroundedProductResult], Dict[str, float], Dict[str, int]]:
    """
    Deterministic SQL Query Execution (Layer 2).
    Enforces tenant isolation via PostgreSQL RLS and strict organization_id filtering.
    Translates extracted Pydantic criteria into deterministic SQL query.
    Returns:
        - List of GroundedProductResult items
        - price_snapshot: Dict[sku, price]
        - stock_snapshot: Dict[sku, stock_count]
    """
    # 1. Enforce PostgreSQL RLS context
    tenant_var.set(org_id)
    db.organization_id = org_id
    try:
        db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org_id)})
    except Exception as e:
        logger.warning(f"Could not set app.current_tenant SQL local: {e}")

    query = db.query(models.Product).filter(
        models.Product.organization_id == org_id
    )

    if criteria:
        # Stock filter
        if criteria.is_in_stock_only:
            query = query.filter(models.Product.stock_count > 0)

        # Budget filters
        if criteria.budget_min is not None and criteria.budget_min > 0:
            query = query.filter(models.Product.price >= criteria.budget_min)
        if criteria.budget_max is not None and criteria.budget_max > 0:
            query = query.filter(models.Product.price <= criteria.budget_max)

        # Color filter
        if criteria.color:
            query = query.filter(models.Product.color.ilike(f"%{criteria.color.strip()}%"))

        # Fabric filter
        if criteria.fabric:
            query = query.filter(models.Product.fabric.ilike(f"%{criteria.fabric.strip()}%"))

        # Product Type / Category filter
        if criteria.product_type:
            pt = criteria.product_type.strip()
            query = query.filter(
                or_(
                    models.Product.name.ilike(f"%{pt}%"),
                    models.Product.description.ilike(f"%{pt}%"),
                    models.Product.fabric.ilike(f"%{pt}%")
                )
            )

        # Keyword filters
        if criteria.keywords:
            kw_filters = []
            for kw in criteria.keywords:
                if len(kw.strip()) >= 3:
                    kw_clean = kw.strip()
                    kw_filters.append(models.Product.name.ilike(f"%{kw_clean}%"))
                    kw_filters.append(models.Product.description.ilike(f"%{kw_clean}%"))
                    kw_filters.append(models.Product.sku.ilike(f"%{kw_clean}%"))
            if kw_filters:
                query = query.filter(or_(*kw_filters))

    # Order by in-stock priority and price
    products = query.order_by(models.Product.stock_count.desc(), models.Product.price.asc()).limit(limit).all()

    # Fallback: if specific combination yielded 0 results, retrieve closest available in same budget / category
    if not products and criteria and (criteria.budget_max or criteria.product_type):
        fallback_query = db.query(models.Product).filter(
            models.Product.organization_id == org_id,
            models.Product.stock_count > 0
        )
        if criteria.budget_max:
            fallback_query = fallback_query.filter(models.Product.price <= criteria.budget_max * 1.25)
        if criteria.product_type:
            fallback_query = fallback_query.filter(models.Product.name.ilike(f"%{criteria.product_type.strip()}%"))
        products = fallback_query.order_by(models.Product.price.asc()).limit(limit).all()

    # If still empty, return top available products for general inquiry
    if not products:
        products = db.query(models.Product).filter(
            models.Product.organization_id == org_id,
            models.Product.stock_count > 0
        ).order_by(models.Product.created_at.desc()).limit(limit).all()

    grounded_results: List[GroundedProductResult] = []
    price_snapshot: Dict[str, float] = {}
    stock_snapshot: Dict[str, int] = {}

    for p in products:
        item = GroundedProductResult(
            id=str(p.id),
            sku=p.sku,
            name=p.name,
            price=float(p.price),
            stock_count=int(p.stock_count or 0),
            color=p.color,
            fabric=p.fabric,
            category=p.category.name if p.category else None,
            sizes=p.sizes or [],
            image_urls=p.image_urls or [],
            description=p.description
        )
        grounded_results.append(item)
        price_snapshot[p.sku] = float(p.price)
        stock_snapshot[p.sku] = int(p.stock_count or 0)

    return grounded_results, price_snapshot, stock_snapshot
