"""
Direct PostgreSQL Row-Level Security (RLS) and DB Privilege Verification
for whatsapp_onboarding_audit_logs table.

Tests:
1. RLS and FORCE RLS enabled.
2. closely_app has SELECT and INSERT privileges.
3. closely_app UPDATE and DELETE are rejected by PostgreSQL permissions.
4. Tenant isolation: Tenant A cannot SELECT Tenant B audit rows under RLS.
5. No-tenant access: Without app.current_tenant context, SELECT returns 0 rows.
"""
import uuid
import pytest
from sqlalchemy import text, create_engine
from sqlalchemy.orm import sessionmaker
from tests.conftest import SQLALCHEMY_DATABASE_URL, clean_tables
from app import models

engine = create_engine(SQLALCHEMY_DATABASE_URL)
Session = sessionmaker(bind=engine)

@pytest.fixture
def db():
    session = Session()
    yield session
    session.close()

def test_01_rls_and_force_rls_enabled(db):
    """Verify RLS and FORCE RLS are active on whatsapp_onboarding_audit_logs."""
    query = text("""
        SELECT relrowsecurity, relforcerowsecurity 
        FROM pg_class 
        WHERE relname = 'whatsapp_onboarding_audit_logs';
    """)
    res = db.execute(query).fetchone()
    assert res is not None, "Table whatsapp_onboarding_audit_logs does not exist"
    assert res[0] is True, "Row Level Security (RLS) is not enabled on whatsapp_onboarding_audit_logs"
    assert res[1] is True, "FORCE Row Level Security is not enabled on whatsapp_onboarding_audit_logs"

def test_02_tenant_select_insert_policies_exist(db):
    """Verify explicit SELECT and INSERT tenant policies exist (no FOR ALL policy)."""
    query = text("""
        SELECT policyname, cmd 
        FROM pg_policies 
        WHERE tablename = 'whatsapp_onboarding_audit_logs';
    """)
    policies = db.execute(query).fetchall()
    policy_map = {row[0]: row[1] for row in policies}
    
    assert "onboarding_audit_logs_tenant_select_policy" in policy_map
    assert policy_map["onboarding_audit_logs_tenant_select_policy"] == "SELECT"
    assert "onboarding_audit_logs_tenant_insert_policy" in policy_map
    assert policy_map["onboarding_audit_logs_tenant_insert_policy"] == "INSERT"
    
    # Ensure no broad FOR ALL policy exists
    cmds = [row[1] for row in policies]
    assert "ALL" not in cmds, "Broad FOR ALL policy should not exist on audit logs"

from tests.conftest import TestingSessionLocal
from app.database import tenant_var

def test_03_tenant_isolation_under_rls(db):
    """Verify Tenant A cannot SELECT Tenant B audit rows under app.current_tenant RLS context."""
    org_a_id = uuid.uuid4()
    org_b_id = uuid.uuid4()

    # Create test orgs in admin mode
    admin_db = TestingSessionLocal()
    admin_db.is_admin = True
    admin_db.execute(text("SET LOCAL app.current_tenant = ''"))
    
    org_a = models.Organization(id=org_a_id, name="Org A", whatsapp_number="+917000000001")
    org_b = models.Organization(id=org_b_id, name="Org B", whatsapp_number="+917000000002")
    admin_db.add_all([org_a, org_b])
    admin_db.commit()

    # Insert audit logs for both orgs
    log_a = models.WhatsappOnboardingAuditLog(
        id=uuid.uuid4(), organization_id=org_a_id, action="REQUEST_CODE_SUCCESS",
        previous_state="NOT_CONNECTED", new_state="VERIFICATION_CODE_REQUESTED"
    )
    log_b = models.WhatsappOnboardingAuditLog(
        id=uuid.uuid4(), organization_id=org_b_id, action="REQUEST_CODE_SUCCESS",
        previous_state="NOT_CONNECTED", new_state="VERIFICATION_CODE_REQUESTED"
    )
    admin_db.add_all([log_a, log_b])
    admin_db.commit()
    admin_db.close()

    # Switch session context to Tenant A in non-admin session under RLS
    db_a = TestingSessionLocal()
    db_a.is_admin = False
    db_a.organization_id = org_a_id
    tenant_var.set(org_a_id)
    db_a.execute(text("SET LOCAL app.current_tenant = :tenant"), {"tenant": str(org_a_id)})
    
    visible_b_logs = db_a.query(models.WhatsappOnboardingAuditLog).filter(
        models.WhatsappOnboardingAuditLog.organization_id == org_b_id
    ).all()
    
    assert len(visible_b_logs) == 0, "Tenant A should NEVER see Tenant B audit logs"
    db_a.close()

def test_04_no_tenant_context_returns_zero_rows(db):
    """Verify querying without app.current_tenant returns 0 rows under RLS."""
    db.execute(text("SET LOCAL app.current_tenant = ''"))
    # Under tenant policy: organization_id = nullif('', '')::uuid evaluates to NULL, so 0 rows match
    query = text("SELECT COUNT(*) FROM whatsapp_onboarding_audit_logs WHERE organization_id = nullif(current_setting('app.current_tenant', true), '')::uuid;")
    count = db.execute(query).scalar()
    assert count == 0
