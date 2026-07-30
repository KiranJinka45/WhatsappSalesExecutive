import pytest
import uuid
import datetime
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from sqlalchemy import event
from app import models
from app.routers.webhooks import process_message_async

# Automatically populate created_at on Message initialization for mock testing
@event.listens_for(models.Message, 'init')
def set_message_created_at(target, args, kwargs):
    if not target.created_at:
        target.created_at = datetime.datetime.now(datetime.timezone.utc)

class MockQuery:
    def __init__(self, return_items):
        self.return_items = return_items
    def filter(self, *args, **kwargs):
        return self
    def order_by(self, *args, **kwargs):
        return self
    def limit(self, *args, **kwargs):
        return self
    def all(self):
        return self.return_items
    def first(self):
        return self.return_items[0] if self.return_items else None

@pytest.fixture
def mock_db():
    db = MagicMock(spec=Session)
    return db

@patch("app.routers.webhooks.SessionLocal")
@patch("app.routers.webhooks.tenant_var")
@patch("app.routers.webhooks.ai_service.transcribe_audio")
@patch("app.bsp_service.download_meta_media")
@patch("app.connection_manager.manager.broadcast")
@patch("app.bsp_service.send_whatsapp_message")
@patch("app.routers.webhooks.ai_service.detect_language")
@patch("app.routers.webhooks.ai_service.extract_entities")
@patch("app.routers.webhooks.ai_service.validate_retrieval")
@patch("app.routers.webhooks.ai_service.rank_recommendations")
@patch("app.routers.webhooks.ai_service.generate_reply")
@patch("app.routers.webhooks.ai_service.decision_engine")
def test_process_message_async_audio(
    mock_decision_engine, mock_generate_reply, mock_rank_recommendations,
    mock_validate_retrieval, mock_extract_entities, mock_detect_language,
    mock_send, mock_broadcast, mock_download, mock_transcribe, mock_tenant, mock_session, mock_db
):
    mock_session.return_value = mock_db
    
    org = models.Organization(id=uuid.uuid4(), name="Test Brand")
    conv = models.Conversation(id=uuid.uuid4(), customer_phone="1234567890", status="AI_ACTIVE")
    msg = models.Message(
        id=uuid.uuid4(),
        sender="customer",
        message_type="audio",
        content="🎙️ [Voice Message]"
    )
    matched_product = models.Product(
        id=uuid.uuid4(),
        sku="SKU-123",
        name="Matching Saree",
        price=1500.0,
        color="Blue",
        image_urls=["https://example.com/blue.jpg"],
        image_embedding_status="completed"
    )
    
    def mock_query(*args, **kwargs):
        model = args[0] if args else None
        if model == models.Conversation:
            return MockQuery([conv])
        elif model == models.Organization:
            return MockQuery([org])
        elif model == models.Message:
            return MockQuery([msg])
        elif model == models.Product:
            if len(args) > 1:
                return MockQuery([(matched_product, 0.2)])
            return MockQuery([matched_product])
        return MockQuery([])
        
    mock_db.query.side_effect = mock_query
    
    mock_transcribe.return_value = "price entha andi"
    mock_download.return_value = b"fake_audio_bytes"
    mock_detect_language.return_value = {"language": "te", "confidence": 0.9}
    mock_extract_entities.return_value = {"budget_max": 2000.0}
    mock_validate_retrieval.return_value = (True, [], None)
    mock_rank_recommendations.return_value = []
    mock_generate_reply.return_value = "Mocked visual search reply"
    mock_decision_engine.evaluate.return_value = MagicMock(is_approved=True, action="auto_send")
    mock_decision_engine.DECISION_ENGINE_VERSION = "v1.0"
    
    # Run task
    process_message_async(
        org_id=str(org.id),
        conv_id=str(conv.id),
        message_text="🎙️ [Voice Message]",
        msg_type="audio",
        media_id="audio_media_123",
        mime_type="audio/ogg"
    )
    
    # Assertions
    mock_transcribe.assert_called_once_with(b"fake_audio_bytes", "audio/ogg")
    assert msg.content == "price entha andi"
    mock_broadcast.assert_any_call(str(org.id), "message_updated", {
        "conversation_id": str(conv.id),
        "message_id": str(msg.id),
        "content": "price entha andi"
    })

@patch("app.routers.webhooks.SessionLocal")
@patch("app.routers.webhooks.tenant_var")
@patch("app.routers.webhooks.ai_service.get_image_embedding")
@patch("app.bsp_service.download_meta_media")
@patch("app.connection_manager.manager.broadcast")
@patch("app.bsp_service.send_whatsapp_message")
@patch("app.routers.webhooks.ai_service.detect_language")
@patch("app.routers.webhooks.ai_service.extract_entities")
@patch("app.routers.webhooks.ai_service.validate_retrieval")
@patch("app.routers.webhooks.ai_service.rank_recommendations")
@patch("app.routers.webhooks.ai_service.generate_reply")
@patch("app.routers.webhooks.ai_service.decision_engine")
def test_process_message_async_image_visual_search_match(
    mock_decision_engine, mock_generate_reply, mock_rank_recommendations,
    mock_validate_retrieval, mock_extract_entities, mock_detect_language,
    mock_send, mock_broadcast, mock_download, mock_get_embedding, mock_tenant, mock_session, mock_db
):
    mock_session.return_value = mock_db
    
    org = models.Organization(id=uuid.uuid4(), name="Test Brand")
    conv = models.Conversation(id=uuid.uuid4(), customer_phone="1234567890", status="AI_ACTIVE")
    msg = models.Message(
        id=uuid.uuid4(),
        sender="customer",
        message_type="image",
        content="🖼️ [Image]"
    )
    matched_product = models.Product(
        id=uuid.uuid4(),
        sku="SKU-123",
        name="Matching Saree",
        price=1500.0,
        color="Blue",
        image_urls=["https://example.com/blue.jpg"],
        image_embedding_status="completed"
    )
    
    def mock_query(*args, **kwargs):
        model = args[0] if args else None
        if model == models.Conversation:
            return MockQuery([conv])
        elif model == models.Organization:
            return MockQuery([org])
        elif model == models.Message:
            return MockQuery([msg])
        elif model == models.Product:
            if len(args) > 1:
                return MockQuery([(matched_product, 0.2)])
            return MockQuery([matched_product])
        return MockQuery([])
        
    mock_db.query.side_effect = mock_query
    mock_download.return_value = b"fake_image_bytes"
    mock_get_embedding.return_value = [0.1] * 3072
    mock_detect_language.return_value = {"language": "te", "confidence": 0.9}
    mock_extract_entities.return_value = {"budget_max": 2000.0}
    mock_validate_retrieval.return_value = (True, [], None)
    mock_rank_recommendations.return_value = []
    mock_generate_reply.return_value = "Mocked visual search reply"
    mock_decision_engine.evaluate.return_value = MagicMock(is_approved=True, action="auto_send")
    mock_decision_engine.DECISION_ENGINE_VERSION = "v1.0"
    
    # Run visual search
    process_message_async(
        org_id=str(org.id),
        conv_id=str(conv.id),
        message_text="🖼️ [Image]",
        msg_type="image",
        media_id="image_media_123",
        mime_type="image/jpeg"
    )
    
    mock_get_embedding.assert_called_with(b"fake_image_bytes")
    mock_send.assert_any_call("1234567890", "Matching Saree — ₹1500", org, media_url="https://example.com/blue.jpg")
