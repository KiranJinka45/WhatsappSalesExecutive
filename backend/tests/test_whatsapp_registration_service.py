import pytest
import uuid
import datetime
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from sqlalchemy.orm import Session
from tests.conftest import app, TestingSessionLocal, clean_tables
from app import models
from app.services import whatsapp_registration_service as reg_service

@pytest.fixture
def db():
    session = TestingSessionLocal()
    clean_tables(session)
    yield session
    session.close()

@pytest.fixture
def mock_org(db: Session):
    """Creates a mock organization tenant for onboarding tests."""
    org = models.Organization(
        id=uuid.uuid4(),
        name="Test Boutique Tenant",
        whatsapp_number="+917989888858",
        whatsapp_business_account_id="waba_test_12345",
        whatsapp_phone_number_id="phone_test_67890",
        whatsapp_access_token="mock_meta_access_token_sec_val",
        whatsapp_onboarding_state="NOT_CONNECTED",
        whatsapp_onboarding_metadata={},
        is_whatsapp_connected=0
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org

@pytest.fixture
def mock_owner(db: Session, mock_org: models.Organization):
    """Creates a mock owner user."""
    user = models.User(
        id=uuid.uuid4(),
        organization_id=mock_org.id,
        email="owner@testboutique.com",
        password_hash="hashed_pw",
        role="owner",
        name="Owner User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@pytest.fixture
def mock_staff(db: Session, mock_org: models.Organization):
    """Creates a mock staff user."""
    user = models.User(
        id=uuid.uuid4(),
        organization_id=mock_org.id,
        email="staff@testboutique.com",
        password_hash="hashed_pw",
        role="staff",
        name="Staff User"
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

# UT-01: request_code SMS Success
@patch("httpx.post")
def test_request_code_sms_success(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.content = b'{"success": true}'
    mock_post.return_value = mock_resp

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "code_requested"
    assert res["onboarding_state"] == "VERIFICATION_CODE_REQUESTED"
    assert res["method"] == "SMS"
    assert mock_org.whatsapp_onboarding_state == "VERIFICATION_CODE_REQUESTED"

# UT-02: request_code VOICE Success
@patch("httpx.post")
def test_request_code_voice_success(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.content = b'{"success": true}'
    mock_post.return_value = mock_resp

    res = reg_service.request_verification_code(db, mock_org, "VOICE", mock_owner.id)

    assert res["status"] == "code_requested"
    assert res["method"] == "VOICE"

# UT-03: verify_code Success
@patch("httpx.post")
def test_verify_code_success(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.content = b'{"success": true}'
    mock_post.return_value = mock_resp

    secret_code = "654321"
    res = reg_service.verify_registration_code(db, mock_org, secret_code, mock_owner.id)

    assert res["status"] == "verified"
    assert res["onboarding_state"] == "VERIFICATION_CODE_VERIFIED"
    assert mock_org.whatsapp_onboarding_state == "VERIFICATION_CODE_VERIFIED"

# UT-04: Invalid Verification Code
@patch("httpx.post")
def test_verify_code_invalid(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"code": 132001, "message": "Invalid verification code"}}
    mock_resp.content = b'{"error": {"code": 132001, "message": "Invalid verification code"}}'
    mock_post.return_value = mock_resp

    res = reg_service.verify_registration_code(db, mock_org, "111111", mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_INVALID_CODE
    assert "invalid or expired" in res["message"].lower()

# UT-05 & UT-11: Cooldown Enforcement & Rate Limiting
def test_cooldown_enforcement(db: Session, mock_org: models.Organization, mock_owner: models.User):
    future_cooldown = datetime.now(timezone.utc) + timedelta(minutes=5)
    mock_org.whatsapp_onboarding_metadata = {"cooldown_until": future_cooldown.isoformat()}
    db.commit()

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "rate_limited"
    assert res["error_category"] == reg_service.ERROR_CAT_TOO_MANY_REQUESTS

# UT-06: Number Active in WhatsApp Business App
@patch("httpx.post")
def test_number_active_in_app(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"code": 131030, "message": "Phone number is active in WhatsApp Business app"}}
    mock_resp.content = b'{"error": {"code": 131030, "message": "Phone number is active in WhatsApp Business app"}}'
    mock_post.return_value = mock_resp

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_ACTIVE_IN_APP
    assert mock_org.whatsapp_onboarding_state == "BLOCKED_NUMBER_ACTIVE_IN_APP"

# UT-07: Migration Required Error
@patch("httpx.post")
def test_migration_required_error(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"code": 131050, "message": "Account migration required"}}
    mock_resp.content = b'{"error": {"code": 131050, "message": "Account migration required"}}'
    mock_post.return_value = mock_resp

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_MIGRATION_REQUIRED
    assert mock_org.whatsapp_onboarding_state == "BLOCKED_MIGRATION_REQUIRED"

# UT-08: Manual Meta Action Required
@patch("httpx.post")
def test_manual_meta_action_required(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"code": 100, "message": "Invalid parameter / permissions review required"}}
    mock_resp.content = b'{"error": {"code": 100, "message": "Invalid parameter / permissions review required"}}'
    mock_post.return_value = mock_resp

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_MANUAL_ACTION
    assert mock_org.whatsapp_onboarding_state == "MANUAL_META_ACTION_REQUIRED"

# UT-09: Meta Configuration Incomplete
def test_meta_config_incomplete(db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_org.whatsapp_access_token = None
    db.commit()

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_CONFIG_INCOMPLETE

# UT-10: Unexpected Provider Error
@patch("httpx.post")
def test_unexpected_provider_error(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_post.side_effect = Exception("Meta API Timeout")

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_UNKNOWN

# UT-12: Lockout on Repeated Verification Failures
@patch("httpx.post")
def test_verification_attempt_lockout(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"code": 132001, "message": "Invalid code"}}
    mock_resp.content = b'{"error": {"code": 132001, "message": "Invalid code"}}'
    mock_post.return_value = mock_resp

    # Perform 5 failed attempts
    for _ in range(5):
        reg_service.verify_registration_code(db, mock_org, "999999", mock_owner.id)

    res = reg_service.verify_registration_code(db, mock_org, "999999", mock_owner.id)

    assert res["status"] == "locked"
    assert res["error_category"] == reg_service.ERROR_CAT_TOO_MANY_REQUESTS

# UT-13: Activate Live Number Success & Server-Side PIN Registration
@patch("httpx.get")
@patch("httpx.post")
def test_activate_live_number_success(mock_post, mock_get, db: Session, mock_org: models.Organization, mock_owner: models.User):
    # Mock POST register response
    mock_reg_resp = MagicMock()
    mock_reg_resp.status_code = 200
    mock_reg_resp.json.return_value = {"success": True}
    mock_reg_resp.content = b'{"success": true}'
    mock_post.return_value = mock_reg_resp

    # Mock GET status response with exact Meta resource fields
    mock_stat_resp = MagicMock()
    mock_stat_resp.status_code = 200
    mock_stat_resp.json.return_value = {
        "id": mock_org.whatsapp_phone_number_id,
        "verified_name": "Test Boutique",
        "code_verification_status": "VERIFIED",
        "quality_rating": "GREEN"
    }
    mock_stat_resp.content = b'{"id": "phone_test_67890", "verified_name": "Test Boutique"}'
    mock_get.return_value = mock_stat_resp

    res = reg_service.activate_live_number(db, mock_org, mock_owner.id)

    assert res["status"] == "activated"
    assert res["onboarding_state"] == "CONNECTED"
    assert mock_org.is_whatsapp_connected == 1

    # Assert server-generated 6-digit numeric PIN was sent to Meta register endpoint
    assert mock_post.called
    payload_sent = mock_post.call_args[1].get("json")
    generated_pin = payload_sent["pin"]
    assert len(generated_pin) == 6
    assert generated_pin.isdigit()

    # Verify zero leak in Audit logs
    audit_logs = db.query(models.WhatsappOnboardingAuditLog).filter(models.WhatsappOnboardingAuditLog.organization_id == mock_org.id).all()
    for log in audit_logs:
        assert generated_pin not in str(log.metadata_)

# UT-13B: Activation Resource ID Mismatch Rejection
@patch("httpx.get")
@patch("httpx.post")
def test_activate_live_number_resource_mismatch(mock_post, mock_get, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_reg_resp = MagicMock()
    mock_reg_resp.status_code = 200
    mock_post.return_value = mock_reg_resp

    mock_stat_resp = MagicMock()
    mock_stat_resp.status_code = 200
    mock_stat_resp.json.return_value = {"id": "different_phone_id_9999"}
    mock_stat_resp.content = b'{"id": "different_phone_id_9999"}'
    mock_get.return_value = mock_stat_resp

    res = reg_service.activate_live_number(db, mock_org, mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_MANUAL_ACTION
    assert mock_org.is_whatsapp_connected == 0

# UT-13C: Blocked Sandbox Test Number Activation Rejection
def test_activate_live_number_test_number_blocked(db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_org.whatsapp_number = "+1 555-659-5978"
    mock_org.whatsapp_phone_number_id = "1292475657271575"
    db.commit()

    res = reg_service.activate_live_number(db, mock_org, mock_owner.id)

    assert res["status"] == "error"
    assert "test/developer numbers cannot be activated" in res["message"]
    assert mock_org.is_whatsapp_connected == 0

# UT-14: Coexistence Flow Availability
@patch("httpx.post")
def test_coexistence_flow_detection(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    mock_resp.json.return_value = {"error": {"code": 131030, "message": "Phone number is active. Please use coexistence flow."}}
    mock_resp.content = b'{"error": {"code": 131030, "message": "Phone number is active. Please use coexistence flow."}}'
    mock_post.return_value = mock_resp

    res = reg_service.request_verification_code(db, mock_org, "SMS", mock_owner.id)

    assert res["status"] == "error"
    assert res["error_category"] == reg_service.ERROR_CAT_COEXISTENCE_AVAILABLE
    assert mock_org.whatsapp_onboarding_state == "COEXISTENCE_FLOW_AVAILABLE"

# ST-01: Zero Code Leakage Assertion
@patch("httpx.post")
def test_security_zero_code_leakage(mock_post, db: Session, mock_org: models.Organization, mock_owner: models.User):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"success": True}
    mock_resp.content = b'{"success": true}'
    mock_post.return_value = mock_resp

    secret_code = "887766"
    res = reg_service.verify_registration_code(db, mock_org, secret_code, mock_owner.id)

    # 1. Assert code is not in returned result
    assert secret_code not in str(res)

    # 2. Assert code is not in Organization model or metadata
    assert secret_code not in str(mock_org.whatsapp_onboarding_metadata)

    # 3. Assert code is not in Audit Logs
    audit_logs = db.query(models.WhatsappOnboardingAuditLog).filter(models.WhatsappOnboardingAuditLog.organization_id == mock_org.id).all()
    for log in audit_logs:
        assert secret_code not in str(log.metadata_)
        assert secret_code not in str(log.action)

# ST-04: No Token Exposure in Status API
def test_security_no_token_exposure(db: Session, mock_org: models.Organization):
    status = reg_service.get_connection_status(db, mock_org)

    status_str = str(status)
    assert mock_org.whatsapp_access_token not in status_str
    assert "mock_meta_access_token_sec_val" not in status_str
    assert "whatsapp_access_token" not in status

# ST-05: Test Number Safeguard Detection
def test_security_test_number_detection(db: Session, mock_org: models.Organization):
    mock_org.whatsapp_number = "+1 555-659-5978"
    mock_org.whatsapp_phone_number_id = "1292475657271575"
    db.commit()

    status = reg_service.get_connection_status(db, mock_org)

    assert status["is_test_number"] is True
    assert "Test Number" in status["safe_next_step"]
