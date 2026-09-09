import logging
import threading
from typing import Optional
from prometheus_client import Counter, Gauge, Histogram, REGISTRY, start_http_server, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi import FastAPI

logger = logging.getLogger(__name__)

# 1. Custom Application & SSE Metrics
ACTIVE_SSE_CONNECTIONS = Gauge(
    "fastapi_active_sse_connections",
    "Number of currently active Server-Sent Events (SSE) connections",
)

# 2. Asynchronous Worker Telemetry Metrics
WORKER_TASKS_PROCESSED_TOTAL = Counter(
    "worker_tasks_processed_total",
    "Total count of background worker tasks processed",
    ["task_type", "status"]
)

WORKER_TASK_DURATION_SECONDS = Histogram(
    "worker_task_duration_seconds",
    "Execution duration of background worker tasks in seconds",
    ["task_type"],
    buckets=(0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)
)

# 3. Redis Queue Depth Metrics
REDIS_QUEUE_DEPTH = Gauge(
    "redis_queue_depth",
    "Current message depth in Redis queues",
    ["queue_name"]
)

# Server state tracking
_metrics_server_started = False
_metrics_server_lock = threading.Lock()


def start_metrics_server(port: int = 9090) -> bool:
    """
    Spawns a dedicated Prometheus HTTP scrape server on internal port 9090.
    Ensures network isolation from public ALB/Nginx traffic.
    """
    global _metrics_server_started
    with _metrics_server_lock:
        if _metrics_server_started:
            return True
        try:
            start_http_server(port)
            _metrics_server_started = True
            logger.info(f"Prometheus metrics server successfully listening on internal port {port}")
            return True
        except OSError as e:
            # Port may already be in use (e.g., during reload or parallel test runs)
            logger.warning(f"Metrics server on port {port} already bound or failed: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to start Prometheus metrics server on port {port}: {e}")
            return False


def get_metrics_response():
    """Generates Prometheus text exposition format response."""
    from fastapi.responses import Response
    return Response(
        content=generate_latest(REGISTRY),
        media_type="text/plain; version=0.0.4; charset=utf-8"
    )


def setup_fastapi_instrumentation(app: FastAPI) -> Instrumentator:
    """
    Attaches prometheus-fastapi-instrumentator to FastAPI for standard RED HTTP metrics
    (request counts, latency histograms, error rates).
    """
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/docs", "/openapi.json", "/redoc"]
    )
    instrumentator.instrument(app)

    @app.get("/internal/metrics", include_in_schema=False)
    def internal_metrics():
        return get_metrics_response()

    return instrumentator

