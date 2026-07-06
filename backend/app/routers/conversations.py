from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import asyncio
import json
from ..database import get_db
from .. import models, schemas, security
from ..connection_manager import manager

router = APIRouter(prefix="/api/conversations", tags=["conversations"])

@router.get("/stream")
async def stream_conversations(
    org: models.Organization = Depends(security.get_current_org)
):
    """
    Exposes an SSE stream of real-time incoming messages, AI replies,
    and conversation status transitions for the active organization.
    """
    queue = manager.register(str(org.id))

    async def event_generator():
        try:
            while True:
                try:
                    # Wait for next event with a timeout for keepalive heartbeat
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send a keepalive ping comment to keep connection active
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            manager.disconnect(str(org.id), queue)
        except Exception:
            manager.disconnect(str(org.id), queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("", response_model=List[schemas.ConversationOut])
def get_conversations(
    status_filter: Optional[str] = Query(None, description="ai_active, human_takeover, resolved"),
    assigned: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    query = db.query(models.Conversation).filter(models.Conversation.organization_id == org.id)
    
    if status_filter:
        query = query.filter(models.Conversation.status == status_filter)
    if assigned is True:
        query = query.filter(models.Conversation.assigned_user_id.isnot(None))
    elif assigned is False:
        query = query.filter(models.Conversation.assigned_user_id.is_(None))

    return query.order_by(models.Conversation.updated_at.desc()).offset(offset).limit(limit).all()

@router.get("/{id}", response_model=schemas.ConversationDetail)
def get_conversation_detail(
    id: UUID,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org.id,
        models.Conversation.id == id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return conv

@router.post("/{id}/takeover", response_model=schemas.ConversationOut)
def toggle_takeover(
    id: UUID,
    status_val: str = Query(..., description="ai_active, human_takeover, resolved"),
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    if status_val not in ["ai_active", "human_takeover", "resolved"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value")
        
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org.id,
        models.Conversation.id == id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conv.status = status_val
    if status_val == "human_takeover":
        conv.assigned_user_id = current_user.id
    elif status_val == "ai_active":
        conv.assigned_user_id = None
        
    db.commit()
    db.refresh(conv)
    
    # Broadcast status change event to connected merchant streams
    manager.broadcast(str(org.id), "status_change", {
        "conversation_id": str(conv.id),
        "status": conv.status
    })
    return conv

@router.post("/{id}/messages", response_model=schemas.MessageOut, status_code=status.HTTP_201_CREATED)
def send_agent_message(
    id: UUID,
    msg_in: schemas.MessageCreate,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org.id,
        models.Conversation.id == id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    # Force status to human_takeover and assign user since agent replied manually
    conv.status = "human_takeover"
    conv.assigned_user_id = current_user.id

    new_msg = models.Message(
        conversation_id=conv.id,
        sender="human",
        message_type="text",
        content=msg_in.content
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)
    
    # Broadcast new manual message to connected merchant streams
    manager.broadcast(str(org.id), "new_message", {
        "conversation_id": str(conv.id),
        "message": {
            "id": str(new_msg.id),
            "sender": new_msg.sender,
            "message_type": new_msg.message_type,
            "content": new_msg.content,
            "created_at": new_msg.created_at.isoformat()
        }
    })
    
    # Trigger real outbound BSP API payload dispatch
    from ..bsp_service import send_whatsapp_message
    send_whatsapp_message(conv.customer_phone, msg_in.content, org)
    
    return new_msg
