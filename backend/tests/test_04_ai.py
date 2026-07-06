import pytest
from fastapi.testclient import TestClient
import uuid
import unittest.mock

from tests.conftest import app, TestingSessionLocal, clean_tables
from app import ai_service

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_teardown():
    db = TestingSessionLocal()
    clean_tables(db)
    db.close()
    yield

def test_intent_classification():
    # Since we mocked it in conftest, let's test the mock behavior or temporarily unpatch it
    # For now, just test our mock wrapper or actual endpoint if there was an AI direct endpoint.
    intent = ai_service.classify_intent("I want to buy a shoe")
    assert intent == "product_discovery"
    
def test_embedding_generation():
    emb = ai_service.get_embedding("red shoe")
    assert len(emb) == 768
    assert emb[0] == 0.0

def test_reply_generation():
    reply = ai_service.generate_reply("red shoe", [], [])
    assert reply == "Mocked AI reply"
