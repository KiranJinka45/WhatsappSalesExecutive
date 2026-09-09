import time
import json
import logging
import signal
import sys
from uuid import UUID
from .queue import (
    get_redis_client,
    REDIS_QUEUE_KEY,
    REDIS_PROCESSING_KEY,
    REDIS_DLQ_KEY,
    REDIS_OUTBOX_QUEUE_KEY,
    REDIS_OUTBOX_PROCESSING_KEY,
    REDIS_OUTBOX_DLQ_KEY
)
from .routers.webhooks import process_message_async
from .outbox_dispatcher import dispatch_outbound_message
from .database import SessionLocal
from .metrics import (
    WORKER_TASKS_PROCESSED_TOTAL,
    WORKER_TASK_DURATION_SECONDS,
    REDIS_QUEUE_DEPTH,
    start_metrics_server
)

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("closely_worker")

MAX_RETRIES = 3
BACKOFF_BASE = 2.0

class Worker:
    def __init__(self):
        self.running = True
        self.redis = get_redis_client()
        self._last_queue_metric_poll = 0.0
        # Handle graceful shutdown signals if running in main thread
        try:
            signal.signal(signal.SIGINT, self.stop)
            signal.signal(signal.SIGTERM, self.stop)
        except (ValueError, AttributeError):
            pass

    def stop(self, signum, frame):
        logger.info("Received shutdown signal. Stopping worker...")
        self.running = False

    def update_queue_depth_metrics(self):
        """Poll Redis list lengths and update Prometheus gauges every 2 seconds."""
        now = time.time()
        if now - self._last_queue_metric_poll < 2.0:
            return
        self._last_queue_metric_poll = now
        try:
            inbound_len = self.redis.llen(REDIS_QUEUE_KEY) or 0
            outbox_len = self.redis.llen(REDIS_OUTBOX_QUEUE_KEY) or 0
            REDIS_QUEUE_DEPTH.labels(queue_name="closely:queue:inbound").set(inbound_len)
            REDIS_QUEUE_DEPTH.labels(queue_name="closely:queue:outbox").set(outbox_len)
        except Exception as e:
            logger.debug(f"Failed to update queue depth metrics: {e}")

    def recover_orphaned_tasks(self):
        """
        Move any orphaned tasks in the processing queues back to their main queues on startup.
        Provides reliability in case the worker process crashed previously.
        """
        logger.info("Checking for orphaned tasks in processing queues...")
        
        # 1. Recover inbound message queue
        rec_inbound = 0
        while True:
            task = self.redis.rpoplpush(REDIS_PROCESSING_KEY, REDIS_QUEUE_KEY)
            if task:
                rec_inbound += 1
            else:
                break
                
        # 2. Recover outbox dispatch queue
        rec_outbox = 0
        while True:
            task = self.redis.rpoplpush(REDIS_OUTBOX_PROCESSING_KEY, REDIS_OUTBOX_QUEUE_KEY)
            if task:
                rec_outbox += 1
            else:
                break
                
        logger.info(f"Completed recovery. Recovered {rec_inbound} inbound tasks and {rec_outbox} outbox tasks.")

    def run(self):
        logger.info("Starting Closely AI Unified Worker process (Inbound + Outbox Dispatches)...")
        self.recover_orphaned_tasks()

        while self.running:
            did_work = False
            self.update_queue_depth_metrics()
            try:
                # 1. Check Outbound Outbox Dispatch Queue first (high priority for customer responsiveness)
                outbox_task = self.redis.brpoplpush(REDIS_OUTBOX_QUEUE_KEY, REDIS_OUTBOX_PROCESSING_KEY, timeout=1)
                if outbox_task:
                    did_work = True
                    logger.info(f"Popped outbox dispatch task: {outbox_task}")
                    start_time = time.time()
                    try:
                        payload = json.loads(outbox_task)
                        outbox_id = payload["outbox_id"]
                        
                        db = SessionLocal()
                        try:
                            res = dispatch_outbound_message(db, UUID(str(outbox_id)), redis_client=self.redis)
                            logger.info(f"Dispatched outbox task {outbox_id}: {res}")
                        finally:
                            db.close()
                            
                        self.redis.lrem(REDIS_OUTBOX_PROCESSING_KEY, 1, outbox_task)
                        duration = time.time() - start_time
                        WORKER_TASK_DURATION_SECONDS.labels(task_type="outbox_dispatch").observe(duration)
                        WORKER_TASKS_PROCESSED_TOTAL.labels(task_type="outbox_dispatch", status="success").inc()
                    except Exception as outbox_err:
                        duration = time.time() - start_time
                        WORKER_TASK_DURATION_SECONDS.labels(task_type="outbox_dispatch").observe(duration)
                        WORKER_TASKS_PROCESSED_TOTAL.labels(task_type="outbox_dispatch", status="error").inc()
                        logger.error(f"Error processing outbox task {outbox_task}: {outbox_err}", exc_info=True)
                        self.redis.lpush(REDIS_OUTBOX_DLQ_KEY, outbox_task)
                        self.redis.lrem(REDIS_OUTBOX_PROCESSING_KEY, 1, outbox_task)

                # 2. Check Inbound Message Queue
                task = self.redis.brpoplpush(REDIS_QUEUE_KEY, REDIS_PROCESSING_KEY, timeout=1)
                if task:
                    did_work = True
                    logger.info(f"Popped inbound message task: {task}")
                    payload = json.loads(task)
                    
                    org_id = payload["org_id"]
                    conv_id = payload["conv_id"]
                    message_text = payload["message_text"]
                    retry_count = payload.get("retry_count", 0)

                    start_time = time.time()
                    try:
                        # Execute message processing synchronously
                        process_message_async(org_id, conv_id, message_text)
                        logger.info(f"Successfully processed inbound message task: {task}")
                        self.redis.lrem(REDIS_PROCESSING_KEY, 1, task)
                        duration = time.time() - start_time
                        WORKER_TASK_DURATION_SECONDS.labels(task_type="inbound_message").observe(duration)
                        WORKER_TASKS_PROCESSED_TOTAL.labels(task_type="inbound_message", status="success").inc()
                    except Exception as ex:
                        duration = time.time() - start_time
                        WORKER_TASK_DURATION_SECONDS.labels(task_type="inbound_message").observe(duration)
                        WORKER_TASKS_PROCESSED_TOTAL.labels(task_type="inbound_message", status="error").inc()
                        logger.error(f"Error processing inbound message task: {task}. Details: {ex}", exc_info=True)
                        
                        if retry_count < MAX_RETRIES:
                            payload["retry_count"] = retry_count + 1
                            delay = BACKOFF_BASE ** retry_count
                            logger.info(f"Retrying inbound task in {delay}s (Attempt {payload['retry_count']}/{MAX_RETRIES})...")
                            time.sleep(delay)
                            self.redis.lpush(REDIS_QUEUE_KEY, json.dumps(payload))
                            self.redis.lrem(REDIS_PROCESSING_KEY, 1, task)
                        else:
                            logger.error(f"Inbound task exceeded max retries. Moving to DLQ: {task}")
                            self.redis.lpush(REDIS_DLQ_KEY, json.dumps(payload))
                            self.redis.lrem(REDIS_PROCESSING_KEY, 1, task)

                if not did_work:
                    time.sleep(0.5)

            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Worker stopped successfully.")

if __name__ == "__main__":
    # In standalone worker process, expose worker metrics on dedicated port 9091
    start_metrics_server(port=9091)
    worker = Worker()
    worker.run()

