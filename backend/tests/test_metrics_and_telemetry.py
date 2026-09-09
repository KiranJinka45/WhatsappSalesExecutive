import pytest
import time
from fastapi.testclient import TestClient
from prometheus_client import REGISTRY, generate_latest
from app.main import app
from app.metrics import (
    ACTIVE_SSE_CONNECTIONS,
    WORKER_TASKS_PROCESSED_TOTAL,
    WORKER_TASK_DURATION_SECONDS,
    REDIS_QUEUE_DEPTH,
)
from app.worker import Worker

client = TestClient(app)


def test_metrics_definitions_in_registry():
    """Verify all custom metrics are registered in the default Prometheus registry."""
    metric_names = [metric.name for metric in REGISTRY.collect()]
    assert "fastapi_active_sse_connections" in metric_names
    assert "worker_tasks_processed" in metric_names
    assert "worker_task_duration_seconds" in metric_names
    assert "redis_queue_depth" in metric_names


def test_active_sse_connections_gauge_lifecycle():
    """Test manual and simulated lifecycle increments and decrements for active SSE connections."""
    initial_val = ACTIVE_SSE_CONNECTIONS._value.get()
    
    # Simulate client connection
    ACTIVE_SSE_CONNECTIONS.inc()
    assert ACTIVE_SSE_CONNECTIONS._value.get() == initial_val + 1

    # Simulate second connection
    ACTIVE_SSE_CONNECTIONS.inc()
    assert ACTIVE_SSE_CONNECTIONS._value.get() == initial_val + 2

    # Simulate client disconnects
    ACTIVE_SSE_CONNECTIONS.dec()
    assert ACTIVE_SSE_CONNECTIONS._value.get() == initial_val + 1

    ACTIVE_SSE_CONNECTIONS.dec()
    assert ACTIVE_SSE_CONNECTIONS._value.get() == initial_val


def test_worker_telemetry_metrics():
    """Verify worker task counters and duration histograms observe values accurately."""
    # Observe an outbox dispatch task
    WORKER_TASK_DURATION_SECONDS.labels(task_type="outbox_dispatch").observe(0.125)
    WORKER_TASKS_PROCESSED_TOTAL.labels(task_type="outbox_dispatch", status="success").inc()

    # Observe an inbound task
    WORKER_TASK_DURATION_SECONDS.labels(task_type="inbound_message").observe(0.450)
    WORKER_TASKS_PROCESSED_TOTAL.labels(task_type="inbound_message", status="error").inc()

    output = generate_latest(REGISTRY).decode("utf-8")
    assert 'worker_tasks_processed_total{status="success",task_type="outbox_dispatch"}' in output
    assert 'worker_tasks_processed_total{status="error",task_type="inbound_message"}' in output
    assert 'worker_task_duration_seconds_bucket{le="0.25",task_type="outbox_dispatch"}' in output


def test_redis_queue_depth_gauge():
    """Verify Redis queue depth gauges track inbound and outbox list depths."""
    REDIS_QUEUE_DEPTH.labels(queue_name="closely:queue:outbox").set(42)
    REDIS_QUEUE_DEPTH.labels(queue_name="closely:queue:inbound").set(15)

    output = generate_latest(REGISTRY).decode("utf-8")
    assert 'redis_queue_depth{queue_name="closely:queue:outbox"} 42.0' in output
    assert 'redis_queue_depth{queue_name="closely:queue:inbound"} 15.0' in output


def test_internal_metrics_endpoint():
    """Verify FastAPI /internal/metrics exposes valid Prometheus text format."""
    response = client.get("/internal/metrics")
    assert response.status_code == 200
    assert "text/plain" in response.headers.get("content-type", "")
    assert "fastapi_active_sse_connections" in response.text
