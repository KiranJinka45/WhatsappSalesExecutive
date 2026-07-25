from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, Header, Response
from sqlalchemy.orm import Session
import logging
import json
import hmac
import hashlib
from typing import Optional
from pydantic import BaseModel
from ..database import get_db, tenant_var, SessionLocal
from .. import models, ai_service, security
from ..config import settings
from ..queue import enqueue_message

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"], responses={400: {"description": "Bad Request"}})
logger = logging.getLogger(__name__)

def verify_meta_signature(payload: bytes, signature_header: str, app_secret: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected_sig = signature_header.split("sha256=")[1]
    computed_sig = hmac.new(
        app_secret.encode('utf-8'),
        payload,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_sig, computed_sig)

@router.get("/whatsapp")
def verify_whatsapp_handshake(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Standard Meta Webhook validation handshake.
    """
    logger.info(f"Webhook handshake received: mode={hub_mode}, verify_token={hub_verify_token}, challenge={hub_challenge}")
    if hub_mode == "subscribe" and hub_challenge:
        expected_token = settings.WHATSAPP_VERIFY_TOKEN or "closely_verify_token"
        if hub_verify_token == expected_token:
            logger.info("Webhook handshake verification successful.")
            return Response(content=str(hub_challenge), media_type="text/plain")
        else:
            logger.warning(f"Webhook verify token mismatch: received {hub_verify_token}, expected {expected_token}")
            raise HTTPException(status_code=403, detail="Verification token mismatch")
    return Response(content="verification_endpoint", media_type="text/plain")

def process_message_async(org_id: str, conv_id: str, message_text: str):
    """
    Background task to process AI response asynchronously, 
    preventing Meta webhook timeouts.
    """
    import time
    max_retries = 3
    retry_delay = 1.0
    last_exception = None

    db = SessionLocal()
    db.organization_id = org_id
    token = tenant_var.set(org_id)
    
    try:
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
        if not conv or conv.status != "AI_ACTIVE":
            db.close()
            tenant_var.reset(token)
            return
    except Exception as e:
        logger.error(f"Failed to load conversation: {e}", exc_info=True)
        last_exception = e

    if last_exception is None:
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    db.close()
                    db = SessionLocal()
                    db.organization_id = org_id
                    tenant_var.set(org_id)
                    conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
                    if not conv or conv.status != "AI_ACTIVE":
                        break

                # Fetch last 10 messages for conversational context
                msg_history = db.query(models.Message).filter(
                    models.Message.conversation_id == conv.id
                ).order_by(models.Message.created_at.asc()).limit(10).all()
                
                history_list = [{"sender": m.sender, "content": m.content} for m in msg_history]
                
                # Start latency timer
                pipeline_start_time = time.time()

                # Intent Classification
                intent = ai_service.classify_intent(message_text, history_list)
                logger.info(f"Classified intent for conversation {conv_id}: {intent}")

                # Language & Script Detection
                try:
                    lang_data = ai_service.detect_language(message_text, history_list)
                except Exception as lang_err:
                    logger.error(f"Language detection failed: {lang_err}")
                    lang_data = {"language": "en", "script": "latin", "confidence": 1.0}
                
                detected_lang = lang_data.get("language", "en")
                detected_script = lang_data.get("script", "latin")
                logger.info(f"Detected language for message: {detected_lang} ({detected_script})")

                # Update the customer's message record with the detected language
                try:
                    cust_msg = db.query(models.Message).filter(
                        models.Message.conversation_id == conv.id,
                        models.Message.sender == "customer"
                    ).order_by(models.Message.created_at.desc()).first()
                    if cust_msg:
                        cust_msg.detected_language = detected_lang
                        db.commit()
                except Exception as db_err:
                    logger.error(f"Failed to save detected language to customer message: {db_err}")
                
                # Initialize entities fallback
                entities = {}
                is_valid = True

                # Context retrieval initialization
                catalog_context = []
                org_token = tenant_var.set(None)
                db.organization_id = None
                try:
                    org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
                finally:
                    tenant_var.reset(org_token)
                    db.organization_id = org_id
                    
                if not org:
                    logger.error(f"Organization {org_id} not found in async task.")
                    break

                # Semantic Search Context Retrieval
                if intent in ["product_search", "inventory_query", "product_discovery", "similar_recommendation", "product_info", "availability"]:
                    # Entity Extraction
                    entities = ai_service.extract_entities(message_text, history_list)
                    logger.info(f"Extracted entities for conversation {conv_id}: {entities}")
                    
                    # Build search string (hybrid search logic: combine text with entities)
                    search_query = message_text
                    if entities.get("product_type"):
                        search_query += f" {entities['product_type']}"
                        
                    query_embedding = ai_service.get_embedding(search_query)
                    
                    # Check if embedding is zero vector (fallback to text matching if offline/missing API key)
                    is_zero_vector = all(v == 0.0 for v in query_embedding) if query_embedding else True
                    
                    if is_zero_vector:
                        # Offline fallback: keyword/text search on name, description, color, fabric
                        keywords = [w.strip() for w in search_query.lower().split() if len(w.strip()) > 2]
                        filters = []
                        for kw in keywords:
                            filters.append(models.Product.name.ilike(f"%{kw}%"))
                            filters.append(models.Product.description.ilike(f"%{kw}%"))
                            filters.append(models.Product.color.ilike(f"%{kw}%"))
                            filters.append(models.Product.fabric.ilike(f"%{kw}%"))
                        
                        if filters:
                            from sqlalchemy import or_
                            catalog_matches = db.query(models.Product).filter(or_(*filters)).limit(5).all()
                        else:
                            catalog_matches = db.query(models.Product).limit(5).all()
                            
                        # If still no keyword matches, fallback to returning the top 5 products
                        if not catalog_matches:
                            catalog_matches = db.query(models.Product).limit(5).all()
                    else:
                        catalog_matches = db.query(models.Product).order_by(
                            models.Product.embedding.cosine_distance(query_embedding)
                        ).limit(5).all()
                    
                    catalog_context = [{
                        "sku": p.sku,
                        "name": p.name,
                        "price": float(p.price),
                        "color": p.color,
                        "fabric": p.fabric,
                        "sizes": p.sizes,
                        "stock_count": p.stock_count,
                        "description": p.description,
                        "image_urls": p.image_urls,
                        "video_urls": p.video_urls
                    } for p in catalog_matches]
                    
                    # Retrieval Quality Layer Validation
                    is_valid, filtered_context, escalation_reason = ai_service.validate_retrieval(intent, entities, catalog_context)
                    
                    # Compute rejected items
                    raw_skus = {item["sku"] for item in catalog_context}
                    filtered_skus = {item["sku"] for item in filtered_context}
                    rejected_skus = list(raw_skus - filtered_skus)
                    
                    if not is_valid:
                        logger.warning(f"Retrieval Quality Layer rejected context: {escalation_reason}")
                    
                    # Recommendation Ranker
                    ranked_context = ai_service.rank_recommendations(filtered_context)
                    catalog_context = ranked_context
                    
                    # Explainability Metadata
                    explainability_meta = {
                        "intent": intent,
                        "entities_extracted": entities,
                        "language": detected_lang,
                        "script": detected_script,
                        "retrieved_products": [item["sku"] for item in catalog_context],
                        "rejected_products": rejected_skus,
                        "escalation_reason": escalation_reason if not is_valid else None
                    }
                else:
                    explainability_meta = {
                        "intent": intent,
                        "language": detected_lang,
                        "script": detected_script
                    }

                # Generate grounded reply
                policies_context = org.policies or {}
                ai_reply = ai_service.generate_reply(
                    message_text, 
                    history_list, 
                    catalog_context, 
                    policies_context,
                    detected_language=detected_lang,
                    detected_script=detected_script
                )

                # Run the deterministic Decision Engine to check safety policies & rules
                decision_result = ai_service.decision_engine.evaluate(
                    intent=intent,
                    policies=policies_context,
                    grounding_valid=is_valid,
                    proposed_reply=ai_reply,
                    entities=entities,
                    catalog_context=catalog_context,
                )
                action = decision_result.action
                reason = decision_result.reason
                risk_score = decision_result.risk_score
                ai_recommendation = decision_result.ai_recommendation
                rule_triggered = decision_result.rule_triggered
                
                # End latency timer and compile telemetry
                latency = time.time() - pipeline_start_time
                
                from ..ai.client import last_llm_meta
                llm_meta = last_llm_meta.get()
                provider = llm_meta.get("provider", "fallback")
                model = llm_meta.get("model", "mock")
                input_tokens = llm_meta.get("input_tokens", 0)
                output_tokens = llm_meta.get("output_tokens", 0)
                estimated_cost = llm_meta.get("estimated_cost", 0.0)
                
                observability_log = {
                    "event": "ai_reply_observability",
                    "conversation_id": str(conv.id),
                    "organization_id": str(org.id),
                    "provider": provider,
                    "model": model,
                    "prompt_version": "v1.0",
                    "policy_version": "v1.0",
                    "decision_engine_version": getattr(ai_service.decision_engine, "DECISION_ENGINE_VERSION", "v1.0"),
                    "grounding_score": 1.0 if is_valid else 0.0,
                    "retrieval_ids": [item["sku"] for item in catalog_context] if catalog_context else [],
                    "latency": latency,
                    "tokens": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens
                    },
                    "estimated_cost": estimated_cost,
                    "approval_request_id": None
                }
                explainability_meta["observability"] = observability_log

                # Log AI message (set status depending on action)
                ai_msg_status = "pending" if action == "wait_for_approval" else "sent"
                ai_msg = models.Message(
                    conversation_id=conv.id,
                    sender="ai",
                    message_type="text",
                    content=ai_reply,
                    status=ai_msg_status,
                    metadata_=explainability_meta
                )
                db.add(ai_msg)
                
                # Update conversation metadata with preferences/budget tracking
                meta = dict(conv.metadata_ or {})
                if "under" in message_text.lower():
                     words = message_text.lower().split()
                     for i, w in enumerate(words):
                          if w == "under" and i+1 < len(words):
                               try:
                                   clean_price = "".join([c for c in words[i+1] if c.isdigit()])
                                   if clean_price:
                                       meta["budget_limit"] = int(clean_price)
                               except ValueError:
                                   pass
                conv.metadata_ = meta
                
                if action == "wait_for_approval":
                    # Transition conversation status
                    conv.status = "WAITING_APPROVAL"
                    conv.escalation_reason = reason
                    db.commit()
                    db.refresh(ai_msg)
                    
                    # Create Approval Request record with complete audit metadata
                    approval = models.ApprovalRequest(
                        conversation_id=conv.id,
                        organization_id=org_id,
                        status="pending",
                        reason=reason,
                        proposed_response=ai_reply,
                        ai_recommendation=ai_recommendation,
                        risk_score=risk_score,
                        llm_model=model,
                        prompt_version="v1.0",
                        retrieval_ids=[item["sku"] for item in catalog_context] if catalog_context else [],
                        grounding_score=1.0 if is_valid else 0.0,
                        decision_engine_version=getattr(ai_service.decision_engine, "DECISION_ENGINE_VERSION", "v1.0"),
                        rule_triggered=rule_triggered,
                        metadata_={
                            "intent": intent,
                            "explainability_meta": explainability_meta
                        }
                    )
                    db.add(approval)
                    db.commit()
                    db.refresh(approval)

                    # Update approval_request_id in observability log and metadata
                    observability_log["approval_request_id"] = str(approval.id)
                    explainability_meta["observability"] = observability_log
                    ai_msg.metadata_ = explainability_meta
                    db.commit()
                    
                    logger.info(f"OBSERVABILITY METRICS: {json.dumps(observability_log)}")
                    
                    # Create a Persistent Notification
                    notification = models.Notification(
                        organization_id=org_id,
                        approval_request_id=approval.id,
                        type="ApprovalCreated",
                        status="unread"
                    )
                    db.add(notification)
                    db.commit()
                    
                    # Broadcast pending message and approval request to merchants
                    from ..connection_manager import manager
                    manager.broadcast(org_id, "new_message", {
                        "conversation_id": str(conv.id),
                        "message": {
                            "id": str(ai_msg.id),
                            "sender": ai_msg.sender,
                            "message_type": ai_msg.message_type,
                            "content": ai_msg.content,
                            "status": ai_msg.status,
                            "error_message": ai_msg.error_message,
                            "created_at": ai_msg.created_at.isoformat()
                        }
                    })
                    # Send human-escalation WhatsApp message to customer so they are not left in silence
                    from ..bsp_service import send_whatsapp_message
                    escalation_text = "I'm connecting you with a store manager. They will get back to you shortly."
                    try:
                        send_whatsapp_message(conv.customer_phone, escalation_text, org)
                    except Exception as whatsapp_err:
                        logger.error(f"Failed to send human-escalation WhatsApp message on approval hold: {whatsapp_err}")

                    db.close()
                    tenant_var.reset(token)
                    return
                
                # Proceed to direct send
                db.commit()
                db.refresh(ai_msg)
                
                logger.info(f"OBSERVABILITY METRICS: {json.dumps(observability_log)}")
                
                # Broadcast AI response to connected merchant streams
                from ..connection_manager import manager
                manager.broadcast(org_id, "new_message", {
                    "conversation_id": str(conv.id),
                    "message": {
                        "id": str(ai_msg.id),
                        "sender": ai_msg.sender,
                        "message_type": ai_msg.message_type,
                        "content": ai_msg.content,
                        "status": ai_msg.status,
                        "error_message": ai_msg.error_message,
                        "created_at": ai_msg.created_at.isoformat()
                    }
                })
                
                # Trigger real outbound BSP API payload dispatch with up to 3 retry attempts
                from ..bsp_service import send_whatsapp_message
                send_whatsapp_res = {"status": "failed", "error": "Not started"}
                for out_attempt in range(3):
                    send_whatsapp_res = send_whatsapp_message(conv.customer_phone, ai_reply, org)
                    if send_whatsapp_res.get("status") != "failed":
                        break
                    if out_attempt < 2:
                        time.sleep(0.5 * (2 ** out_attempt))
                
                if send_whatsapp_res.get("status") == "failed":
                    conv.status = "OWNER_ACTIVE"
                    ai_msg.status = "failed"
                    ai_msg.error_message = send_whatsapp_res.get("error")
                    db.commit()
                    manager.broadcast(org_id, "new_message", {
                        "conversation_id": str(conv.id),
                        "message": {
                            "id": str(ai_msg.id),
                            "sender": ai_msg.sender,
                            "message_type": ai_msg.message_type,
                            "content": ai_msg.content,
                            "status": "failed",
                            "error_message": ai_msg.error_message,
                            "created_at": ai_msg.created_at.isoformat()
                        }
                    })
                    logger.error(f"Outbound WhatsApp send failed permanently after retries: {send_whatsapp_res.get('error')}")
                else:
                    logger.info(f"Generated and sent reply: '{ai_reply}' for customer: {conv.customer_phone}")
                
                db.close()
                tenant_var.reset(token)
                return

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed in process_message_async: {e}")
                last_exception = e
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2.0

    # Persistent failure handling
    logger.error(f"Persistent failure in async message processing: {last_exception}", exc_info=True)
    try:
        try:
            db.close()
        except Exception:
            pass
        db = SessionLocal()
        db.organization_id = org_id
        tenant_var.set(org_id)
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_id).first()
        if conv:
            conv.status = "human_takeover"
            failed_msg = models.Message(
                conversation_id=conv.id,
                sender="ai",
                message_type="text",
                content="System Error: Failed to generate reply.",
                status="failed",
                error_message=str(last_exception)
            )
            db.add(failed_msg)
            db.commit()
            db.refresh(failed_msg)
            
            # Send human-escalation WhatsApp message to customer so they are not left in silence
            org_token = tenant_var.set(None)
            db.organization_id = None
            try:
                org = db.query(models.Organization).filter(models.Organization.id == org_id).first()
            finally:
                tenant_var.reset(org_token)
                db.organization_id = org_id
                
            if org:
                from ..bsp_service import send_whatsapp_message
                escalation_text = "I'm connecting you with a store manager. They will get back to you shortly."
                try:
                    send_whatsapp_message(conv.customer_phone, escalation_text, org)
                except Exception as whatsapp_err:
                    logger.error(f"Failed to send human-escalation WhatsApp message on persistent worker failure: {whatsapp_err}")
            
            from ..connection_manager import manager
            manager.broadcast(org_id, "new_message", {
                "conversation_id": str(conv.id),
                "message": {
                    "id": str(failed_msg.id),
                    "sender": failed_msg.sender,
                    "message_type": failed_msg.message_type,
                    "content": failed_msg.content,
                    "status": "failed",
                    "error_message": failed_msg.error_message,
                    "created_at": failed_msg.created_at.isoformat()
                }
            })
    except Exception as e:
        logger.error(f"Failed to save background task error to database: {e}", exc_info=True)
    finally:
        db.close()
        tenant_var.reset(token)


from ..rate_limiter import InMemoryRateLimiter

webhook_limiter = InMemoryRateLimiter(requests_limit=100, window_seconds=60, name="webhook")

@router.post("/whatsapp")
async def receive_whatsapp_message(
    request: Request, 
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db),
    limiter: None = Depends(webhook_limiter)
):
    """
    Receives incoming WhatsApp message payload from BSP.
    Decoupled processing via BackgroundTasks.
    """
    payload_bytes = await request.body()
    
    # Signature Verification
    if not settings.TESTING:
        if not settings.WHATSAPP_APP_SECRET:
            if settings.APP_ENV == "development":
                logger.warning("WHATSAPP_APP_SECRET is not set. Skipping signature check in development mode.")
            else:
                logger.error("WHATSAPP_APP_SECRET is not set. Rejecting webhook.")
                raise HTTPException(status_code=401, detail="Authentication credentials not provided")
        else:
            if not x_hub_signature_256 or not verify_meta_signature(payload_bytes, x_hub_signature_256, settings.WHATSAPP_APP_SECRET):
                if settings.APP_ENV == "development":
                    logger.warning("Invalid signature in development, proceeding anyway.")
                else:
                    logger.warning("Invalid or missing webhook signature rejected.")
                    raise HTTPException(status_code=403, detail="Invalid or missing signature")

    try:
        body = await request.json()
    except Exception:
        # If not JSON, try Form data (Twilio default format)
        form_data = await request.form()
        body = dict(form_data)

    logger.info(f"Incoming webhook payload: {body}")

    # Standardize incoming fields
    customer_phone = None
    brand_phone = None
    message_text = ""
    customer_name = "Customer"
    message_id = None
    import time
    
    # 1. Twilio Format parsing
    if "From" in body:
        from_raw = body.get("From", "")
        customer_phone = from_raw.replace("whatsapp:", "").strip()
        to_raw = body.get("To", "")
        brand_phone = to_raw.replace("whatsapp:", "").strip()
        message_text = body.get("Body", "").strip()
        customer_name = body.get("ProfileName", "Customer")
        message_id = body.get("MessageSid") or body.get("SmsMessageSid")
    # 2. WasenderAPI Format parsing (Instant QR-code WhatsApp Gateway)
    elif "event" in body or ("data" in body and isinstance(body.get("data"), dict)):
        try:
            event_name = body.get("event", "")
            data = body.get("data", {})
            
            # Ignore outgoing messages (fromMe = True)
            key = data.get("key", {}) if isinstance(data, dict) else {}
            if key.get("fromMe") is True:
                return {"status": "ignored", "reason": "Self-sent message ignored"}
                
            remote_jid = key.get("remoteJid", "") or (data.get("from", "") if isinstance(data, dict) else "")
            if "@" in remote_jid:
                customer_phone = remote_jid.split("@")[0]
            else:
                customer_phone = remote_jid
                
            customer_name = (data.get("pushName") if isinstance(data, dict) else None) or "Customer"
            message_id = key.get("id") or (data.get("id") if isinstance(data, dict) else None)
            
            # Extract text
            msg_obj = data.get("message", {}) if isinstance(data, dict) else {}
            if isinstance(msg_obj, dict):
                message_text = (
                    msg_obj.get("conversation") or 
                    msg_obj.get("extendedTextMessage", {}).get("text") or 
                    msg_obj.get("imageMessage", {}).get("caption") or 
                    ""
                ).strip()
            else:
                message_text = str(data.get("body") or data.get("text") or "").strip()

            brand_phone = (data.get("session") if isinstance(data, dict) else None) or body.get("session")
        except Exception as e:
            logger.error(f"Failed to parse WasenderAPI payload: {e}")
            return {"status": "ignored", "reason": "Unparseable WasenderAPI payload structure"}
    # 3. General / Gupshup / Meta Cloud API format parsing
    elif "entry" in body:
        try:
            entry = body["entry"][0]
            changes = entry["changes"][0]
            value = changes["value"]
            if "messages" in value:
                message = value["messages"][0]
                customer_phone = message["from"]
                message_text = message.get("text", {}).get("body", "").strip()
                contacts = value.get("contacts", [{}])[0]
                customer_name = contacts.get("profile", {}).get("name", "Customer")
                brand_phone = value.get("metadata", {}).get("display_phone_number")
                message_id = message.get("id")
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse Meta Cloud API payload: {e}")
            return {"status": "ignored", "reason": "Unparseable payload structure"}
    # 4. Direct Test sandbox payload format (allowed in development environment only for tests)
    elif settings.APP_ENV == "development":
        customer_phone = body.get("customer_phone")
        brand_phone = body.get("brand_phone")
        message_text = body.get("message", "")
        customer_name = body.get("customer_name", "Customer")
        msg_hash = hashlib.md5(message_text.encode("utf-8")).hexdigest()[:8] if message_text else "empty"
        message_id = body.get("message_id") or f"test_{customer_phone}_{msg_hash}_{int(time.time())}"

    if not customer_phone or not message_text:
        return {"status": "ignored", "reason": "No sender phone or message content parsed."}

    # Redis Deduplication
    if message_id:
        import redis
        try:
            r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
            dedup_key = f"webhook:dedup:{message_id}"
            is_new = r.set(dedup_key, "1", ex=300, nx=True)
            if not is_new:
                logger.info(f"Duplicate webhook message {message_id} ignored.")
                return {"status": "ignored", "reason": "Duplicate message ID"}
        except Exception as e:
            logger.warning(f"Redis deduplication failed (proceeding anyway): {e}")

    # Temporarily unset tenant filter to find the correct org globally
    token = tenant_var.set(None)
    db.organization_id = None
    try:
        org = None
        if brand_phone:
            org = db.query(models.Organization).filter(models.Organization.whatsapp_number == brand_phone).first()
        
        if not org:
            org = db.query(models.Organization).first()
            if not org:
                return {"status": "error", "reason": "No registered brands found in the system."}
    finally:
        tenant_var.reset(token)

    # Set tenant context for the remainder of the synchronous request
    tenant_var.set(org.id)
    db.organization_id = org.id

    # Resolve/Create conversation
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org.id,
        models.Conversation.customer_phone == customer_phone
    ).first()

    if not conv:
        conv = models.Conversation(
            organization_id=org.id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            status="AI_ACTIVE"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Log Customer message synchronously
    cust_msg = models.Message(
        conversation_id=conv.id,
        sender="customer",
        message_type="text",
        content=message_text
    )
    db.add(cust_msg)
    db.commit()
    db.refresh(cust_msg)
    
    # Broadcast customer message to connected merchant streams
    from ..connection_manager import manager
    manager.broadcast(str(org.id), "new_message", {
        "conversation_id": str(conv.id),
        "message": {
            "id": str(cust_msg.id),
            "sender": cust_msg.sender,
            "message_type": cust_msg.message_type,
            "content": cust_msg.content,
            "created_at": cust_msg.created_at.isoformat()
        }
    })

    # Reopen closed or owner-active conversations when customer messages again
    if conv.status in ["CLOSED", "OWNER_ACTIVE"]:
        conv.status = "AI_ACTIVE"
        db.commit()

    if conv.status == "WAITING_APPROVAL":
        return {"status": "forwarded_to_agent"}

    # Delegate LLM and database intensive work to FastAPI BackgroundTasks
    background_tasks.add_task(process_message_async, str(org.id), str(conv.id), message_text)

    # Return 200 OK immediately to Meta
    return {"status": "processing"}


class SimulatedPayload(BaseModel):
    customer_phone: str
    message: str
    customer_name: Optional[str] = "Customer"
    brand_phone: Optional[str] = None

@router.post("/whatsapp/simulated", responses={401: {"description": "Unauthorized"}})
def receive_simulated_whatsapp_message(
    payload: SimulatedPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(security.get_current_user)
):
    """
    Simulates incoming WhatsApp message payload for sandbox testing.
    This endpoint is auth-gated to prevent abuse.
    """
    org_id = current_user.organization_id
    customer_phone = payload.customer_phone
    message_text = payload.message
    customer_name = payload.customer_name or "Customer"
    
    # Set tenant context
    tenant_var.set(org_id)
    db.organization_id = org_id
    
    # Resolve/Create conversation
    conv = db.query(models.Conversation).filter(
        models.Conversation.organization_id == org_id,
        models.Conversation.customer_phone == customer_phone
    ).first()

    if not conv:
        conv = models.Conversation(
            organization_id=org_id,
            customer_phone=customer_phone,
            customer_name=customer_name,
            status="AI_ACTIVE"
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

    # Log Customer message synchronously
    cust_msg = models.Message(
        conversation_id=conv.id,
        sender="customer",
        message_type="text",
        content=message_text
    )
    db.add(cust_msg)
    db.commit()
    db.refresh(cust_msg)
    
    # Broadcast customer message to connected merchant streams
    from ..connection_manager import manager
    manager.broadcast(str(org_id), "new_message", {
        "conversation_id": str(conv.id),
        "message": {
            "id": str(cust_msg.id),
            "sender": cust_msg.sender,
            "message_type": cust_msg.message_type,
            "content": cust_msg.content,
            "created_at": cust_msg.created_at.isoformat()
        }
    })

    # Reopen closed conversations if customer messages again
    if conv.status == "CLOSED":
        conv.status = "AI_ACTIVE"
        db.commit()

    if conv.status in ["OWNER_ACTIVE", "WAITING_APPROVAL"]:
        return {"status": "forwarded_to_agent", "conversation_id": str(conv.id)}

    # Delegate LLM and database intensive work to Redis queue
    enqueue_message(org_id, conv.id, message_text)

    return {"status": "processing", "conversation_id": str(conv.id)}

class PaymentPayload(BaseModel):
    event: str  # e.g. "payment.captured"
    customer_phone: str
    amount: float
    currency: str = "INR"

@router.post("/payments", responses={404: {"description": "Conversation not found"}})
def receive_payment_webhook(payload: PaymentPayload, db: Session = Depends(get_db)):
    """
    Simulates payment gateway webhook ingestion.
    Updates conversation metadata funnel_stage to 'paid' and logs order_value.
    """
    # Temporarily bypass tenant filtering to find conversation globally by customer phone
    token = tenant_var.set(None)
    db.organization_id = None
    try:
        conv = db.query(models.Conversation).filter(
            models.Conversation.customer_phone == payload.customer_phone
        ).order_by(models.Conversation.updated_at.desc()).first()
        
        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found for this customer phone")
            
        org_id = str(conv.organization_id)
        
        # Apply changes
        meta = dict(conv.metadata_ or {})
        meta["funnel_stage"] = "paid"
        meta["order_value"] = payload.amount
        conv.metadata_ = meta
        db.commit()
        db.refresh(conv)
        
        # Broadcast funnel update to merchant dashboard SSE streams
        from ..connection_manager import manager
        manager.broadcast(org_id, "funnel_update", {
            "conversation_id": str(conv.id),
            "funnel_stage": "paid",
            "order_value": payload.amount
        })
        return {"status": "success", "conversation_id": str(conv.id)}
    finally:
        tenant_var.reset(token)
