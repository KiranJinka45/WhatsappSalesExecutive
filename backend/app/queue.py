import json
import logging
import time
import redis
from .config import settings

logger = logging.getLogger(__name__)

REDIS_QUEUE_KEY = "closely:queue:messages"
REDIS_PROCESSING_KEY = "closely:queue:messages:processing"
REDIS_DLQ_KEY = "closely:queue:messages:dlq"

REDIS_OUTBOX_QUEUE_KEY = "closely:queue:outbox"
REDIS_OUTBOX_PROCESSING_KEY = "closely:queue:outbox:processing"
REDIS_OUTBOX_DLQ_KEY = "closely:queue:outbox:dlq"

def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client initialized with settings.REDIS_URL.
    """
    return redis.from_url(settings.REDIS_URL, decode_responses=True)

def enqueue_message(org_id: str, conv_id: str, message_text: str):
    """
    Enqueues message processing metadata into the primary Redis queue.
    Falls back to direct background thread execution if Redis is unavailable.
    """
    if settings.TESTING:
        from .routers.webhooks import process_message_async
        process_message_async(org_id, conv_id, message_text)
        return

    try:
        r = get_redis_client()
        payload = {
            "org_id": str(org_id),
            "conv_id": str(conv_id),
            "message_text": message_text,
            "retry_count": 0,
            "timestamp": time.time()
        }
        r.lpush(REDIS_QUEUE_KEY, json.dumps(payload))
        logger.info(f"Enqueued background task to Redis queue '{REDIS_QUEUE_KEY}': {payload}")
    except Exception as e:
        logger.warning(f"Redis queue dispatch failed ({e}). Falling back to direct background thread processing.")
        from .routers.webhooks import process_message_async
        import threading
        t = threading.Thread(target=process_message_async, args=(org_id, conv_id, message_text), daemon=True)
        t.start()

def enqueue_outbox_dispatch(outbox_id: str):
    """
    Enqueues an outbox message ID into the asynchronous Redis outbox queue.
    Decouples external Meta Cloud API HTTP calls from the synchronous approval web handler.
    In TESTING mode, skips immediate dispatch so test suites can control mocking and dispatch execution explicitly.
    """
    if settings.TESTING:
        logger.info(f"TESTING mode active: Outbox ID '{outbox_id}' enqueued.")
        return

    try:
        r = get_redis_client()
        payload = {
            "outbox_id": str(outbox_id),
            "retry_count": 0,
            "timestamp": time.time()
        }
        r.lpush(REDIS_OUTBOX_QUEUE_KEY, json.dumps(payload))
        logger.info(f"Enqueued outbox dispatch to Redis queue '{REDIS_OUTBOX_QUEUE_KEY}': {payload}")
    except Exception as e:
        logger.warning(f"Redis outbox queue dispatch failed ({e}). Falling back to direct background thread processing.")
        from .outbox_dispatcher import dispatch_outbound_message
        from .database import SessionLocal
        import threading
        from uuid import UUID

        def _async_worker():
            db = SessionLocal()
            try:
                dispatch_outbound_message(db, UUID(str(outbox_id)))
            except Exception as thread_err:
                logger.error(f"Background thread outbox dispatch failed: {thread_err}")
            finally:
                db.close()

        t = threading.Thread(target=_async_worker, daemon=True)
        t.start()

