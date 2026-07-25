from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..database import get_db
from .. import models, schemas, security

router = APIRouter(prefix="/api/brand", tags=["brand"], responses={401: {"description": "Unauthorized"}, 400: {"description": "Bad Request"}})

@router.get("/profile", response_model=schemas.OrganizationOut)
def get_brand_profile(org: models.Organization = Depends(security.get_current_org)):
    return org

@router.put("/profile", response_model=schemas.OrganizationOut)
def update_brand_profile(
    profile_in: schemas.OrganizationUpdate,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    update_data = profile_in.model_dump(exclude_unset=True)
    
    # Check duplicate WhatsApp number
    if "whatsapp_number" in update_data and update_data["whatsapp_number"] != org.whatsapp_number:
        num = update_data["whatsapp_number"]
        exists = db.query(models.Organization).filter(models.Organization.whatsapp_number == num).first()
        if exists:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This WhatsApp number is already connected to another brand."
            )

    for field, value in update_data.items():
        if field == "policies" and org.policies:
            # Shallow merge policies instead of fully overwriting
            merged = org.policies.copy()
            merged.update(value)
            org.policies = merged
        else:
            setattr(org, field, value)

    db.commit()
    db.refresh(org)
    return org

@router.delete("/profile", status_code=status.HTTP_204_NO_CONTENT)
def delete_brand_profile(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.require_role("owner"))
):
    from sqlalchemy.sql import func
    # Soft delete the organization
    org.deleted_at = func.now()
    # Soft delete all conversations of this organization
    db.query(models.Conversation).filter(models.Conversation.organization_id == org.id).update(
        {models.Conversation.deleted_at: func.now()},
        synchronize_session=False
    )
    # Soft delete all orders and order items of this organization
    order_ids = [r[0] for r in db.query(models.Order.id).filter(models.Order.organization_id == org.id).all()]
    if order_ids:
        db.query(models.Order).filter(models.Order.organization_id == org.id).update(
            {models.Order.deleted_at: func.now()},
            synchronize_session=False
        )
        db.query(models.OrderItem).filter(models.OrderItem.order_id.in_(order_ids)).update(
            {models.OrderItem.deleted_at: func.now()},
            synchronize_session=False
        )
    db.commit()
    return None
