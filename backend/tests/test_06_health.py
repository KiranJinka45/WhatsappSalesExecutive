import pytest
from fastapi.testclient import TestClient

from tests.conftest import app

client = TestClient(app)

def test_health_liveness():
    response = client.get("/api/health/liveness")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ok", "alive"]

def test_health_readiness():
    response = client.get("/api/health/readiness")
    # Returns 200 when all services up, or 503 if redis/db down
    assert response.status_code in [200, 503]
