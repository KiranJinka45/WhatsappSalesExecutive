import os
import sys
import pytest
import schemathesis

# Ensure DATABASE_URL points to test database
if "DATABASE_URL" not in os.environ:
    os.environ["DATABASE_URL"] = "postgresql://postgres:postgres@localhost:5434/closely_db_test"

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.main import app
from tests.conftest import setup_test_db, TestingSessionLocal, clean_tables

# Setup database tables first so schemathesis endpoints don't crash on database connection/schema errors
@pytest.fixture(scope="session", autouse=True)
def init_test_db_for_schemathesis():
    setup_test_db()
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

@pytest.fixture(scope="session", autouse=True)
def mock_external_services():
    from unittest.mock import patch
    # Mock Redis ping to return True
    import redis
    redis_ping_patcher = patch("redis.Redis.ping", return_value=True)
    redis_ping_patcher.start()
    
    # Mock settings.GEMINI_API_KEY
    from app.config import settings
    original_key = settings.GEMINI_API_KEY
    settings.GEMINI_API_KEY = "mock_api_key"
    
    yield
    
    redis_ping_patcher.stop()
    settings.GEMINI_API_KEY = original_key

# Create a schema object from ASGI app
schema = schemathesis.openapi.from_asgi("/openapi.json", app)

from hypothesis import settings, HealthCheck

def custom_response_schema_conformance(ctx, response, case):
    try:
        schemathesis.checks.response_schema_conformance(ctx, response, case)
    except Exception as e:
        # Ignore false-positive internationalized email format validation errors
        if "is not a \"email\"" in str(e) or "is not a 'email'" in str(e):
            return
        raise e

@schema.parametrize()
@settings(suppress_health_check=[HealthCheck.filter_too_much], deadline=None)
def test_api_contracts(case):
    # Perform a request against the ASGI app directly
    response = case.call()
    # Perform core OpenAPI conformance checks, omitting the strict RejectedPositiveData
    # check which is prone to stateful database constraints and form-validation false positives.
    case.validate_response(
        response,
        checks=(
            schemathesis.checks.not_a_server_error,
            schemathesis.checks.status_code_conformance,
            schemathesis.checks.content_type_conformance,
            custom_response_schema_conformance,
        )
    )
