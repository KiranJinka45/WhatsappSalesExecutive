import time
import json
import logging
import signal
import sys
from .queue import get_redis_client, REDIS_QUEUE_KEY, REDIS_PROCESSING_KEY, REDIS_DLQ_KEY
from .routers.webhooks import process_message_async

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("closely_worker")

MAX_RETRIES = 3
BACKOFF_BASE = 2.0

class Worker:
    def __init__(self):
        self.running = True
        self.redis = get_redis_client()
        # Handle graceful shutdown signals if running in main thread
        try:
            signal.signal(signal.SIGINT, self.stop)
            signal.signal(signal.SIGTERM, self.stop)
        except (ValueError, AttributeError):
            pass


    def stop(self, signum, frame):
        logger.info("Received shutdown signal. Stopping worker...")
        self.running = False

    def recover_orphaned_tasks(self):
        """
        Move any orphaned tasks in the processing queue back to the main queue on startup.
        This provides reliability in case the worker process crashed previously.
        """
        logger.info("Checking for orphaned tasks in processing queue...")
        recovered_count = 0
        while True:
            # Atomic transfer from processing back to main queue
            task = self.redis.rpoplpush(REDIS_PROCESSING_KEY, REDIS_QUEUE_KEY)
            if task:
                logger.info(f"Recovered orphaned task and re-enqueued: {task}")
                recovered_count += 1
            else:
                break
        logger.info(f"Completed recovery. Recovered {recovered_count} tasks.")

    def run(self):
        logger.info("Starting Closely AI Worker process...")
        self.recover_orphaned_tasks()

        while self.running:
            try:
                # Atomically pop a task and move it to processing queue
                # BRPOPLPUSH blocks up to 2 seconds to allow checking self.running regularly
                task = self.redis.brpoplpush(REDIS_QUEUE_KEY, REDIS_PROCESSING_KEY, timeout=2)
                if not task:
                    continue

                logger.info(f"Popped task from queue: {task}")
                payload = json.loads(task)
                
                org_id = payload["org_id"]
                conv_id = payload["conv_id"]
                message_text = payload["message_text"]
                retry_count = payload.get("retry_count", 0)

                try:
                    # Execute message processing synchronously (blocking in this worker thread/process)
                    process_message_async(org_id, conv_id, message_text)
                    logger.info(f"Successfully processed message task: {task}")
                    # Remove task from the processing queue
                    self.redis.lrem(REDIS_PROCESSING_KEY, 1, task)
                except Exception as ex:
                    logger.error(f"Error processing message task: {task}. Details: {ex}", exc_info=True)
                    
                    if retry_count < MAX_RETRIES:
                        payload["retry_count"] = retry_count + 1
                        delay = BACKOFF_BASE ** retry_count
                        logger.info(f"Retrying task in {delay}s (Attempt {payload['retry_count']}/{MAX_RETRIES})...")
                        time.sleep(delay)
                        
                        # Re-enqueue to main queue and remove from processing
                        self.redis.lpush(REDIS_QUEUE_KEY, json.dumps(payload))
                        self.redis.lrem(REDIS_PROCESSING_KEY, 1, task)
                    else:
                        logger.error(f"Task exceeded max retries. Moving to DLQ: {task}")
                        # Move to DLQ and remove from processing
                        self.redis.lpush(REDIS_DLQ_KEY, json.dumps(payload))
                        self.redis.lrem(REDIS_PROCESSING_KEY, 1, task)

            except Exception as e:
                logger.error(f"Unexpected error in worker loop: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Worker stopped successfully.")

if __name__ == "__main__":
    worker = Worker()
    worker.run()
