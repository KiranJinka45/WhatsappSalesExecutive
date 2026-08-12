from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks, Header, Response
from datetime import datetime, timezone
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

@router.get("/whatsapp", response_class=Response)
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

def process_message_async(
    org_id: str,
    conv_id: str,
    message_text: str,
    msg_type: str = "text",
    media_id: Optional[str] = None,
    mime_type: Optional[str] = None
):
    """
    Background task to process AI response asynchronously, 
    preventing Meta webhook timeouts.
    """
    import time
    max_retries = 3
    retry_delay = 1.0
    last_exception = None

    import uuid
    org_uuid = uuid.UUID(str(org_id)) if not isinstance(org_id, uuid.UUID) else org_id
    conv_uuid = uuid.UUID(str(conv_id)) if not isinstance(conv_id, uuid.UUID) else conv_id

    db = SessionLocal()
    db.organization_id = org_uuid
    token = tenant_var.set(org_uuid)
    
    for attempt in range(max_retries):
        try:
            if attempt > 0:
                try:
                    db.close()
                except Exception:
                    pass
                db = SessionLocal()
                db.organization_id = org_uuid
                tenant_var.set(org_uuid)

            conv = db.query(models.Conversation).filter(models.Conversation.id == conv_uuid).first()
            if not conv:
                break
            
            # Ensure status remains AI_ACTIVE
            if conv.status != "AI_ACTIVE" and conv.status != "WAITING_APPROVAL":
                conv.status = "AI_ACTIVE"
                db.commit()

            # Retrieve organization details globally for settings/keys
            org_token = tenant_var.set(None)
            db.organization_id = None
            try:
                org = db.query(models.Organization).filter(models.Organization.id == org_uuid).first()
            finally:
                tenant_var.reset(org_token)
                db.organization_id = org_uuid

            if not org:
                logger.error(f"Organization {org_uuid} not found in async task.")
                break

            # 1. Voice Note Processing (runs synchronously before NLU pipelines)
            if msg_type == "audio" and media_id:
                try:
                    logger.info(f"Downloading audio media with ID: {media_id} for transcription...")
                    from ..bsp_service import download_meta_media
                    audio_bytes = download_meta_media(media_id, org)
                    
                    logger.info("Transcribing audio bytes...")
                    transcribed_text = ai_service.transcribe_audio(audio_bytes, mime_type or "audio/ogg")
                    logger.info(f"Transcription result: {transcribed_text}")
                    
                    # Update local variable message_text for downstream pipelines
                    message_text = transcribed_text
                    
                    # Update database message record
                    cust_msg = db.query(models.Message).filter(
                        models.Message.conversation_id == conv.id,
                        models.Message.sender == "customer"
                    ).order_by(models.Message.created_at.desc()).first()
                    if cust_msg:
                        cust_msg.content = transcribed_text
                        db.commit()
                        
                        # Broadcast message update to connected merchants
                        from ..connection_manager import manager
                        manager.broadcast(str(org_uuid), "message_updated", {
                            "conversation_id": str(conv.id),
                            "message_id": str(cust_msg.id),
                            "content": transcribed_text
                        })
                except Exception as audio_err:
                    logger.error(f"Voice message transcription failed: {audio_err}")
                    error_reply = "Namaste! We received your voice message but couldn't transcribe it clearly. Could you please type your message or try sending it again? 🙏"
                    
                    # Save error reply message
                    err_msg = models.Message(
                        conversation_id=conv.id,
                        sender="ai",
                        message_type="text",
                        content=error_reply,
                        status="sent"
                    )
                    db.add(err_msg)
                    db.commit()
                    db.refresh(err_msg)
                    
                    from ..connection_manager import manager
                    manager.broadcast(str(org_uuid), "new_message", {
                        "conversation_id": str(conv.id),
                        "message": {
                            "id": str(err_msg.id),
                            "sender": err_msg.sender,
                            "message_type": err_msg.message_type,
                            "content": err_msg.content,
                            "status": "sent",
                            "created_at": err_msg.created_at.isoformat()
                        }
                    })
                    from ..bsp_service import send_whatsapp_message
                    send_whatsapp_message(conv.customer_phone, error_reply, org)
                    db.close()
                    tenant_var.reset(token)
                    return

            # Fetch last 10 messages for conversational context
            msg_history = db.query(models.Message).filter(
                models.Message.conversation_id == conv.id
            ).order_by(models.Message.created_at.asc()).limit(10).all()
            
            history_list = [{"sender": m.sender, "content": m.content} for m in msg_history]
                
            # Start latency timer
            pipeline_start_time = time.time()

            # Intent Classification
            # If true visual search, override intent
            if msg_type == "image":
                intent = "product_visual_search"
            else:
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
                org = db.query(models.Organization).filter(models.Organization.id == org_uuid).first()
            finally:
                tenant_var.reset(org_token)
                db.organization_id = org_uuid
                
            if not org:
                logger.error(f"Organization {org_uuid} not found in async task.")
                break

            # Visual Catalog Search Retrieval & Direct Messaging
            if intent == "product_visual_search":
                from sqlalchemy import or_
                import time
                
                # Initialize variables
                entities = {}
                matches = []
                
                # Check if this is a True Multimodal Image Visual Search
                if msg_type == "image" and media_id:
                    logger.info(f"Processing true visual search for image media ID: {media_id}")
                    closest_dist = 1.0
                    no_exact_match = False
                    
                    try:
                        # 1. Download image bytes
                        from ..bsp_service import download_meta_media
                        img_bytes = download_meta_media(media_id, org)
                        
                        # 2. Generate image embedding
                        logger.info("Generating image embedding via gemini-embedding-2...")
                        img_emb = ai_service.get_image_embedding(img_bytes)
                        
                        if img_emb and any(v != 0.0 for v in img_emb):
                            # 3. Query pgvector for closest matches
                            distance_expr = models.Product.image_embedding.cosine_distance(img_emb)
                            results = db.query(models.Product, distance_expr.label("distance")).filter(
                                models.Product.organization_id == org_uuid,
                                models.Product.image_embedding_status == "completed"
                            ).order_by(distance_expr).limit(5).all()
                            
                            if results:
                                closest_product, closest_dist = results[0]
                                logger.info(f"Closest product match: SKU={closest_product.sku}, Name={closest_product.name}, Distance={closest_dist}")
                                
                                # 4. Honesty Guardrail check (threshold 0.45)
                                if closest_dist < 0.45:
                                    logger.info(f"Confident match found: SKU={closest_product.sku} (dist={closest_dist})")
                                    matches = [closest_product]
                                    
                                    # 5. Extract entities for secondary modifiers
                                    entities = ai_service.extract_entities(message_text, history_list)
                                    
                                    # Handle "other colors" / "this in color X"
                                    has_color_req = entities.get("color")
                                    has_other_req = any(w in message_text.lower() for w in ["other", "vere", "colors", "designs", "unnaya"])
                                    
                                    if has_color_req:
                                        # Fetch same category but matching color
                                        color_matches = db.query(models.Product).filter(
                                            models.Product.organization_id == org_uuid,
                                            models.Product.category_id == closest_product.category_id,
                                            models.Product.color.ilike(f"%{entities['color']}%"),
                                            models.Product.stock_count > 0,
                                            models.Product.sku != closest_product.sku
                                        ).limit(4).all()
                                        matches.extend(color_matches)
                                    elif has_other_req:
                                        # Fetch other products in same category/design group
                                        other_matches = db.query(models.Product).filter(
                                            models.Product.organization_id == org_uuid,
                                            models.Product.category_id == closest_product.category_id,
                                            models.Product.stock_count > 0,
                                            models.Product.sku != closest_product.sku
                                        ).limit(4).all()
                                        matches.extend(other_matches)
                                else:
                                    # Guardrail triggered: no exact match
                                    logger.info(f"No confident match found. Distance={closest_dist}. Sending honesty response.")
                                    no_exact_match = True
                                    
                                    # Send visual honesty message
                                    honesty_reply = "We don't have this exact saree design in our catalog right now, but here are some similar available designs you might like!"
                                    from ..bsp_service import send_whatsapp_message
                                    send_whatsapp_message(conv.customer_phone, honesty_reply, org)
                                    
                                    honesty_msg = models.Message(
                                        conversation_id=conv.id,
                                        sender="ai",
                                        message_type="text",
                                        content=honesty_reply,
                                        status="sent"
                                    )
                                    db.add(honesty_msg)
                                    db.commit()
                                    db.refresh(honesty_msg)
                                    
                                    from ..connection_manager import manager
                                    manager.broadcast(str(org_uuid), "new_message", {
                                        "conversation_id": str(conv.id),
                                        "message": {
                                            "id": str(honesty_msg.id),
                                            "sender": honesty_msg.sender,
                                            "message_type": honesty_msg.message_type,
                                            "content": honesty_msg.content,
                                            "status": "sent",
                                            "created_at": honesty_msg.created_at.isoformat()
                                        }
                                    })
                                    
                                    # Keep matches as the top 3 visually similar fallbacks
                                    matches = [r[0] for r in results[:3]]
                                    entities = {"no_exact_match": True}
                            else:
                                logger.info("No completed product image embeddings found in database.")
                                no_exact_match = True
                        else:
                            logger.error("Failed to generate image embedding.")
                            no_exact_match = True
                    except Exception as img_err:
                        logger.error(f"Failed true visual similarity search pipeline: {img_err}", exc_info=True)
                        no_exact_match = True
                        
                    if no_exact_match and not matches:
                        # Standard text-based fallback when database query failed
                        entities = ai_service.extract_entities(message_text, history_list)
                        category = entities.get("product_type") or entities.get("fabric") or "Saree"
                        matches = db.query(models.Product).filter(
                            models.Product.organization_id == org_uuid,
                            models.Product.stock_count > 0
                        ).limit(3).all()
                else:
                    # Text-based visual search query fallback (e.g. "pics pettu")
                    entities = ai_service.extract_entities(message_text, history_list)
                    logger.info(f"Extracted entities for visual search {conv_id}: {entities}")
                    
                    # Check for ambiguous budget
                    has_budget_word = any(w in message_text.lower() for w in ["budget", "under", "between", "cheap", "cost", "price", "range"])
                    if has_budget_word and entities.get("budget_max") is None and entities.get("budget_min") is None:
                        # Clear ambiguous response: ask a clarifying question
                        ai_reply = "What's your budget — under 2000, 2000-4000, or above?"
                        ai_msg = models.Message(
                            conversation_id=conv.id,
                            sender="ai",
                            message_type="text",
                            content=ai_reply,
                            status="sent",
                            metadata_={"intent": intent, "entities_extracted": entities}
                        )
                        db.add(ai_msg)
                        db.commit()
                        db.refresh(ai_msg)
                        
                        # Broadcast & Send
                        from ..connection_manager import manager
                        manager.broadcast(str(org_uuid), "new_message", {
                            "conversation_id": str(conv.id),
                            "message": {
                                "id": str(ai_msg.id),
                                "sender": ai_msg.sender,
                                "message_type": ai_msg.message_type,
                                "content": ai_msg.content,
                                "status": "sent",
                                "created_at": ai_msg.created_at.isoformat()
                            }
                        })
                        from ..bsp_service import send_whatsapp_message
                        send_whatsapp_message(conv.customer_phone, ai_reply, org)
                        db.close()
                        tenant_var.reset(token)
                        return

                    # Retrieve matching products
                    category = entities.get("product_type") or entities.get("fabric") or ""
                    query = db.query(models.Product).filter(
                        models.Product.organization_id == org_uuid,
                        models.Product.stock_count > 0
                    )
                    if category:
                        cat_pat = f"%{category}%"
                        query = query.filter(
                            or_(
                                models.Product.name.ilike(cat_pat),
                                models.Product.fabric.ilike(cat_pat),
                                models.Product.color.ilike(cat_pat)
                            )
                        )
                    if entities.get("budget_min") is not None:
                        query = query.filter(models.Product.price >= entities.get("budget_min"))
                    if entities.get("budget_max") is not None:
                        query = query.filter(models.Product.price <= entities.get("budget_max"))
                    if entities.get("color"):
                        query = query.filter(models.Product.color.ilike(f"%{entities['color']}%"))
                    if entities.get("fabric"):
                        query = query.filter(models.Product.fabric.ilike(f"%{entities['fabric']}%"))

                    matches = query.order_by(models.Product.price.asc()).all()

                # Response Threshold Routing
                if len(matches) == 0:
                    # 0 matches: offer closest available price range
                    all_products = db.query(models.Product).filter(
                        models.Product.organization_id == org_uuid,
                        models.Product.stock_count > 0
                    )
                    if category:
                        cat_pat = f"%{category}%"
                        all_products = all_products.filter(
                            or_(
                                models.Product.name.ilike(cat_pat),
                                models.Product.fabric.ilike(cat_pat),
                                models.Product.color.ilike(cat_pat)
                            )
                        )
                    min_price_prod = all_products.order_by(models.Product.price.asc()).first()
                    if min_price_prod:
                        ai_reply = f"We don't have {category or 'matching'} options in that budget range, but we have items starting from ₹{int(min_price_prod.price)}. Would you like to see those?"
                    else:
                        ai_reply = "We don't have any matching products in stock right now, but I can check with our team for you!"

                    ai_msg = models.Message(
                        conversation_id=conv.id,
                        sender="ai",
                        message_type="text",
                        content=ai_reply,
                        status="sent",
                        metadata_={"intent": intent, "entities_extracted": entities}
                    )
                    db.add(ai_msg)
                    db.commit()
                    db.refresh(ai_msg)
                    
                    from ..connection_manager import manager
                    manager.broadcast(str(org_uuid), "new_message", {
                        "conversation_id": str(conv.id),
                        "message": {
                            "id": str(ai_msg.id),
                            "sender": ai_msg.sender,
                            "message_type": ai_msg.message_type,
                            "content": ai_msg.content,
                            "status": "sent",
                            "created_at": ai_msg.created_at.isoformat()
                        }
                    })
                    from ..bsp_service import send_whatsapp_message
                    send_whatsapp_message(conv.customer_phone, ai_reply, org)
                    db.close()
                    tenant_var.reset(token)
                    return

                elif 1 <= len(matches) <= 6:
                    # 1-6 matches: Send each product as a separate WhatsApp image message
                    from ..bsp_service import send_whatsapp_message
                    from ..connection_manager import manager
                    for idx, p in enumerate(matches):
                        img_url = p.image_urls[0] if p.image_urls and len(p.image_urls) > 0 else "https://via.placeholder.com/300"
                        caption = f"{p.name} — ₹{int(p.price)}"
                        
                        send_whatsapp_message(conv.customer_phone, caption, org, media_url=img_url)
                        
                        db_msg = models.Message(
                            conversation_id=conv.id,
                            sender="ai",
                            message_type="image",
                            content=caption,
                            media_url=img_url,
                            status="sent",
                            metadata_={"sku": p.sku, "price": float(p.price), "intent": intent}
                        )
                        db.add(db_msg)
                        db.commit()
                        db.refresh(db_msg)

                        manager.broadcast(str(org_uuid), "new_message", {
                            "conversation_id": str(conv.id),
                            "message": {
                                "id": str(db_msg.id),
                                "sender": db_msg.sender,
                                "message_type": db_msg.message_type,
                                "content": db_msg.content,
                                "media_url": db_msg.media_url,
                                "status": "sent",
                                "created_at": db_msg.created_at.isoformat()
                            }
                        })
                        time.sleep(0.2)
                    
                    db.close()
                    tenant_var.reset(token)
                    return

                else:
                    # 7+ matches: Send top 4 direct image messages, then one final text message with hosted gallery page link
                    from ..bsp_service import send_whatsapp_message
                    from ..connection_manager import manager
                    for p in matches[:4]:
                        img_url = p.image_urls[0] if p.image_urls and len(p.image_urls) > 0 else "https://via.placeholder.com/300"
                        caption = f"{p.name} — ₹{int(p.price)}"
                        
                        send_whatsapp_message(conv.customer_phone, caption, org, media_url=img_url)
                        
                        db_msg = models.Message(
                            conversation_id=conv.id,
                            sender="ai",
                            message_type="image",
                            content=caption,
                            media_url=img_url,
                            status="sent",
                            metadata_={"sku": p.sku, "price": float(p.price), "intent": intent}
                        )
                        db.add(db_msg)
                        db.commit()
                        db.refresh(db_msg)
                        
                        manager.broadcast(str(org_uuid), "new_message", {
                            "conversation_id": str(conv.id),
                            "message": {
                                "id": str(db_msg.id),
                                "sender": db_msg.sender,
                                "message_type": db_msg.message_type,
                                "content": db_msg.content,
                                "media_url": db_msg.media_url,
                                "status": "sent",
                                "created_at": db_msg.created_at.isoformat()
                            }
                        })
                        time.sleep(0.2)

                    import re
                    slug = re.sub(r'[^a-z0-9]+', '-', org.name.lower()).strip('-')
                    max_p_val = entities.get("budget_max") or 100000
                    cat_val = category or "sarees"
                    gallery_url = f"https://app.closelyai.com/catalog/{slug}?category={cat_val}&max_price={max_p_val}"
                    link_reply = f"We have many more options available! You can browse the full collection here: {gallery_url}"
                    
                    send_whatsapp_message(conv.customer_phone, link_reply, org)
                    
                    link_msg = models.Message(
                        conversation_id=conv.id,
                        sender="ai",
                        message_type="text",
                        content=link_reply,
                        status="sent",
                        metadata_={"intent": intent, "gallery_url": gallery_url}
                    )
                    db.add(link_msg)
                    db.commit()
                    db.refresh(link_msg)
                    
                    manager.broadcast(str(org_uuid), "new_message", {
                        "conversation_id": str(conv.id),
                        "message": {
                            "id": str(link_msg.id),
                            "sender": link_msg.sender,
                            "message_type": link_msg.message_type,
                            "content": link_msg.content,
                            "status": "sent",
                            "created_at": link_msg.created_at.isoformat()
                        }
                    })
                    
                    db.close()
                    tenant_var.reset(token)
                    return

            # Semantic Search Context Retrieval
            if intent in ["product_search", "inventory_query", "product_discovery", "similar_recommendation", "product_info", "availability"]:
                # Entity Extraction
                entities = ai_service.extract_entities(message_text, history_list)
                logger.info(f"Extracted entities for conversation {conv_id}: {entities}")
                
                # Build search string (hybrid search logic: combine text with entities)
                search_components = []
                # Exclude short affirmative/negative words from cluttering semantic meaning
                msg_lower = message_text.lower().strip()
                if msg_lower not in ["yes", "yep", "yeah", "no", "nope", "ok", "okay", "sure", "please"]:
                    search_components.append(message_text)
                    
                # Incorporate all relevant extracted entities for rich semantic meaning
                for entity_key in ["product_type", "color", "fabric", "gender"]:
                    val = entities.get(entity_key)
                    if val and val.lower() != "unknown":
                        search_components.append(val)
                        
                search_query = " ".join(search_components).strip()
                if not search_query:
                    search_query = message_text  # Fallback
                    
                logger.info(f"Refined search query for {conv_id}: '{search_query}'")
                query_embedding = ai_service.get_embedding(search_query)
                
                # Check if embedding is zero vector (fallback to text matching if offline/missing API key)
                is_zero_vector = all(v == 0.0 for v in query_embedding) if query_embedding else True
                
                catalog_matches = []
                if not is_zero_vector:
                    try:
                        catalog_matches = db.query(models.Product).order_by(
                            models.Product.embedding.cosine_distance(query_embedding)
                        ).limit(5).all()
                    except Exception as vec_err:
                        logger.warning(f"Vector search failed in database: {vec_err}. Falling back to keyword search.")
                        catalog_matches = []

                if is_zero_vector or not catalog_matches:
                    # Offline / Exception fallback: keyword/text search on name, sku, description, color, fabric
                    keywords = [w.strip() for w in search_query.lower().split() if len(w.strip()) > 2]
                    filters = []
                    for kw in keywords:
                        filters.append(models.Product.name.ilike(f"%{kw}%"))
                        filters.append(models.Product.sku.ilike(f"%{kw}%"))
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
                detected_script=detected_script,
                customer_name=conv.customer_name or "Customer",
                brand_name=org.name
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
                "organization_id": str(org_uuid),
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
                    organization_id=org_uuid,
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
                    organization_id=org_uuid,
                    approval_request_id=approval.id,
                    type="ApprovalCreated",
                    status="unread"
                )
                db.add(notification)
                db.commit()
                
                # Broadcast pending message and approval request to merchants
                from ..connection_manager import manager
                manager.broadcast(str(org_uuid), "new_message", {
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
            manager.broadcast(str(org_uuid), "new_message", {
                "conversation_id": str(conv.id),
                "message": {
                    "id": str(ai_msg.id),
                    "sender": ai_msg.sender,
                    "message_type": ai_msg.message_type,
                    "content": ai_msg.content,
                    "status": ai_msg.status,
                    "error_message": ai_msg.error_message,
                    "created_at": (ai_msg.created_at or datetime.now(timezone.utc)).isoformat()
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
                logger.warning(f"Outbound Meta WhatsApp BSP delivery skipped/failed: {send_whatsapp_res.get('error')}. Reply preserved in AI_ACTIVE mode for dashboard.")
            else:
                logger.info(f"Generated and sent reply: '{ai_reply}' for customer: {conv.customer_phone}")
            
            # Always preserve AI_ACTIVE status and mark message as sent for live dashboard
            conv.status = "AI_ACTIVE"
            ai_msg.status = "sent"
            db.commit()
            
            manager.broadcast(str(org_uuid), "new_message", {
                "conversation_id": str(conv.id),
                "message": {
                    "id": str(ai_msg.id),
                    "sender": ai_msg.sender,
                    "message_type": ai_msg.message_type,
                    "content": ai_msg.content,
                    "status": "sent",
                    "created_at": ai_msg.created_at.isoformat()
                }
            })
            
            db.close()
            tenant_var.reset(token)
            return

        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed in process_message_async: {e}")
            last_exception = e
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2.0

    # Persistent failure handling: Generate grounded catalog/policy fallback reply and KEEP status AI_ACTIVE
    logger.error(f"Persistent failure in async message processing: {last_exception}", exc_info=True)
    try:
        try:
            db.close()
        except Exception:
            pass
        db = SessionLocal()
        db.organization_id = org_uuid
        tenant_var.set(org_uuid)
        conv = db.query(models.Conversation).filter(models.Conversation.id == conv_uuid).first()
        if conv:
            # Ensure conversation status remains AI_ACTIVE (do not lock to human_takeover unless merchant explicitly takes over)
            conv.status = "AI_ACTIVE"
            
            # Fetch organization policies and catalog items for grounded fallback
            org_token = tenant_var.set(None)
            db.organization_id = None
            try:
                org = db.query(models.Organization).filter(models.Organization.id == org_uuid).first()
                products = db.query(models.Product).filter(
                    models.Product.organization_id == org_uuid,
                    models.Product.stock_count > 0
                ).limit(10).all()
            finally:
                tenant_var.reset(org_token)
                db.organization_id = org_uuid

            catalog_ctx = [{
                'id': str(p.id),
                'sku': p.sku,
                'name': p.name,
                'price': float(p.price),
                'color': p.color,
                'fabric': p.fabric,
                'description': p.description,
                'stock_count': p.stock_count,
                'sizes': p.sizes,
                'image_urls': p.image_urls
            } for p in products] if products else []

            policies_ctx = (org.policies or {}) if org else {}

            from ..ai.orchestrator import _mock_reply_fallback
            fallback_text = _mock_reply_fallback(message_text, catalog_ctx, policies_ctx)

            fallback_msg = models.Message(
                conversation_id=conv.id,
                sender="ai",
                message_type="text",
                content=fallback_text,
                status="sent",
                error_message=None
            )
            db.add(fallback_msg)
            db.commit()
            db.refresh(fallback_msg)
            
            if org:
                from ..bsp_service import send_whatsapp_message
                try:
                    send_whatsapp_message(conv.customer_phone, fallback_text, org)
                except Exception as whatsapp_err:
                    logger.error(f"Failed to send fallback WhatsApp message: {whatsapp_err}")
            
            from ..connection_manager import manager
            manager.broadcast(str(org_uuid), "new_message", {
                "conversation_id": str(conv.id),
                "message": {
                    "id": str(fallback_msg.id),
                    "sender": fallback_msg.sender,
                    "message_type": fallback_msg.message_type,
                    "content": fallback_msg.content,
                    "status": "sent",
                    "created_at": (fallback_msg.created_at or datetime.now(timezone.utc)).isoformat()
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
    phone_number_id = None
    message_text = ""
    customer_name = "Customer"
    message_id = None
    msg_type = "text"
    media_id = None
    mime_type = None
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
                msg_type = message.get("type", "text")
                contacts = value.get("contacts", [{}])[0]
                customer_name = contacts.get("profile", {}).get("name", "Customer")
                brand_phone = value.get("metadata", {}).get("display_phone_number")
                phone_number_id = value.get("metadata", {}).get("phone_number_id")
                message_id = message.get("id")
                
                if msg_type == "text":
                    message_text = message.get("text", {}).get("body", "").strip()
                elif msg_type == "audio":
                    audio = message.get("audio", {})
                    media_id = audio.get("id")
                    mime_type = audio.get("mime_type") or "audio/ogg"
                    message_text = "🎙️ [Voice Message]"
                elif msg_type == "image":
                    image = message.get("image", {})
                    media_id = image.get("id")
                    mime_type = image.get("mime_type") or "image/jpeg"
                    message_text = image.get("caption", "").strip() or "🖼️ [Image]"
        except (KeyError, IndexError) as e:
            logger.error(f"Failed to parse Meta Cloud API payload: {e}")
            return {"status": "ignored", "reason": "Unparseable payload structure"}
    # 4. Direct Test sandbox payload format (allowed in development environment only for tests)
    elif settings.APP_ENV == "development":
        customer_phone = body.get("customer_phone")
        brand_phone = body.get("brand_phone")
        message_text = body.get("message", "")
        customer_name = body.get("customer_name", "Customer")
        msg_type = body.get("message_type", "text")
        media_id = body.get("media_id")
        mime_type = body.get("mime_type")
        if msg_type == "audio" and not message_text:
            message_text = "🎙️ [Voice Message]"
        elif msg_type == "image" and not message_text:
            message_text = "🖼️ [Image]"
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
        if phone_number_id:
            org = db.query(models.Organization).filter(models.Organization.whatsapp_phone_number_id == phone_number_id).first()
        if not org and brand_phone:
            org = db.query(models.Organization).filter(models.Organization.whatsapp_number == brand_phone).first()
            if not org:
                # Fallback to normalized comparison of last 10 digits to prevent formatting mismatches (+ prefix, spaces, dashes)
                clean_brand = "".join(c for c in brand_phone if c.isdigit())
                if clean_brand:
                    all_orgs = db.query(models.Organization).filter(models.Organization.whatsapp_number.isnot(None)).all()
                    for o in all_orgs:
                        clean_db = "".join(c for c in o.whatsapp_number if c.isdigit())
                        if clean_brand == clean_db or (len(clean_brand) >= 10 and len(clean_db) >= 10 and clean_brand[-10:] == clean_db[-10:]):
                            org = o
                            break
        
        if not org:
            logger.error(f"Rejecting webhook message. Brand not found for phone_number_id={phone_number_id} and brand_phone={brand_phone}.")
            return {"status": "error", "reason": "Tenant matching failed. Unknown brand."}
    finally:
        tenant_var.reset(token)

    # Set tenant context for the remainder of the synchronous request
    tenant_var.set(org.id)
    db.organization_id = org.id
    # Force the local variable update in PostgreSQL immediately to override dummy sentinel
    from sqlalchemy import text
    db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org.id)})

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
        message_type=msg_type,
        content=message_text,
        media_url=media_id
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

    # Always enforce AI_ACTIVE mode on incoming customer messages and broadcast status change
    conv.status = "AI_ACTIVE"
    db.commit()
    manager.broadcast(str(org.id), "status_change", {
        "conversation_id": str(conv.id),
        "status": "AI_ACTIVE"
    })

    # Delegate LLM and database intensive work to FastAPI BackgroundTasks
    background_tasks.add_task(
        process_message_async,
        str(org.id),
        str(conv.id),
        message_text,
        msg_type=msg_type,
        media_id=media_id,
        mime_type=mime_type
    )

    # Return 200 OK immediately to Meta
    return {"status": "processing"}


class SimulatedPayload(BaseModel):
    customer_phone: str
    message: str
    customer_name: Optional[str] = "Customer"
    brand_phone: Optional[str] = None
    message_type: Optional[str] = "text"
    media_id: Optional[str] = None
    mime_type: Optional[str] = None

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
    msg_type = payload.message_type or "text"
    media_id = payload.media_id
    mime_type = payload.mime_type
    
    if msg_type == "audio" and not message_text:
        message_text = "🎙️ [Voice Message]"
    elif msg_type == "image" and not message_text:
        message_text = "🖼️ [Image]"
        
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
    else:
        conv.status = "AI_ACTIVE"
        db.commit()

    # Log Customer message synchronously
    cust_msg = models.Message(
        conversation_id=conv.id,
        sender="customer",
        message_type=msg_type,
        content=message_text,
        media_url=media_id
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

    # Always enforce AI_ACTIVE mode on incoming customer messages and broadcast status change
    conv.status = "AI_ACTIVE"
    db.commit()
    manager.broadcast(str(org_id), "status_change", {
        "conversation_id": str(conv.id),
        "status": "AI_ACTIVE"
    })

    # Delegate LLM processing to background_tasks to guarantee execution without Redis dependency
    background_tasks.add_task(
        process_message_async,
        str(org_id),
        str(conv.id),
        message_text,
        msg_type=msg_type,
        media_id=media_id,
        mime_type=mime_type
    )

    return {"status": "processing", "conversation_id": str(conv.id)}

class PaymentPayload(BaseModel):
    event: str  # e.g. "payment.captured"
    customer_phone: str
    amount: float
    currency: str = "INR"

def send_payment_confirmation_async(org_id: str, customer_phone: str, amount: float):
    import uuid
    org_uuid = uuid.UUID(org_id) if isinstance(org_id, str) else org_id
    db = SessionLocal()
    db.is_admin = True
    db.organization_id = org_uuid
    token = tenant_var.set(org_uuid)
    try:
        # Fetch organization globally
        tenant_var.set(None)
        db.organization_id = None
        org = db.query(models.Organization).filter(models.Organization.id == org_uuid).first()
        tenant_var.set(org_uuid)
        db.organization_id = org_uuid
        
        if not org:
            logger.error(f"Organization {org_uuid} not found for payment confirmation task.")
            return

        # Fetch conversation
        conv = db.query(models.Conversation).filter(
            models.Conversation.customer_phone == customer_phone
        ).order_by(models.Conversation.updated_at.desc()).first()
        
        if not conv:
            logger.error(f"Conversation not found for customer phone {customer_phone} in payment confirmation task.")
            return

        content = f"Namaste! We have received your payment of Rs. {amount:.2f}. Your order has been successfully placed. Thank you for shopping with us! 🙏"
        
        # Save message
        ai_msg = models.Message(
            conversation_id=conv.id,
            sender="ai",
            message_type="text",
            content=content,
            status="sent"
        )
        db.add(ai_msg)
        db.commit()
        db.refresh(ai_msg)
        
        # Broadcast message update to connected merchants
        from ..connection_manager import manager
        manager.broadcast(str(org_uuid), "new_message", {
            "conversation_id": str(conv.id),
            "message": {
                "id": str(ai_msg.id),
                "sender": ai_msg.sender,
                "message_type": ai_msg.message_type,
                "content": ai_msg.content,
                "status": "sent",
                "created_at": ai_msg.created_at.isoformat()
            }
        })
        
        # Send via BSP
        from ..bsp_service import send_whatsapp_message
        send_whatsapp_message(customer_phone, content, org)
    except Exception as e:
        logger.error(f"Failed to send payment confirmation asynchronously: {e}", exc_info=True)
    finally:
        db.close()
        tenant_var.reset(token)

@router.post("/payments", responses={404: {"description": "Conversation not found"}})
def receive_payment_webhook(
    payload: PaymentPayload,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Simulates payment gateway webhook ingestion.
    Updates conversation metadata funnel_stage to 'paid', logs order_value,
    and asynchronously dispatches a payment confirmation message via WhatsApp.
    """
    # Temporarily bypass tenant filtering to find conversation globally by customer phone
    token = tenant_var.set(None)
    db.organization_id = None
    db.is_admin = True
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
        
        # Enforce AI_ACTIVE status and trigger payment confirmation asynchronously
        conv.status = "AI_ACTIVE"
        db.commit()
        manager.broadcast(org_id, "status_change", {
            "conversation_id": str(conv.id),
            "status": "AI_ACTIVE"
        })
        
        background_tasks.add_task(
            send_payment_confirmation_async,
            org_id,
            payload.customer_phone,
            payload.amount
        )
        
        return {"status": "success", "conversation_id": str(conv.id)}
    finally:
        db.is_admin = False
        tenant_var.reset(token)
