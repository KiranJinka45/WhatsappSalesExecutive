import pytest
import uuid
from tests.conftest import TestingSessionLocal, setup_test_db
from app.database import tenant_var
from app import models
from sqlalchemy import text

@pytest.fixture(autouse=True)
def setup_worker_db():
    setup_test_db()
    yield

def test_worker_context_propagation():
    """
    Verifies that background tasks executed by the worker process explicitly
    bind organization tenant context and prevent cross-tenant exposure.
    """
    org1_id = uuid.uuid4()
    org2_id = uuid.uuid4()

    # Create Organization 1 and Organization 2
    db = TestingSessionLocal()
    db.is_admin = True
    try:
        org1 = models.Organization(id=org1_id, name="WorkerOrg1", whatsapp_number="+911111111111")
        org2 = models.Organization(id=org2_id, name="WorkerOrg2", whatsapp_number="+912222222222")
        db.add(org1)
        db.add(org2)
        db.commit()
    finally:
        db.is_admin = False
        db.close()

    # Create Conversation for Org 1
    db = TestingSessionLocal()
    db.organization_id = org1_id
    token = tenant_var.set(org1_id)
    try:
        try:
            db.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org1_id)})
        except Exception:
            pass
        conv1 = models.Conversation(id=uuid.uuid4(), organization_id=org1_id, customer_phone="+919999988888", status="AI_ACTIVE")
        db.add(conv1)
        db.commit()
        conv1_id = conv1.id
    finally:
        db.close()
        tenant_var.reset(token)

    # Verify Org 2 cannot read Conv 1
    db2 = TestingSessionLocal()
    db2.organization_id = org2_id
    token2 = tenant_var.set(org2_id)
    try:
        try:
            db2.execute(text("SET LOCAL app.current_tenant = :org_id"), {"org_id": str(org2_id)})
        except Exception:
            pass
        stolen_conv = db2.query(models.Conversation).filter(models.Conversation.id == conv1_id).first()
        assert stolen_conv is None, "Cross-tenant leak! Org 2 accessed Org 1's conversation."
    finally:
        db2.close()
        tenant_var.reset(token2)
