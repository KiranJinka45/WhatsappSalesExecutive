import pytest
import uuid
import unittest.mock
from unittest.mock import patch, MagicMock

from app.config import validate_config, Settings
from app.routers.webhooks import process_message_async
from app.database import SessionLocal
from app import models

class LLMFailure(Exception):
    pass

@pytest.fixture
def mock_db_and_conv():
    org_id = str(uuid.uuid4())
    conv_id = str(uuid.uuid4())
    customer_phone = "+1234567890"
    
    db = SessionLocal()
    org = models.Organization(id=org_id, name="Test Org", whatsapp_number="+0987654321")
    db.add(org)
    
    conv = models.Conversation(id=conv_id, organization_id=org_id, customer_phone=customer_phone, status="AI_ACTIVE")
    db.add(conv)
    db.commit()
    db.close()
    
    yield org_id, conv_id, customer_phone
    
    db = SessionLocal()
    conv = db.query(models.Conversation).filter_by(id=conv_id).first()
    if conv:
        db.delete(conv)
    org = db.query(models.Organization).filter_by(id=org_id).first()
    if org:
        db.delete(org)
    db.commit()
    db.close()

def test_startup_validation_rejects_deprecated_models():
    # Test that decommissioned model throws ValueError
    mock_settings = Settings(
        TESTING=False,
        JWT_SECRET="x" * 32,
        GEMINI_API_KEY="dummy",
        GROQ_API_KEY="dummy",
        GROQ_MODEL="llama3-8b-8192"
    )
    with pytest.raises(ValueError, match="CRITICAL CONFIGURATION ERROR: GROQ_MODEL is set to decommissioned model"):
        validate_config(mock_settings)

def test_startup_validation_rejects_missing_keys():
    # Test that having no valid keys throws ValueError
    mock_settings = Settings(
        TESTING=False,
        JWT_SECRET="x" * 32,
        GEMINI_API_KEY="",
        GROQ_API_KEY="placeholder",
        OPENAI_API_KEY="",
        OPENROUTER_API_KEY="",
        NVIDIA_API_KEY=""
    )
    with pytest.raises(ValueError, match="CRITICAL CONFIGURATION ERROR: No valid LLM provider API key is configured"):
        validate_config(mock_settings)

def test_escalation_guardrail_approval_path(mock_db_and_conv):
    # If the decision engine results in 'wait_for_approval', ensure WhatsApp escalation triggers.
    org_id, conv_id, customer_phone = mock_db_and_conv
    
    with patch("app.connection_manager.ConnectionManager.broadcast") as mock_broadcast, \
         patch("app.ai_service.generate_reply", return_value="Here is a mock response.") as mock_generate, \
         patch("app.ai_service.classify_intent", return_value="inventory_query") as mock_classify, \
         patch("app.ai_service.extract_entities", return_value={}) as mock_extract, \
         patch("app.ai_service.get_embedding", return_value=[0.0] * 768) as mock_embed, \
         patch("app.ai_service.validate_retrieval", return_value=(True, [], None)) as mock_validate, \
         patch("app.ai_service.rank_recommendations", return_value=[]) as mock_rank, \
         patch("app.bsp_service.send_whatsapp_message") as mock_send_whatsapp:

        # Execute
        process_message_async(org_id, conv_id, "I want to buy a dress.")
        
        # Assert
        mock_send_whatsapp.assert_called_once()
        args, kwargs = mock_send_whatsapp.call_args
        assert args[0] == customer_phone
        assert "connecting you with a store manager" in args[1]
        from sqlalchemy import inspect
        assert str(inspect(args[2]).identity[0]) == org_id
        
        # Check conversation status
        db = SessionLocal()
        conv = db.query(models.Conversation).filter_by(id=conv_id).first()
        assert conv.status == "WAITING_APPROVAL"
        db.close()

def test_escalation_guardrail_persistent_failure(mock_db_and_conv):
    # Simulate a persistent worker failure
    org_id, conv_id, customer_phone = mock_db_and_conv
    
    with patch("app.connection_manager.ConnectionManager.broadcast") as mock_broadcast, \
         patch("app.ai_service.classify_intent", side_effect=LLMFailure("Simulated persistent failure in worker")) as mock_classify, \
         patch("time.sleep") as mock_sleep, \
         patch("app.bsp_service.send_whatsapp_message") as mock_send_whatsapp:

        # Execute
        process_message_async(org_id, conv_id, "Help me")
        
        # Assert
        mock_send_whatsapp.assert_called_once()
        args, kwargs = mock_send_whatsapp.call_args
        assert args[0] == customer_phone
        assert "Welcome to Pushpalatha Silks!" in args[1] or "sarees" in args[1]
        from sqlalchemy import inspect
        assert str(inspect(args[2]).identity[0]) == org_id
        
        # Check conversation status is "AI_ACTIVE"
        db = SessionLocal()
        conv = db.query(models.Conversation).filter_by(id=conv_id).first()
        assert conv.status == "AI_ACTIVE"
        db.close()
