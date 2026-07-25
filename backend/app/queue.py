import json
import logging
import time
import redis
from .config import settings

logger = logging.getLogger(__name__)

REDIS_QUEUE_KEY = "closely:queue:messages"
REDIS_PROCESSING_KEY = "closely:queue:messages:processing"
REDIS_DLQ_KEY = "closely:queue:messages:dlq"

def get_redis_client() -> redis.Redis:
    """
    Returns a Redis client initialized with settings.REDIS_URL.
    """
    return redis.from_url(settings.REDIS_URL, decode_responses=True)

def enqueue_message(org_id: str, conv_id: str, message_text: str):
    """
    Enqueues message processing metadata into the primary Redis queue.
    """
    if settings.TESTING:
        from .routers.webhooks import process_message_async
        process_message_async(org_id, conv_id, message_text)
        return

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
