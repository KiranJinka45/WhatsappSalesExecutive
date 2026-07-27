import pytest
import json
import time
import uuid
import unittest.mock
from app.config import settings
from app.queue import enqueue_message, get_redis_client, REDIS_QUEUE_KEY, REDIS_PROCESSING_KEY, REDIS_DLQ_KEY
from app.worker import Worker, MAX_RETRIES

TEST_QUEUE_KEY = "closely:test_queue:messages"
TEST_PROCESSING_KEY = "closely:test_queue:messages:processing"
TEST_DLQ_KEY = "closely:test_queue:messages:dlq"

@pytest.fixture(autouse=True)
def patch_queue_keys(monkeypatch):
    monkeypatch.setattr("app.queue.REDIS_QUEUE_KEY", TEST_QUEUE_KEY)
    monkeypatch.setattr("app.queue.REDIS_PROCESSING_KEY", TEST_PROCESSING_KEY)
    monkeypatch.setattr("app.queue.REDIS_DLQ_KEY", TEST_DLQ_KEY)
    monkeypatch.setattr("app.worker.REDIS_QUEUE_KEY", TEST_QUEUE_KEY)
    monkeypatch.setattr("app.worker.REDIS_PROCESSING_KEY", TEST_PROCESSING_KEY)
    monkeypatch.setattr("app.worker.REDIS_DLQ_KEY", TEST_DLQ_KEY)

@pytest.fixture
def redis_client():
    r = get_redis_client()
    # Clean keys beforehand
    r.delete(TEST_QUEUE_KEY, TEST_PROCESSING_KEY, TEST_DLQ_KEY)
    yield r
    # Clean keys afterward
    r.delete(TEST_QUEUE_KEY, TEST_PROCESSING_KEY, TEST_DLQ_KEY)

def test_queue_enqueue_and_worker_flow(redis_client):
    original_testing = settings.TESTING
    settings.TESTING = False
    try:
        org_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())
        message_text = "Success integration message"

        enqueue_message(org_id, conv_id, message_text)
        
        worker = Worker()
        
        # When process_message_async is called, we set worker.running = False so the loop terminates
        def mock_process(oid, cid, msg):
            worker.running = False
            
        with unittest.mock.patch("app.worker.process_message_async", side_effect=mock_process) as mock_p:
            worker.run()
            
            mock_p.assert_called_once_with(org_id, conv_id, message_text)
            
        # Verify it was removed from processing queue and main queue
        assert redis_client.llen(TEST_QUEUE_KEY) == 0
        assert redis_client.llen(TEST_PROCESSING_KEY) == 0
    finally:
        settings.TESTING = original_testing

def test_worker_run_failure_and_dlq_integration(redis_client):
    original_testing = settings.TESTING
    settings.TESTING = False
    try:
        org_id = str(uuid.uuid4())
        conv_id = str(uuid.uuid4())
        message_text = "Failure integration message"

        enqueue_message(org_id, conv_id, message_text)
        
        worker = Worker()
        
        call_count = 0
        def mock_process(oid, cid, msg):
            nonlocal call_count
            call_count += 1
            if call_count > MAX_RETRIES:  # termination condition after exhausting retries
                worker.running = False
            raise Exception("Simulated processing failure")

        with unittest.mock.patch("app.worker.process_message_async", side_effect=mock_process) as mock_p, \
             unittest.mock.patch("time.sleep") as mock_sleep:
             
            worker.run()
            
            assert call_count == 4
            assert redis_client.llen(TEST_QUEUE_KEY) == 0
            assert redis_client.llen(TEST_PROCESSING_KEY) == 0
            assert redis_client.llen(TEST_DLQ_KEY) == 1
            
            dlq_task = redis_client.lindex(TEST_DLQ_KEY, 0)
            payload = json.loads(dlq_task)
            assert payload["retry_count"] == 3
            assert payload["message_text"] == message_text
    finally:
        settings.TESTING = original_testing

def test_worker_orphaned_task_recovery(redis_client):
    original_testing = settings.TESTING
    settings.TESTING = False
    with unittest.mock.patch("redis.Redis.brpoplpush", return_value=None):
        try:
            org_id = str(uuid.uuid4())
            conv_id = str(uuid.uuid4())
            message_text = "Orphaned task recovery message"

            payload = {
                "org_id": org_id,
                "conv_id": conv_id,
                "message_text": message_text,
                "retry_count": 0,
                "timestamp": time.time()
            }
            
            # Manually push to processing queue to simulate orphaned task from a crash
            redis_client.lpush(TEST_PROCESSING_KEY, json.dumps(payload))
            
            assert redis_client.llen(TEST_PROCESSING_KEY) == 1
            assert redis_client.llen(TEST_QUEUE_KEY) == 0
            
            worker = Worker()
            worker.recover_orphaned_tasks()
            
            # Processing queue should now be empty and queue should have the task
            assert redis_client.llen(TEST_PROCESSING_KEY) == 0
            assert redis_client.llen(TEST_QUEUE_KEY) == 1
            
            recovered_str = redis_client.lindex(TEST_QUEUE_KEY, 0)
            recovered_payload = json.loads(recovered_str)
            assert recovered_payload["message_text"] == message_text
        finally:
            settings.TESTING = original_testing
