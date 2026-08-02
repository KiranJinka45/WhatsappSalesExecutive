from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import asyncio
import json
from ..database import get_db
from .. import models, schemas, security
from ..connection_manager import manager

router = APIRouter(prefix="/api/conversations", tags=["conversations"], responses={401: {"description": "Unauthorized"}, 400: {"description": "Bad Request"}})

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
            logger.debug(f"SSE client disconnected for Org: {org.id}")
        except Exception as e:
            logger.warning(f"SSE stream error for Org {org.id}: {e}")
        finally:
            manager.disconnect(str(org.id), queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.get("", response_model=List[schemas.ConversationOut])
def get_conversations(
    status_filter: Optional[str] = Query(None, description="AI_ACTIVE, WAITING_APPROVAL, OWNER_ACTIVE, CLOSED"),
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

@router.get("/{id}", response_model=schemas.ConversationDetail, responses={404: {"description": "Conversation not found"}})
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

@router.post("/{id}/takeover", response_model=schemas.ConversationOut, responses={404: {"description": "Conversation not found"}})
def toggle_takeover(
    id: UUID,
    status_val: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    if status_val not in ["AI_ACTIVE", "WAITING_APPROVAL", "OWNER_ACTIVE", "CLOSED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status value")
        
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org.id,
        models.Conversation.id == id
    ).first()
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    conv.status = status_val
    if status_val == "OWNER_ACTIVE":
        conv.assigned_user_id = current_user.id
    elif status_val == "AI_ACTIVE":
        conv.assigned_user_id = None
        
    db.commit()
    db.refresh(conv)
    
    # Broadcast status change event to connected merchant streams
    manager.broadcast(str(org.id), "status_change", {
        "conversation_id": str(conv.id),
        "status": conv.status
    })

    # If resumed to AI_ACTIVE, trigger AI processing for the latest customer message if unreplied
    if status_val == "AI_ACTIVE":
        last_msg = db.query(models.Message).filter(
            models.Message.conversation_id == conv.id
        ).order_by(models.Message.created_at.desc()).first()
        if last_msg and last_msg.sender == "customer":
            from .webhooks import process_message_async
            background_tasks.add_task(process_message_async, str(org.id), str(conv.id), last_msg.content)

    return conv

@router.post("/{id}/messages", response_model=schemas.MessageOut, status_code=status.HTTP_201_CREATED, responses={404: {"description": "Conversation not found"}})
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

    # Force status to OWNER_ACTIVE and assign user since agent replied manually
    conv.status = "OWNER_ACTIVE"
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
            "status": new_msg.status,
            "error_message": new_msg.error_message,
            "created_at": new_msg.created_at.isoformat()
        }
    })
    
    # Trigger real outbound BSP API payload dispatch
    from ..bsp_service import send_whatsapp_message
    send_whatsapp_res = send_whatsapp_message(conv.customer_phone, msg_in.content, org)
    
    if send_whatsapp_res.get("status") == "failed":
        new_msg.status = "failed"
        new_msg.error_message = send_whatsapp_res.get("error")
        db.commit()
        
        # Broadcast updated failure status
        manager.broadcast(str(org.id), "new_message", {
            "conversation_id": str(conv.id),
            "message": {
                "id": str(new_msg.id),
                "sender": new_msg.sender,
                "message_type": new_msg.message_type,
                "content": new_msg.content,
                "status": "failed",
                "error_message": new_msg.error_message,
                "created_at": new_msg.created_at.isoformat()
            }
        })
    
    return new_msg


@router.post("/feedback", response_model=schemas.RecommendationFeedbackOut)
def log_recommendation_feedback(
    feedback: schemas.RecommendationFeedbackCreate,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    """
    Saves merchant thumbs up / down feedback for individual recommendations to build a supervised NLU database.
    """
    # Verify message exists
    msg = db.query(models.Message).filter(models.Message.id == feedback.message_id).first()
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found")

    new_fb = models.RecommendationFeedback(
        message_id=feedback.message_id,
        product_sku=feedback.product_sku,
        rating=feedback.rating,
        reason=feedback.reason
    )
    db.add(new_fb)
    db.commit()
    db.refresh(new_fb)
    return new_fb


@router.get("/approvals/pending", response_model=List[schemas.ApprovalRequestOut])
def get_pending_approvals(
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org)
):
    """
    Fetches all pending approval requests for the organization.
    """
    return db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.organization_id == org.id,
        models.ApprovalRequest.status == "pending"
    ).all()


@router.post("/approvals/{id}/respond", response_model=schemas.ConversationOut)
def respond_to_approval(
    id: UUID,
    resp: schemas.ApprovalRequestRespond,
    db: Session = Depends(get_db),
    org: models.Organization = Depends(security.get_current_org),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Action to Approve, Reject, or Edit-and-Send a proposed AI response.
    """
    approval = db.query(models.ApprovalRequest).filter(
        models.ApprovalRequest.organization_id == org.id,
        models.ApprovalRequest.id == id
    ).first()
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
        
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org.id,
        models.Conversation.id == approval.conversation_id
    ).first()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Find the pending AI message in the database
    pending_msg = db.query(models.Message).filter(
        models.Message.conversation_id == conv.id,
        models.Message.sender == "ai",
        models.Message.status == "pending"
    ).order_by(models.Message.created_at.desc()).first()

    final_text = ""
    
    if resp.action == "approve":
        approval.status = "approved"
        conv.status = "AI_ACTIVE"
        final_text = approval.proposed_response
        if pending_msg:
            pending_msg.status = "sent"
            pending_msg.content = final_text
        notification = models.Notification(
            organization_id=org.id,
            approval_request_id=approval.id,
            type="ApprovalApproved",
            status="unread"
        )
        db.add(notification)
            
    elif resp.action == "reject":
        approval.status = "rejected"
        conv.status = "OWNER_ACTIVE"
        conv.assigned_user_id = current_user.id
        if pending_msg:
            db.delete(pending_msg)
        notification = models.Notification(
            organization_id=org.id,
            approval_request_id=approval.id,
            type="ApprovalRejected",
            status="unread"
        )
        db.add(notification)
            
    elif resp.action == "edit":
        if not resp.edited_response:
            raise HTTPException(status_code=400, detail="Edited response cannot be empty")
        approval.status = "modified"
        conv.status = "AI_ACTIVE"
        final_text = resp.edited_response
        if pending_msg:
            pending_msg.status = "sent"
            pending_msg.content = final_text
        notification = models.Notification(
            organization_id=org.id,
            approval_request_id=approval.id,
            type="ApprovalEdited",
            status="unread"
        )
        db.add(notification)
            
    else:
        raise HTTPException(status_code=400, detail="Invalid action")

    db.commit()
    db.refresh(conv)

    # Broadcast conversation status change
    manager.broadcast(str(org.id), "status_change", {
        "conversation_id": str(conv.id),
        "status": conv.status
    })

    # Broadcast database message status updates if approved/edited
    if resp.action in ["approve", "edit"] and pending_msg:
        manager.broadcast(str(org.id), "new_message", {
            "conversation_id": str(conv.id),
            "message": {
                "id": str(pending_msg.id),
                "sender": pending_msg.sender,
                "message_type": pending_msg.message_type,
                "content": pending_msg.content,
                "status": pending_msg.status,
                "error_message": pending_msg.error_message,
                "created_at": pending_msg.created_at.isoformat()
            }
        })
        
        # Dispatch final message to WhatsApp Cloud API emulator/live
        from ..bsp_service import send_whatsapp_message
        send_whatsapp_res = send_whatsapp_message(conv.customer_phone, final_text, org)
        if send_whatsapp_res.get("status") == "failed":
            pending_msg.status = "failed"
            pending_msg.error_message = send_whatsapp_res.get("error")
            conv.status = "OWNER_ACTIVE"
            db.commit()
            manager.broadcast(str(org.id), "new_message", {
                "conversation_id": str(conv.id),
                "message": {
                    "id": str(pending_msg.id),
                    "sender": pending_msg.sender,
                    "message_type": pending_msg.message_type,
                    "content": pending_msg.content,
                    "status": "failed",
                    "error_message": pending_msg.error_message,
                    "created_at": pending_msg.created_at.isoformat()
                }
            })
            
    elif resp.action == "reject" and pending_msg:
        # Tell the client that the pending message was removed
        manager.broadcast(str(org.id), "message_deleted", {
            "conversation_id": str(conv.id),
            "message_id": str(pending_msg.id)
        })

    return conv
